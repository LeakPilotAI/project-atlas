"""Fixed-duration forward diversity diagnostics.

Compares recent frozen prospective membership against cumulative PIT diversity so
old history cannot hide recent concentration. Read-only research; never promotes.
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


def fixed_window_diversity(*,membership_path:Path=MEMBERSHIP_PATH,history_path:Path=HISTORY_PATH,window_days:int=WINDOW_DAYS)->Dict[str,Any]:
    memberships=[r for r in iter_jsonl(membership_path) if r.get("event")=="membership"] if membership_path.exists() else []
    snapshots=[r for r in iter_jsonl(history_path) if r.get("event")=="v6_forward_evidence_snapshot" and _parse(r.get("timestamp"))] if history_path.exists() else []
    snapshots.sort(key=lambda r:_parse(r.get("timestamp")))
    latest=snapshots[-1] if snapshots else None
    cutoff=_parse(latest.get("timestamp")) if latest else None
    candidates={}
    if cutoff:
        start=cutoff-timedelta(days=max(1,int(window_days)))
        forward=((latest.get("evidence") or {}).get("forward") or {})
        for name in forward:
            cumulative=[];recent=[]
            for r in memberships:
                if name not in (r.get("challengers") or []):continue
                ts=_parse(r.get("entry_timestamp"))
                if ts is None or ts>cutoff:continue
                cumulative.append(r)
                if ts>start:recent.append(r)
            cumulative_state=_state(cumulative);recent_state=_state(recent)
            enough=len(recent)>=MIN_WINDOW_MEMBERSHIPS
            if not enough:comparison="INSUFFICIENT_RECENT_WINDOW_EVIDENCE"
            elif cumulative_state["diversity_established"] and not recent_state["diversity_established"]:comparison="RECENT_CONCENTRATION"
            elif not cumulative_state["diversity_established"] and recent_state["diversity_established"]:comparison="RECENT_BROADENING"
            elif cumulative_state["diversity_established"] and recent_state["diversity_established"]:comparison="DIVERSITY_PERSISTS"
            else:comparison="CONCENTRATED_BOTH_WINDOWS"
            candidates[name]={"window_days":max(1,int(window_days)),"window_start_exclusive":start.isoformat(),"window_end_inclusive":cutoff.isoformat(),"minimum_window_memberships":MIN_WINDOW_MEMBERSHIPS,"recent_window_evidence_sufficient":enough,"cumulative":cumulative_state,"recent_window":recent_state,"comparison":comparison,"human_review_only":True,"production_promoted":False}
    return {"ok":True,"title":"ATLAS V6 FIXED-DURATION FORWARD DIVERSITY","mode":"READ_ONLY_POINT_IN_TIME_FIXED_WINDOW","snapshot_available":latest is not None,"window_days":max(1,int(window_days)),"candidates":candidates,"future_membership_excluded":True,"retrospective_reclassification":False,"automatic_promotion":False,"production_strategy_modified":False,"trading_readiness":"NOT_READY","live_capital_allowed":False,"automatic_real_money_execution":False,"note":"Recent-window concentration/broadening is descriptive research evidence only. It does not establish expectancy, independence, production approval, or live readiness."}
