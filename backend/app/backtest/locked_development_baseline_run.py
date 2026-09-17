"""Deterministic locked DEVELOPMENT baseline runner.

Consumes only canonical PIT datasets that already passed source_audit. The baseline
uses the locked production thresholds without retuning and never touches holdout data.
Signals are generated from point-in-time history only and filled by the existing
historical engine at the next 5m bar open.
"""
from __future__ import annotations

import argparse,json
from dataclasses import asdict,dataclass
from pathlib import Path

from app.analytics.indicators import rsi
from app.backtest.historical import BacktestAssumptions,BacktestSignal,run_historical_backtest,persist_backtest_result
from app.backtest.io import HistoricalContext,load_historical_contexts
from app.backtest.source_audit import audit_representative_bundle

SYMBOLS=("BTC","ETH","SOL")

@dataclass(frozen=True)
class LockedThresholds:
    min_open_interest_usd:float=75_000.0
    min_volume_24h_usd:float=150_000.0
    rsi_long_max:float=28.0
    rsi_short_min:float=72.0
    min_extension_pct:float=1.4
    max_extension_pct:float=3.5
    min_rr:float=1.8
    htf_alignment_enabled:bool=True
    rsi_period:int=14
    extension_lookback_bars:int=20


def _signal_fn(contexts:list[HistoricalContext],thresholds:LockedThresholds):
    by_ts={c.bar.timestamp:c for c in contexts}
    index_by_ts={c.bar.timestamp:i for i,c in enumerate(contexts)}
    closes=tuple(c.bar.close for c in contexts)
    min_history=max(thresholds.rsi_period+1,thresholds.extension_lookback_bars+1)
    def signal(history):
        if len(history)<min_history:return None
        current=history[-1]
        ctx=by_ts[current.timestamp]
        if ctx.open_interest_usd<thresholds.min_open_interest_usd:return None
        if ctx.volume_24h_usd<thresholds.min_volume_24h_usd:return None
        idx=index_by_ts[current.timestamp]
        rsi_start=idx-thresholds.rsi_period
        rv=rsi(closes[rsi_start:idx+1],thresholds.rsi_period)
        if rv is None:return None
        anchor_idx=idx-thresholds.extension_lookback_bars
        if anchor_idx<0:return None
        anchor=closes[anchor_idx]
        if anchor<=0:return None
        extension=(current.close/anchor-1.0)*100.0
        abs_extension=abs(extension)
        if abs_extension<thresholds.min_extension_pct or abs_extension>thresholds.max_extension_pct:return None
        trend=(ctx.htf_trend or "UNKNOWN").upper()
        long_ok=rv<=thresholds.rsi_long_max and extension<0
        short_ok=rv>=thresholds.rsi_short_min and extension>0
        if thresholds.htf_alignment_enabled:
            if trend=="UP":short_ok=False
            elif trend=="DOWN":long_ok=False
        entry_ref=current.close
        risk_distance=entry_ref*0.01
        if long_ok:
            return BacktestSignal("LONG",entry_ref-risk_distance,entry_ref+risk_distance*thresholds.min_rr)
        if short_ok:
            return BacktestSignal("SHORT",entry_ref+risk_distance,entry_ref-risk_distance*thresholds.min_rr)
        return None
    return signal


def run(*,canonical_root:Path,output_root:Path,summary_path:Path,timeframe:str="5m",thresholds:LockedThresholds=LockedThresholds())->dict:
    audit=audit_representative_bundle(canonical_root,SYMBOLS,timeframe)
    if not audit["ready_for_locked_baseline_batch"]:raise RuntimeError("canonical source audit is not GREEN")
    runs=[]
    for symbol in SYMBOLS:
        path=Path(canonical_root)/f"{symbol}-{timeframe}.csv"
        contexts=load_historical_contexts(path)
        bars=[x.bar for x in contexts]
        result=run_historical_backtest(bars,_signal_fn(contexts,thresholds),BacktestAssumptions())
        persisted=persist_backtest_result(result,Path(output_root)/symbol)
        runs.append({"symbol":symbol,"dataset":str(path),"result_path":str(persisted),"run_id":result["run_id"],"metrics":result["metrics"]})
    total_trades=sum(x["metrics"]["trade_count"] for x in runs)
    total_r=sum(x["metrics"]["total_r"] for x in runs)
    payload={
        "mode":"LOCKED_DEVELOPMENT_BASELINE_RUN",
        "research_window":"dev-2024-h2",
        "source_audit_id":audit["audit_id"],
        "source_audit_green":True,
        "thresholds":asdict(thresholds),
        "threshold_retuning_allowed":False,
        "holdout_data_touched":False,
        "production_strategy_modified":False,
        "live_capital_allowed":False,
        "automatic_real_money_execution":False,
        "runs":runs,
        "aggregate":{"trade_count":total_trades,"total_r":total_r,"expectancy_r":total_r/total_trades if total_trades else 0.0},
        "status":"LOCKED_DEVELOPMENT_BASELINE_COMPLETE",
    }
    summary_path=Path(summary_path);summary_path.parent.mkdir(parents=True,exist_ok=True)
    summary_path.write_text(json.dumps(payload,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    return payload


def main(argv:list[str]|None=None)->int:
    p=argparse.ArgumentParser(description="Run deterministic locked DEVELOPMENT baseline")
    p.add_argument("--canonical-root",type=Path,required=True);p.add_argument("--output-root",type=Path,required=True);p.add_argument("--summary",type=Path,required=True);p.add_argument("--timeframe",default="5m")
    a=p.parse_args(argv);result=run(canonical_root=a.canonical_root,output_root=a.output_root,summary_path=a.summary,timeframe=a.timeframe)
    print(json.dumps(result,indent=2,sort_keys=True));return 0

if __name__=="__main__":raise SystemExit(main())
