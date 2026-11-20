"""Deterministic, research-only historical replay primitives for Atlas.

This module deliberately has no exchange adapter and no production-setting mutation path.
Callers provide timestamped bars and a point-in-time signal function. Orders generated
at bar i are filled at bar i+1 open so the decision cannot consume its own fill bar.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from hashlib import sha256
import json
import math
import os
import re
from pathlib import Path
from typing import Callable, Iterable, Literal, Sequence

from app.core.durable_io import sync_parent, write_flushed
from app.services.paper_execution_model import conservative_stop_exit

Side = Literal["LONG", "SHORT"]


@dataclass(frozen=True)
class HistoricalBar:
    timestamp: str
    symbol: str
    timeframe: str
    open: float
    high: float
    low: float
    close: float
    volume: float
    funding_rate: float = 0.0


@dataclass(frozen=True)
class BacktestSignal:
    side: Side
    stop_price: float
    target_price: float


@dataclass(frozen=True)
class BacktestAssumptions:
    risk_usd: float = 1.0
    fee_bps_per_fill: float = 3.5
    slippage_bps_per_fill: float = 1.0
    initial_equity_usd: float = 10_000.0
    intrabar_priority: Literal["STOP_FIRST", "TARGET_FIRST"] = "STOP_FIRST"


@dataclass(frozen=True)
class BacktestTrade:
    symbol: str
    side: Side
    signal_timestamp: str
    entry_timestamp: str
    exit_timestamp: str
    entry_price: float
    exit_price: float
    stop_price: float
    target_price: float
    quantity: float
    gross_pnl_usd: float
    fees_usd: float
    slippage_usd: float
    funding_usd: float
    net_pnl_usd: float
    net_r: float
    exit_reason: str


SignalFn = Callable[[Sequence[HistoricalBar]], BacktestSignal | None]


def _finite(value, *, positive=False):
    try:
        valid = type(value) in (int, float) and math.isfinite(value)
    except OverflowError as error:
        raise ValueError("Unsupported historical numeric range") from error
    if not valid or (positive and value <= 0):
        raise ValueError("Finite historical numeric evidence required")


def _validate_assumptions(assumptions):
    if type(assumptions) is not BacktestAssumptions:
        raise ValueError("Explicit backtest assumptions required")
    for value in (assumptions.risk_usd, assumptions.initial_equity_usd):
        _finite(value, positive=True)
    for value in (assumptions.fee_bps_per_fill, assumptions.slippage_bps_per_fill):
        _finite(value)
        if not 0 <= value < 10000:
            raise ValueError("Execution cost assumptions must be nonnegative and below 10000 bps")
    if assumptions.intrabar_priority not in ("STOP_FIRST", "TARGET_FIRST"):
        raise ValueError("Explicit intrabar priority required")


def validate_historical_timestamps(values):
    """Compare actual aware UTC instants, never lexicographic offset strings."""
    instants=[]
    for value in values:
        if type(value) is not str or not 1<=len(value)<=64:
            raise ValueError("Explicit bounded timezone-aware historical timestamps required")
        try:
            parsed=datetime.fromisoformat(value)
        except ValueError as error:
            raise ValueError("Malformed historical timestamp") from error
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError("Timezone-aware historical timestamps required")
        instants.append(parsed.astimezone(UTC))
    if instants!=sorted(instants) or len(set(instants))!=len(instants):
        raise ValueError("bars must have unique ascending timestamps in actual UTC order")
    return instants


def _validate_bars(bars: Iterable[HistoricalBar]) -> list[HistoricalBar]:
    rows=list(bars)
    if not rows:
        raise ValueError("historical dataset is empty")
    key={(b.symbol,b.timeframe) for b in rows}
    if len(key)!=1:
        raise ValueError("one deterministic run requires exactly one symbol/timeframe")
    validate_historical_timestamps([b.timestamp for b in rows])
    for b in rows:
        for value in (b.open,b.high,b.low,b.close):
            _finite(value, positive=True)
        for value in (b.volume,b.funding_rate):
            _finite(value)
        if b.volume < 0 or not b.low <= b.open <= b.high or not b.low <= b.close <= b.high:
            raise ValueError("Inconsistent historical OHLC/volume evidence")
        if min(b.open,b.high,b.low,b.close)<=0 or b.low>b.high:
            raise ValueError(f"invalid OHLC bar at {b.timestamp}")
    return rows


def _slipped(price:float,side:Side,is_entry:bool,bps:float)->float:
    adverse=1 if (side=="LONG") == is_entry else -1
    return price*(1+adverse*bps/10_000.0)


def _exit_on_bar(side:Side,bar:HistoricalBar,stop:float,target:float,priority:str)->tuple[float,str]|None:
    stop_hit=bar.low<=stop if side=="LONG" else bar.high>=stop
    target_hit=bar.high>=target if side=="LONG" else bar.low<=target
    # A later bar can gap beyond the stop. Reuse the existing conservative
    # PAPER price rule with zero slippage here; the replay applies costs once.
    stop_fill=conservative_stop_exit(side=side,mark=bar.open,stop_price=stop,slippage_bps=0)
    if stop_hit and target_hit:
        return (stop_fill,"STOP") if priority=="STOP_FIRST" else (target,"TARGET")
    if stop_hit:return stop_fill,"STOP"
    if target_hit:return target,"TARGET"
    return None


def run_historical_backtest(bars:Iterable[HistoricalBar],signal_fn:SignalFn,assumptions:BacktestAssumptions=BacktestAssumptions())->dict:
    _validate_assumptions(assumptions)
    rows=_validate_bars(bars);trades:list[BacktestTrade]=[];equity=assumptions.initial_equity_usd;curve=[equity];i=0
    while i<len(rows)-1:
        history=tuple(rows[:i+1])  # strict PIT view: signal sees nothing after rows[i]
        signal=signal_fn(history)
        if signal is None:
            i+=1;continue
        if type(signal) is not BacktestSignal or signal.side not in ("LONG", "SHORT"):
            raise ValueError("Explicit historical signal side required")
        _finite(signal.stop_price, positive=True)
        _finite(signal.target_price, positive=True)
        raw_entry=rows[i+1].open;entry=_slipped(raw_entry,signal.side,True,assumptions.slippage_bps_per_fill)
        risk_per_unit=(entry-signal.stop_price) if signal.side=="LONG" else (signal.stop_price-entry)
        reward_per_unit=(signal.target_price-entry) if signal.side=="LONG" else (entry-signal.target_price)
        if risk_per_unit<=0 or reward_per_unit<=0:
            raise ValueError("signal stop/target must define positive risk and reward from next-bar entry")
        qty=assumptions.risk_usd/risk_per_unit;exit_i=None;raw_exit=None;reason=None;funding=0.0
        for j in range(i+1,len(rows)):
            funding += abs(qty*rows[j].open)*rows[j].funding_rate*(1 if signal.side=="LONG" else -1)
            hit=_exit_on_bar(signal.side,rows[j],signal.stop_price,signal.target_price,assumptions.intrabar_priority)
            if hit:
                raw_exit,reason=hit;exit_i=j;break
        if exit_i is None:
            exit_i=len(rows)-1;raw_exit=rows[exit_i].close;reason="END_OF_DATA"
        exit_price=_slipped(float(raw_exit),signal.side,False,assumptions.slippage_bps_per_fill)
        direction=1 if signal.side=="LONG" else -1
        gross=qty*(exit_price-entry)*direction
        fees=(abs(qty*entry)+abs(qty*exit_price))*assumptions.fee_bps_per_fill/10_000.0
        slippage=abs(qty*(entry-raw_entry))+abs(qty*(float(raw_exit)-exit_price))
        net=gross-fees-funding;net_r=net/assumptions.risk_usd
        for value in (entry,exit_price,qty):
            _finite(value, positive=True)
        for value in (gross,fees,slippage,funding,net,net_r):
            _finite(value)
        trade=BacktestTrade(rows[i].symbol,signal.side,rows[i].timestamp,rows[i+1].timestamp,rows[exit_i].timestamp,entry,exit_price,signal.stop_price,signal.target_price,qty,gross,fees,slippage,funding,net,net_r,str(reason))
        trades.append(trade);equity+=net;curve.append(equity);i=exit_i+1
    wins=sum(t.net_pnl_usd>0 for t in trades);gross_win=sum(max(t.net_pnl_usd,0) for t in trades);gross_loss=-sum(min(t.net_pnl_usd,0) for t in trades)
    peak=curve[0];max_dd=0.0
    for value in curve:
        peak=max(peak,value);max_dd=max(max_dd,peak-value)
    metrics={"trade_count":len(trades),"win_rate":wins/len(trades) if trades else 0.0,"expectancy_r":sum(t.net_r for t in trades)/len(trades) if trades else 0.0,"total_r":sum(t.net_r for t in trades),"profit_factor":gross_win/gross_loss if gross_loss>0 else None,"max_drawdown_usd":max_dd,"ending_equity_usd":equity,"fees_usd":sum(t.fees_usd for t in trades),"slippage_usd":sum(t.slippage_usd for t in trades),"funding_usd":sum(t.funding_usd for t in trades)}
    for value in metrics.values():
        if value is not None:
            _finite(value)
    payload={"mode":"RESEARCH_ONLY_HISTORICAL_BACKTEST","symbol":rows[0].symbol,"timeframe":rows[0].timeframe,"dataset":{"first_timestamp":rows[0].timestamp,"last_timestamp":rows[-1].timestamp,"bar_count":len(rows)},"assumptions":asdict(assumptions),"trades":[asdict(t) for t in trades],"equity_curve_usd":curve,"metrics":metrics,"production_strategy_modified":False,"live_capital_allowed":False,"automatic_real_money_execution":False}
    canonical=json.dumps(payload,sort_keys=True,separators=(",",":"));payload["run_id"]=sha256(canonical.encode()).hexdigest()[:20]
    return payload


def persist_backtest_result(result:dict,output_dir:Path)->Path:
    run_id=result.get("run_id")
    if not isinstance(run_id,str) or not re.fullmatch(r"[0-9a-f]{20}",run_id):
        raise ValueError("Exact bounded historical run identity required")
    output_dir=Path(output_dir)
    if any(p.is_symlink() or p.is_junction() for p in (output_dir,*output_dir.parents)):
        raise ValueError("Linked historical output directory refused")
    text=json.dumps(result,sort_keys=True,indent=2,allow_nan=False)+"\n"
    output_dir.mkdir(parents=True,exist_ok=True);path=output_dir/f"{run_id}.json"
    if path.is_symlink() or path.is_junction():
        raise ValueError("Linked historical result refused")
    try:
        with path.open("x",encoding="utf-8",newline="\n") as handle:
            write_flushed(handle,text)
    except FileExistsError:
        if path.stat().st_nlink!=1:
            raise ValueError("Hard-linked historical result refused")
        with path.open("r+b") as handle:
            if handle.read() not in (text.encode(),text.replace("\n","\r\n").encode()):
                raise RuntimeError("deterministic run_id collision with different or incomplete result content")
            os.fsync(handle.fileno())
    sync_parent(path)
    return path
