"""Prospective-only V6 challenger comparison against contemporaneous baseline.

Consumes the frozen forward cohort report. No retrospective rows or SHADOW data
are substituted. Research nomination is informational only.
"""
from __future__ import annotations
from typing import Any, Dict

MIN_CLOSED=100

def _f(v:Any)->float:
    try:return float(v)
    except (TypeError,ValueError):return 0.0

def _ci_low(row:Dict[str,Any]):
    ci=(row.get("uncertainty") or {}).get("expectancy_ci95")
    return ci[0] if isinstance(ci,(list,tuple)) and len(ci)>=2 else None

def compare_report(prospective:Dict[str,Any])->Dict[str,Any]:
    baseline=prospective.get("baseline") if isinstance(prospective,dict) else {}; baseline=baseline if isinstance(baseline,dict) else {}
    b_n=int(baseline.get("n") or 0); b_exp=_f(baseline.get("expectancy")); b_dd=_f(baseline.get("max_drawdown_r")); b_ci=(baseline.get("uncertainty") or {}).get("expectancy_ci95")
    out={}; nominations=[]
    for name,row in ((prospective.get("challengers") or {}) if isinstance(prospective,dict) else {}).items():
        row=row if isinstance(row,dict) else {}; m=row.get("metrics") if isinstance(row.get("metrics"),dict) else {}; closed=int(row.get("closed") or 0); exp=_f(m.get("expectancy")); ci_low=_ci_low(row); sample_ok=closed>=MIN_CLOSED; baseline_sample_ok=b_n>=MIN_CLOSED; positive=exp>0; ci_positive=ci_low is not None and float(ci_low)>0; beats_baseline=exp>b_exp; nomination=bool(sample_ok and baseline_sample_ok and positive and ci_positive and beats_baseline)
        item={"opened":int(row.get("opened") or 0),"closed":closed,"open":int(row.get("open") or 0),"minimum_closed":MIN_CLOSED,"sample_sufficient":sample_ok,"metrics":m,"uncertainty":row.get("uncertainty") or {},"expectancy_delta_vs_baseline":round(exp-b_exp,6),"max_drawdown_delta_vs_baseline":round(_f(m.get("max_drawdown_r"))-b_dd,6),"positive_expectancy":positive,"positive_lower_expectancy_ci95":ci_positive,"beats_contemporaneous_baseline_expectancy":beats_baseline,"research_nomination":nomination,"prospective_only":True,"promoted":False}
        out[name]=item
        if nomination:nominations.append(name)
    return {"ok":True,"title":"ATLAS V6 PROSPECTIVE CANDIDATE COMPARISON","mode":"FORWARD_ONLY_CONTEMPORANEOUS_BASELINE","cohort":(prospective.get("marker") or {}).get("cohort"),"cutoff":(prospective.get("marker") or {}).get("started_at"),"baseline":{"closed":b_n,"metrics":{k:v for k,v in baseline.items() if k!="uncertainty"},"uncertainty":baseline.get("uncertainty") or {},"sample_sufficient":b_n>=MIN_CLOSED},"candidates":out,"research_nominations":nominations,"retrospective_substitution":False,"shadow_population_used":False,"membership_frozen_at_open":True,"automatic_promotion":False,"production_strategy_modified":False,"trading_readiness":"NOT_READY","live_capital_allowed":False,"automatic_real_money_execution":False,"note":"A research nomination requires >=100 forward closes, positive expectancy, positive lower 95% expectancy bound, and expectancy above the contemporaneous forward baseline. It is not production approval."}

def candidate_comparison()->Dict[str,Any]:
    from app.services.challenger_prospective import prospective_report
    return compare_report(prospective_report())
