"""Prospective point-in-time history for the predeclared 3d/7d/14d diversity method.

Duplicate refreshes do not count as new observations. A later snapshot is retained for
a candidate only when prospective membership count or forward closed evidence grows.
This is descriptive research only and never a production-promotion mechanism.
"""
from __future__ import annotations
from datetime import timedelta
from pathlib import Path
from typing import Any, Dict
from app.services.paper_journal import iter_jsonl
from app.services.challenger_prospective import MEMBERSHIP_PATH
from app.services.v6_forward_monitor import HISTORY_PATH
from app.services.v6_window_diversity import _parse
from app.services.v6_diversity_trends import _state
from app.services.v6_fixed_window_diversity import PREDECLARED_WINDOWS, _comparison


def multi_window_consistency_history(*, membership_path:Path=MEMBERSHIP_PATH, history_path:Path=HISTORY_PATH)->Dict[str,Any]:
    memberships=[r for r in iter_jsonl(membership_path) if r.get("event")=="membership"] if membership_path.exists() else []
    snapshots=[r for r in iter_jsonl(history_path) if r.get("event")=="v6_forward_evidence_snapshot" and _parse(r.get("timestamp"))] if history_path.exists() else []
    snapshots.sort(key=lambda r:_parse(r.get("timestamp")))
    series:dict[str,list[dict[str,Any]]]={}; last_progress:dict[str,tuple[int,int]]={}; skipped=0
    for snap in snapshots:
        cutoff=_parse(snap.get("timestamp")); forward=((snap.get("evidence") or {}).get("forward") or {})
        for name,fwd in forward.items():
            eligible=[]
            for r in memberships:
                if name not in (r.get("challengers") or []):continue
                ts=_parse(r.get("entry_timestamp"))
                if ts is not None and ts<=cutoff:eligible.append(r)
            progress=(len(eligible),int((fwd or {}).get("closed") or 0))
            prior=last_progress.get(name)
            if prior is not None and progress[0]<=prior[0] and progress[1]<=prior[1]:
                skipped+=1;continue
            last_progress[name]=progress; cumulative=_state(eligible); windows={}; labels=[]
            for days,min_n in PREDECLARED_WINDOWS:
                start=cutoff-timedelta(days=days); recent=[]
                for r in eligible:
                    ts=_parse(r.get("entry_timestamp"))
                    if ts is not None and ts>start:recent.append(r)
                state=_state(recent); enough=len(recent)>=min_n; label=_comparison(cumulative,state,enough)
                if enough:labels.append(label)
                windows[str(days)]={"days":days,"minimum_memberships":min_n,"membership_count":len(recent),"evidence_sufficient":enough,"comparison":label,"diversity_established":bool(state.get("diversity_established",False))}
            series.setdefault(name,[]).append({"timestamp":snap.get("timestamp"),"prospective_membership_count":progress[0],"forward_closed":progress[1],"windows":windows,"interpretable_window_count":len(labels),"window_disagreement":len(set(labels))>1})
    candidates={}
    for name,points in series.items():
        candidates[name]={"observation_count":len(points),"duplicate_refresh_resistant":True,"new_evidence_required":True,"latest":points[-1] if points else None,"series":points,"human_review_only":True,"production_promoted":False}
    return {"ok":True,"title":"ATLAS V6 PROSPECTIVE MULTI-WINDOW CONSISTENCY HISTORY","mode":"APPEND_ONLY_POINT_IN_TIME_NEW_EVIDENCE_ONLY","predeclared_windows":[{"days":d,"minimum_memberships":n} for d,n in PREDECLARED_WINDOWS],"snapshot_count":len(snapshots),"duplicate_refreshes_skipped":skipped,"candidates":candidates,"best_window_selection":False,"retrospective_reclassification":False,"automatic_promotion":False,"production_strategy_modified":False,"trading_readiness":"NOT_READY","live_capital_allowed":False,"automatic_real_money_execution":False,"note":"History preserves every declared window at each qualifying point in time. Duplicate refreshes cannot manufacture stability; new prospective membership or closed evidence is required."}
