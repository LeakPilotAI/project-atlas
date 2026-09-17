"""Locked perp-micro historical signal adapter for research-only backtesting."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Sequence
from app.backtest.historical import BacktestSignal,HistoricalBar
from app.backtest.htf_context import htf_allows_side
from app.core.config import Settings,get_settings

@dataclass(frozen=True)
class PerpMicroBaselineConfig:
    rsi_long:float;rsi_short:float;min_extension_pct:float;max_extension_pct:float;min_rr:float;risk_usd:float
    require_oi_volume:bool=True;require_htf_alignment:bool=True;min_open_interest_usd:float=75_000.0;min_volume_24h_usd:float=150_000.0
    @classmethod
    def from_settings(cls,settings:Settings|None=None)->"PerpMicroBaselineConfig":
        s=settings or get_settings();return cls(float(s.perp_micro_rsi_long),float(s.perp_micro_rsi_short),float(s.perp_micro_min_extension_pct),float(s.perp_micro_max_extension_pct),float(s.perp_micro_min_rr),float(s.perp_micro_risk_usd),True,bool(s.perp_micro_htf_align),float(s.perp_micro_min_oi),float(s.perp_micro_min_vol))

def _rsi(closes:Sequence[float],period:int=14)->float|None:
    if len(closes)<period+1:return None
    deltas=[closes[i]-closes[i-1] for i in range(len(closes)-period,len(closes))];g=[max(x,0.0) for x in deltas];l=[max(-x,0.0) for x in deltas];ag=sum(g)/period;al=sum(l)/period
    if al==0:return 100.0
    if ag==0:return 0.0
    rs=ag/al;return 100.0-(100.0/(1.0+rs))

def _extension_pct(closes:Sequence[float],lookback:int=20)->float|None:
    if len(closes)<lookback:return None
    window=list(closes[-lookback:]);mean=sum(window)/len(window)
    return None if mean<=0 else (window[-1]-mean)/mean*100.0

def locked_perp_micro_signal(history:Sequence[HistoricalBar],*,config:PerpMicroBaselineConfig|None=None,oi_volume_eligible:bool|None=None,htf_regime_aligned:bool|None=None,htf_trend:str|None=None)->BacktestSignal|None:
    cfg=config or PerpMicroBaselineConfig.from_settings()
    if cfg.require_oi_volume and oi_volume_eligible is not True:return None
    closes=[b.close for b in history];rsi=_rsi(closes);extension=_extension_pct(closes)
    if rsi is None or extension is None:return None
    current=history[-1].close;ext_abs=abs(extension)
    if ext_abs<cfg.min_extension_pct or ext_abs>cfg.max_extension_pct:return None
    side=None
    if rsi<=cfg.rsi_long and extension<0:side="LONG"
    elif rsi>=cfg.rsi_short and extension>0:side="SHORT"
    if side is None:return None
    if cfg.require_htf_alignment:
        # Real historical runs must use the production-equivalent side-aware trend.
        # htf_regime_aligned remains only for backward-compatible synthetic fixtures.
        if htf_trend is not None:
            if not htf_allows_side(side,htf_trend):return None
        elif htf_regime_aligned is not True:return None
    if side=="LONG":
        stop=min(b.low for b in history[-10:]);risk=current-stop
        if risk<=0:return None
        return BacktestSignal("LONG",stop,current+risk*cfg.min_rr)
    stop=max(b.high for b in history[-10:]);risk=stop-current
    if risk<=0:return None
    return BacktestSignal("SHORT",stop,current-risk*cfg.min_rr)

def baseline_metadata(config:PerpMicroBaselineConfig|None=None)->dict:
    cfg=config or PerpMicroBaselineConfig.from_settings();return {"name":"LOCKED_PERP_MICRO_BASELINE","rsi_long":cfg.rsi_long,"rsi_short":cfg.rsi_short,"min_extension_pct":cfg.min_extension_pct,"max_extension_pct":cfg.max_extension_pct,"min_rr":cfg.min_rr,"risk_usd":cfg.risk_usd,"min_open_interest_usd":cfg.min_open_interest_usd,"min_volume_24h_usd":cfg.min_volume_24h_usd,"requires_oi_volume_eligibility":cfg.require_oi_volume,"requires_htf_alignment":cfg.require_htf_alignment,"htf_semantics":"production 1h close vs SMA20; UP > +0.2%, DOWN < -0.2%, FLAT/UNKNOWN allow either side","production_strategy_modified":False,"live_capital_allowed":False,"automatic_real_money_execution":False}
