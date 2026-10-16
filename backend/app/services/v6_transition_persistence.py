"""Descriptive persistence/reversal diagnostics for prospective consistency transitions."""
from __future__ import annotations
from pathlib import Path
from typing import Any,Dict
from app.services.challenger_prospective import MEMBERSHIP_PATH
from app.services.v6_forward_monitor import HISTORY_PATH
from app.services.v6_multi_window_history import multi_window_consistency_history


def _window_outcome(a:dict[str,Any],b:dict[str,Any],c:dict[str,Any])->str:
    if not bool(c.get("evidence_sufficient",False)):return "BECAME_INSUFFICIENT"
    av=a.get("comparison");bv=b.get("comparison");cv=c.get("comparison")
    if cv==bv:return "PERSISTED"
    if cv==av and bv!=av:return "REVERSED"
    return "CHANGED_AGAIN"


def _disagreement_outcome(a:bool,b:bool,c:bool)->str:
    if c==b:return "PERSISTED"
    if c==a and b!=a:return "REVERSED"
    return "CHANGED_AGAIN"


def transition_persistence_diagnostics(*,membership_path:Path=MEMBERSHIP_PATH,history_path:Path=HISTORY_PATH)->Dict[str,Any]:
    history=multi_window_consistency_history(membership_path=membership_path,history_path=history_path);candidates={}
    for name,row in (history.get("candidates") or {}).items():
        points=row.get("series") or [];checks=[]
        for a,b,c in zip(points,points[1:],points[2:]):
            windows={}
            for key in ("3","7","14"):
                aw=(a.get("windows") or {}).get(key) or {};bw=(b.get("windows") or {}).get(key) or {};cw=(c.get("windows") or {}).get(key) or {}
                windows[key]={"outcome":_window_outcome(aw,bw,cw),"previous":aw.get("comparison"),"transitioned_to":bw.get("comparison"),"next":cw.get("comparison"),"next_evidence_sufficient":bool(cw.get("evidence_sufficient",False))}
            checks.append({"transition_timestamp":b.get("timestamp"),"confirmation_timestamp":c.get("timestamp"),"windows":windows,"disagreement_outcome":_disagreement_outcome(bool(a.get("window_disagreement",False)),bool(b.get("window_disagreement",False)),bool(c.get("window_disagreement",False)))})
        candidates[name]={"observation_count":len(points),"confirmation_check_count":len(checks),"checks":checks,"latest_check":checks[-1] if checks else None,"minimum_observations_required":3,"new_evidence_only":True,"human_review_only":True,"production_promoted":False}
    return {"ok":True,"title":"ATLAS V6 TRANSITION PERSISTENCE / REVERSAL DIAGNOSTICS","mode":"DESCRIPTIVE_NEXT_NEW_EVIDENCE_CONFIRMATION","candidates":candidates,"duplicate_refreshes_skipped":int(history.get("duplicate_refreshes_skipped") or 0),"automatic_scoring":False,"automatic_promotion":False,"production_strategy_modified":False,"trading_readiness":"NOT_READY","live_capital_allowed":False,"automatic_real_money_execution":False,"note":"Each transition is checked only against the next qualifying new-evidence observation. Outcomes are descriptive: PERSISTED, REVERSED, CHANGED_AGAIN, or BECAME_INSUFFICIENT."}
