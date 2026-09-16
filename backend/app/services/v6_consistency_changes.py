"""Descriptive transition diagnostics over new-evidence-only multi-window history."""
from __future__ import annotations
from pathlib import Path
from typing import Any,Dict
from app.services.challenger_prospective import MEMBERSHIP_PATH
from app.services.v6_forward_monitor import HISTORY_PATH
from app.services.v6_multi_window_history import multi_window_consistency_history


def _transition(a:Any,b:Any)->str:
    return "UNCHANGED" if a==b else f"{a}->{b}"


def consistency_change_diagnostics(*,membership_path:Path=MEMBERSHIP_PATH,history_path:Path=HISTORY_PATH)->Dict[str,Any]:
    history=multi_window_consistency_history(membership_path=membership_path,history_path=history_path);candidates={}
    for name,row in (history.get("candidates") or {}).items():
        points=row.get("series") or [];transitions=[]
        for previous,current in zip(points,points[1:]):
            windows={}
            for key in ("3","7","14"):
                a=(previous.get("windows") or {}).get(key) or {};b=(current.get("windows") or {}).get(key) or {}
                windows[key]={"comparison":_transition(a.get("comparison"),b.get("comparison")),"comparison_changed":a.get("comparison")!=b.get("comparison"),"sufficiency":_transition(bool(a.get("evidence_sufficient",False)),bool(b.get("evidence_sufficient",False))),"sufficiency_changed":bool(a.get("evidence_sufficient",False))!=bool(b.get("evidence_sufficient",False)),"diversity":_transition(bool(a.get("diversity_established",False)),bool(b.get("diversity_established",False))),"diversity_changed":bool(a.get("diversity_established",False))!=bool(b.get("diversity_established",False))}
            before=bool(previous.get("window_disagreement",False));after=bool(current.get("window_disagreement",False))
            disagreement="PERSISTED" if before and after else "ENTERED" if not before and after else "LEFT" if before and not after else "ABSENT"
            transitions.append({"from_timestamp":previous.get("timestamp"),"to_timestamp":current.get("timestamp"),"windows":windows,"disagreement_transition":disagreement,"prospective_membership_growth":int(current.get("prospective_membership_count") or 0)-int(previous.get("prospective_membership_count") or 0),"forward_closed_growth":int(current.get("forward_closed") or 0)-int(previous.get("forward_closed") or 0)})
        candidates[name]={"observation_count":len(points),"transition_count":len(transitions),"transitions":transitions,"latest_transition":transitions[-1] if transitions else None,"new_evidence_only":True,"human_review_only":True,"production_promoted":False}
    return {"ok":True,"title":"ATLAS V6 PROSPECTIVE CONSISTENCY CHANGE DIAGNOSTICS","mode":"DESCRIPTIVE_NEW_EVIDENCE_TRANSITIONS","candidates":candidates,"duplicate_refreshes_skipped":int(history.get("duplicate_refreshes_skipped") or 0),"best_window_selection":False,"automatic_scoring":False,"automatic_promotion":False,"production_strategy_modified":False,"trading_readiness":"NOT_READY","live_capital_allowed":False,"automatic_real_money_execution":False,"note":"Transitions describe changes between qualifying new-evidence observations only. They do not rank windows, score candidates, retune gates, or approve production."}
