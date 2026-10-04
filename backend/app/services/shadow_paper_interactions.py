"""V6 SHADOW-vs-PAPER interaction diagnostics.

Populations remain separate. This module applies identical descriptive buckets to
both populations and reports deltas only as research clues. It never pools returns,
changes production gates, or grants live-capital permission.
"""
from __future__ import annotations

from typing import Any, Callable, Dict, Optional, Sequence

from app.analytics.regime import normalize_regime
from app.services.outcome_research import load_paper_closes, load_shadow_resolved
from app.services.paper_validation import metrics, uncertainty

MIN_N = 30


def _num(v: Any) -> Optional[float]:
    try: return float(v)
    except (TypeError, ValueError): return None


def _features(row: Dict[str, Any]) -> Dict[str, Any]:
    return row.get("features") if isinstance(row.get("features"), dict) else {}


def _extension(row: Dict[str, Any]) -> Optional[float]:
    f=_features(row); return _num(f.get("ext_pct") if f.get("ext_pct") is not None else row.get("extension_pct"))


def _quality(row: Dict[str, Any]) -> Optional[float]:
    f=_features(row); raw=f.get("qscore") if f.get("qscore") is not None else row.get("signal_score")
    return _num(raw)


def _slice(rows: Sequence[Dict[str, Any]], pred: Callable[[Dict[str, Any]], bool]) -> Dict[str, Any]:
    selected=[r for r in rows if pred(r)]
    return {**metrics(selected), "uncertainty": uncertainty(selected), "sample_sufficient": len(selected)>=MIN_N}


def _pair(paper, shadow, pred):
    p=_slice(paper,pred); s=_slice(shadow,pred)
    return {"paper":p,"shadow":s,"expectancy_delta_shadow_minus_paper":round(float(s.get("expectancy",0))-float(p.get("expectancy",0)),6),"comparable_sample":bool(p["sample_sufficient"] and s["sample_sufficient"])}


def interaction_report(*, paper: Optional[Sequence[Dict[str,Any]]]=None, shadow: Optional[Sequence[Dict[str,Any]]]=None) -> Dict[str,Any]:
    p=list(paper) if paper is not None else load_paper_closes()
    s=list(shadow) if shadow is not None else load_shadow_resolved()
    defs={
        "long":{"definition":"side == LONG","pred":lambda r:str(r.get("side") or "").upper()=="LONG"},
        "short":{"definition":"side == SHORT","pred":lambda r:str(r.get("side") or "").upper()=="SHORT"},
        "trend":{"definition":"regime in TREND_UP,TREND_DOWN","pred":lambda r:normalize_regime(r.get("regime_normalized") or r.get("regime")) in {"TREND_UP","TREND_DOWN"}},
        "range_low_vol":{"definition":"regime in RANGE,LOW_VOLATILITY","pred":lambda r:normalize_regime(r.get("regime_normalized") or r.get("regime")) in {"RANGE","LOW_VOLATILITY"}},
        "extension_ge_3":{"definition":"extension >= 3%","pred":lambda r:(_extension(r) is not None and _extension(r)>=3.0)},
        "quality_ge_85":{"definition":"quality >= 85","pred":lambda r:(_quality(r) is not None and _quality(r)>=85.0)},
        "trend_ext3_q85":{"definition":"trend AND extension >=3% AND quality >=85","pred":lambda r:(normalize_regime(r.get("regime_normalized") or r.get("regime")) in {"TREND_UP","TREND_DOWN"} and _extension(r) is not None and _extension(r)>=3.0 and _quality(r) is not None and _quality(r)>=85.0)},
    }
    interactions={k:{"definition":v["definition"],**_pair(p,s,v["pred"])} for k,v in defs.items()}
    nominations=[]
    for name,v in interactions.items():
        if v["comparable_sample"] and v["expectancy_delta_shadow_minus_paper"]>0:
            nominations.append({"interaction":name,"reason":"SHADOW expectancy exceeded PAPER under the identical descriptive bucket.","prospective_validation_required":True})
    return {
        "ok":True,"title":"ATLAS V6 SHADOW-vs-PAPER INTERACTION DIAGNOSTICS","mode":"RESEARCH_ONLY_SEPARATE_POPULATIONS",
        "paper_baseline":{**metrics(p),"uncertainty":uncertainty(p)},"shadow_baseline":{**metrics(s),"uncertainty":uncertainty(s)},
        "paper_n":len(p),"shadow_n":len(s),"combined_performance":None,"populations_pooled":False,"interactions":interactions,
        "prospective_nominations":nominations,"automatic_gate_change":False,"production_strategy_modified":False,"automatic_promotion":False,
        "live_capital_allowed":False,"automatic_real_money_execution":False,
        "note":"Deltas compare separate populations under identical definitions. Selection effects remain possible; nominations require prospective validation before any production consideration."
    }
