"""Fail-closed multi-snapshot stability gate for V6 human research review.

Consumes append-only forward evidence snapshots only. This can make a candidate
eligible for human review; it cannot promote production or unlock live capital.
"""
from __future__ import annotations
from datetime import datetime
from pathlib import Path
from typing import Any, Dict
from app.services.paper_journal import iter_jsonl
from app.services.v6_forward_monitor import HISTORY_PATH

MIN_CLOSED=100
MIN_QUALIFYING_SNAPSHOTS=3
MIN_SEPARATION_HOURS=6.0

def _parse(v:Any):
    try:return datetime.fromisoformat(str(v).replace("Z","+00:00"))
    except Exception:return None

def _rows(path:Path)->list[Dict[str,Any]]:
    if not path.exists():return []
    return [r for r in iter_jsonl(path) if r.get("event")=="v6_forward_evidence_snapshot"]

def _qualifies(point:Dict[str,Any])->bool:
    return bool(int(point.get("closed") or 0)>=MIN_CLOSED and float(point.get("expectancy") or 0)>0 and point.get("uncertainty_supports_positive_edge") is True)

def stability_report(*,path:Path=HISTORY_PATH)->Dict[str,Any]:
    rows=_rows(path); names=[]
    for r in rows:
        for name in (((r.get("evidence") or {}).get("forward") or {})):
            if name not in names:names.append(name)
    candidates={}
    for name in names:
        qualifying=[]
        for r in rows:
            p=(((r.get("evidence") or {}).get("forward") or {}).get(name))
            if isinstance(p,dict) and _qualifies(p):qualifying.append((r,p))
        separated=[]
        for r,p in qualifying:
            ts=_parse(r.get("timestamp"))
            if ts is None:continue
            if not separated or (ts-separated[-1][0]).total_seconds()>=MIN_SEPARATION_HOURS*3600:separated.append((ts,p))
        recent=separated[-MIN_QUALIFYING_SNAPSHOTS:]
        sustained=len(recent)>=MIN_QUALIFYING_SNAPSHOTS
        no_expectancy_reversal=bool(sustained and all(float(p.get("expectancy") or 0)>0 for _,p in recent))
        no_ci_reversal=bool(sustained and all(p.get("uncertainty_supports_positive_edge") is True for _,p in recent))
        candidates[name]={"qualifying_snapshot_count":len(separated),"required_qualifying_snapshots":MIN_QUALIFYING_SNAPSHOTS,"minimum_separation_hours":MIN_SEPARATION_HOURS,"sustained_positive_expectancy":no_expectancy_reversal,"sustained_positive_lower_ci95":no_ci_reversal,"human_review_eligible":bool(sustained and no_expectancy_reversal and no_ci_reversal),"production_promoted":False}
    eligible=[n for n,v in candidates.items() if v["human_review_eligible"]]
    return {"ok":True,"title":"ATLAS V6 MULTI-SNAPSHOT PROSPECTIVE STABILITY","mode":"APPEND_ONLY_FORWARD_EVIDENCE_ONLY","snapshot_count":len(rows),"candidates":candidates,"human_review_eligible":eligible,"history_rewritten":False,"retrospective_substitution":False,"automatic_promotion":False,"production_strategy_modified":False,"trading_readiness":"NOT_READY","live_capital_allowed":False,"automatic_real_money_execution":False,"note":"Human-review eligibility requires at least three qualifying forward snapshots separated by >=6 hours after >=100 closes with positive expectancy and a positive lower 95% expectancy bound. It is not production approval."}
