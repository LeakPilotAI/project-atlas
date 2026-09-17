"""Locked perp-micro historical signal adapter for research-only backtesting.

This adapter intentionally consumes only data that can be reconstructed from the
historical bar stream. Inputs required by production but absent from the current
historical contract (open interest, 24h volume eligibility, HTF regime) are explicit
fail-closed gates unless the caller disables the corresponding requirement for a
controlled research run.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from app.backtest.historical import BacktestSignal,HistoricalBar
from app.core.config import Settings,get_settings


@dataclass(frozen=True)
class PerpMicroBaselineConfig:
    rsi_long: float
    rsi_short: float
    min_extension_pct: float
    max_extension_pct: float
    min_rr: float
    risk_usd: float
    require_oi_volume: bool = True
    require_htf_alignment: bool = True

    @classmethod
    def from_settings(cls,settings:Settings|None=None)->"PerpMicroBaselineConfig":
        s=settings or get_settings()
        return cls(
            rsi_long=float(s.perp_micro_rsi_long),
            rsi_short=float(s.perp_micro_rsi_short),
            min_extension_pct=float(s.perp_micro_min_extension_pct),
            max_extension_pct=float(s.perp_micro_max_extension_pct),
            min_rr=float(s.perp_micro_min_rr),
            risk_usd=float(s.perp_micro_risk_usd),
            require_oi_volume=True,
            require_htf_alignment=bool(s.perp_micro_htf_align),
        )


def _rsi(closes:Sequence[float],period:int=14)->float|None:
    if len(closes)<period+1:return None
    deltas=[closes[i]-closes[i-1] for i in range(len(closes)-period,len(closes))]
    gains=[max(x,0.0) for x in deltas];losses=[max(-x,0.0) for x in deltas]
    avg_gain=sum(gains)/period;avg_loss=sum(losses)/period
    if avg_loss==0:return 100.0
    if avg_gain==0:return 0.0
    rs=avg_gain/avg_loss
    return 100.0-(100.0/(1.0+rs))


def _extension_pct(closes:Sequence[float],lookback:int=20)->float|None:
    if len(closes)<lookback:return None
    window=list(closes[-lookback:]);mean=sum(window)/len(window)
    if mean<=0:return None
    return (window[-1]-mean)/mean*100.0


def locked_perp_micro_signal(
    history:Sequence[HistoricalBar],
    *,
    config:PerpMicroBaselineConfig|None=None,
    oi_volume_eligible:bool|None=None,
    htf_regime_aligned:bool|None=None,
)->BacktestSignal|None:
    cfg=config or PerpMicroBaselineConfig.from_settings()
    if cfg.require_oi_volume and oi_volume_eligible is not True:return None
    if cfg.require_htf_alignment and htf_regime_aligned is not True:return None
    closes=[b.close for b in history]
    rsi=_rsi(closes);extension=_extension_pct(closes)
    if rsi is None or extension is None:return None
    current=history[-1].close
    ext_abs=abs(extension)
    if ext_abs<cfg.min_extension_pct or ext_abs>cfg.max_extension_pct:return None
    recent_lows=[b.low for b in history[-10:]];recent_highs=[b.high for b in history[-10:]]
    if rsi<=cfg.rsi_long and extension<0:
        stop=min(recent_lows)
        risk=current-stop
        if risk<=0:return None
        return BacktestSignal("LONG",stop,current+risk*cfg.min_rr)
    if rsi>=cfg.rsi_short and extension>0:
        stop=max(recent_highs)
        risk=stop-current
        if risk<=0:return None
        return BacktestSignal("SHORT",stop,current-risk*cfg.min_rr)
    return None


def baseline_metadata(config:PerpMicroBaselineConfig|None=None)->dict:
    cfg=config or PerpMicroBaselineConfig.from_settings()
    return {
        "name":"LOCKED_PERP_MICRO_BASELINE",
        "rsi_long":cfg.rsi_long,
        "rsi_short":cfg.rsi_short,
        "min_extension_pct":cfg.min_extension_pct,
        "max_extension_pct":cfg.max_extension_pct,
        "min_rr":cfg.min_rr,
        "risk_usd":cfg.risk_usd,
        "requires_oi_volume_eligibility":cfg.require_oi_volume,
        "requires_htf_alignment":cfg.require_htf_alignment,
        "production_strategy_modified":False,
        "live_capital_allowed":False,
        "automatic_real_money_execution":False,
    }
