"""Descriptive persistence/reversal diagnostics for maturity-dimension transitions."""
from __future__ import annotations
from pathlib import Path
from typing import Any,Dict
from app.services.challenger_prospective import MEMBERSHIP_PATH
from app.services.v6_forward_monitor import HISTORY_PATH
from app.services.v6_maturity_transitions import DIMENSIONS,maturity_change_history


def _outcome(a:str,b:str,c:str)->str:
    if c==b:return "PERSISTED"
    if c==a and b!=a:return "REVERSED"
    return "CHANGED_AGAIN"


def maturity_transition_persistence(*,membership_path:Path=MEMBERSHIP_PATH,history_path:Path=HISTORY_PATH)->Dict[str,Any]:
    history=maturity_change_history(membership_path=membership_path,history_path=history_path);candidates={}
    for name,row in (history.get("candidates") or {}).items():
        states=row.get("states") or [];checks=[]
        for a,b,c in zip(states,states[1:],states[2:]):
            dims={}
            for key in DIMENSIONS:
                av=(a.get("states") or {}).get(key,"MISSING");bv=(b.get("states") or {}).get(key,"MISSING");cv=(c.get("states") or {}).get(key,"MISSING")
                dims[key]={"outcome":_outcome(av,bv,cv),"previous":av,"transitioned_to":bv,"next":cv,"transition":f"{av}->{bv}"}
            checks.append({"transition_timestamp":b.get("timestamp"),"confirmation_timestamp":c.get("timestamp"),"dimensions":dims})
        candidates[name]={"observation_count":len(states),"confirmation_check_count":len(checks),"minimum_observations_required":3,"checks":checks,"latest_check":checks[-1] if checks else None,"duplicate_refresh_resistant":True,"new_evidence_only":True,"human_review_only":True,"production_promoted":False}
    return {"ok":True,"title":"ATLAS V6 MATURITY TRANSITION PERSISTENCE / REVERSAL DIAGNOSTICS","mode":"DESCRIPTIVE_MATURITY_NEXT_NEW_EVIDENCE_CONFIRMATION","dimensions":list(DIMENSIONS),"candidates":candidates,"duplicate_refreshes_skipped":int(history.get("duplicate_refreshes_skipped") or 0),"automatic_scoring":False,"weighted_scoring":False,"readiness_percentage":None,"automatic_promotion":False,"production_strategy_modified":False,"trading_readiness":"NOT_READY","live_capital_allowed":False,"automatic_real_money_execution":False,"note":"Each maturity-dimension transition is checked only against the next retained qualifying new-evidence observation. Outcomes are descriptive: PERSISTED, REVERSED, or CHANGED_AGAIN."}
