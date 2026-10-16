"""Predeclared fixed-duration forward diversity diagnostics.

Reports every declared window; never selects a favorable window after observing
results. Read-only research and never a production promotion mechanism.
"""
from __future__ import annotations
from datetime import timedelta
from pathlib import Path
from typing import Any,Dict
from app.services.paper_journal import iter_jsonl
from app.services.challenger_prospective import MEMBERSHIP_PATH
from app.services.v6_forward_monitor import HISTORY_PATH
from app.services.v6_window_diversity import _parse
from app.services.v6_diversity_trends import _state

WINDOW_DAYS=7
MIN_WINDOW_MEMBERSHIPS=20
PREDECLARED_WINDOWS=((3,10),(7,20),(14,30))

def _comparison(cumulative:dict,recent:dict,enough:bool)->str:
    if not enough:return "INSUFFICIENT_RECENT_WINDOW_EVIDENCE"
    if cumulative["diversity_established"] and not recent["diversity_established"]:return "RECENT_CONCENTRATION"
    if not cumulative["diversity_established"] and recent["diversity_established"]:return "RECENT_BROADENING"
    if cumulative["diversity_established"] and recent["diversity_established"]:return "DIVERSITY_PERSISTS"
    return "CONCENTRATED_BOTH_WINDOWS"

def _load(membership_path:Path,history_path:Path):
    memberships=[r for r in iter_jsonl(membership_path) if r.get("event")=="membership"] if membership_path.exists() else []
    snapshots=[r for r in iter_jsonl(history_path) if r.get("event")=="v6_forward_evidence_snapshot" and _parse(r.get("timestamp"))] if history_path.exists() else []
    snapshots.sort(key=lambda r:_parse(r.get("timestamp")))
    return memberships,(snapshots[-1] if snapshots else None)

def fixed_window_diversity(*,membership_path:Path=MEMBERSHIP_PATH,history_path:Path=HISTORY_PATH,window_days:int=WINDOW_DAYS)->Dict[str,Any]:
    memberships,latest=_load(membership_path,history_path);cutoff=_parse(latest.get("timestamp")) if latest else None;candidates={}
    if cutoff:
        days=max(1,int(window_days));start=cutoff-timedelta(days=days);forward=((latest.get("evidence") or {}).get("forward") or {})
        for name in forward:
            cumulative=[];recent=[]
            for r in memberships:
                if name not in (r.get("challengers") or []):continue
                ts=_parse(r.get("entry_timestamp"))
                if ts is None or ts>cutoff:continue
                cumulative.append(r)
                if ts>start:recent.append(r)
            cs=_state(cumulative);rs=_state(recent);enough=len(recent)>=MIN_WINDOW_MEMBERSHIPS
            candidates[name]={"window_days":days,"window_start_exclusive":start.isoformat(),"window_end_inclusive":cutoff.isoformat(),"minimum_window_memberships":MIN_WINDOW_MEMBERSHIPS,"recent_window_evidence_sufficient":enough,"cumulative":cs,"recent_window":rs,"comparison":_comparison(cs,rs,enough),"human_review_only":True,"production_promoted":False}
    return {"ok":True,"title":"ATLAS V6 FIXED-DURATION FORWARD DIVERSITY","mode":"READ_ONLY_POINT_IN_TIME_FIXED_WINDOW","snapshot_available":latest is not None,"window_days":max(1,int(window_days)),"candidates":candidates,"future_membership_excluded":True,"retrospective_reclassification":False,"automatic_promotion":False,"production_strategy_modified":False,"trading_readiness":"NOT_READY","live_capital_allowed":False,"automatic_real_money_execution":False}

def multi_window_diversity(*,membership_path:Path=MEMBERSHIP_PATH,history_path:Path=HISTORY_PATH)->Dict[str,Any]:
    memberships,latest=_load(membership_path,history_path);cutoff=_parse(latest.get("timestamp")) if latest else None;candidates={}
    if cutoff:
        forward=((latest.get("evidence") or {}).get("forward") or {})
        for name in forward:
            eligible=[]
            for r in memberships:
                if name not in (r.get("challengers") or []):continue
                ts=_parse(r.get("entry_timestamp"))
                if ts is not None and ts<=cutoff:eligible.append(r)
            cs=_state(eligible);windows={};labels=[]
            for days,min_n in PREDECLARED_WINDOWS:
                start=cutoff-timedelta(days=days);recent=[r for r in eligible if (_parse(r.get("entry_timestamp")) or cutoff)<=cutoff and (_parse(r.get("entry_timestamp")) or cutoff)>start];rs=_state(recent);enough=len(recent)>=min_n;comparison=_comparison(cs,rs,enough);labels.append(comparison)
                windows[str(days)]={"window_days":days,"window_start_exclusive":start.isoformat(),"window_end_inclusive":cutoff.isoformat(),"minimum_window_memberships":min_n,"recent_window_evidence_sufficient":enough,"recent_window":rs,"comparison":comparison}
            sufficient=[x for x in labels if x!="INSUFFICIENT_RECENT_WINDOW_EVIDENCE"]
            candidates[name]={"cumulative":cs,"windows":windows,"window_disagreement":len(set(sufficient))>1,"interpretable_window_count":len(sufficient),"selected_best_window":None,"human_review_only":True,"production_promoted":False}
    return {"ok":True,"title":"ATLAS V6 PREDECLARED MULTI-WINDOW DIVERSITY","mode":"READ_ONLY_PREDECLARED_MULTI_WINDOW","snapshot_available":latest is not None,"predeclared_windows":[{"days":d,"minimum_memberships":n} for d,n in PREDECLARED_WINDOWS],"all_windows_reported":True,"best_window_selection":False,"candidates":candidates,"future_membership_excluded":True,"retrospective_reclassification":False,"automatic_promotion":False,"production_strategy_modified":False,"trading_readiness":"NOT_READY","live_capital_allowed":False,"automatic_real_money_execution":False,"note":"3d/7d/14d are declared together and all reported. Disagreement is retained; no favorable-window selection or production retuning."}
