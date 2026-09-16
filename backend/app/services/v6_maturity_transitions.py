"""Descriptive maturity-state transitions across qualifying new-evidence observations."""
from __future__ import annotations
from pathlib import Path
from typing import Any, Dict
from app.services.challenger_prospective import MEMBERSHIP_PATH
from app.services.v6_forward_monitor import HISTORY_PATH
from app.services.v6_multi_window_history import multi_window_consistency_history

DIMENSIONS=("forward_sample","uncertainty_support","stability","diversity","longitudinal_history","multi_window_evidence","confirmation_depth","gap_closure")


def _state(v:bool)->str:return "PRESENT" if v else "MISSING"
def _transition(a:str,b:str)->str:return f"{a}->{b}"


def maturity_change_history(*,membership_path:Path=MEMBERSHIP_PATH,history_path:Path=HISTORY_PATH)->Dict[str,Any]:
    history=multi_window_consistency_history(membership_path=membership_path,history_path=history_path);candidates={}
    for name,row in (history.get("candidates") or {}).items():
        series=row.get("series") or [];states=[]
        for i,p in enumerate(series):
            windows=p.get("windows") or {};sufficient=bool(windows) and all(bool((windows.get(k) or {}).get("evidence_sufficient",False)) for k in ("3","7","14"))
            interpretable=int(p.get("interpretable_window_count") or 0);closed=int(p.get("forward_closed") or 0);obs=i+1
            state={
                "forward_sample":_state(closed>0),
                "uncertainty_support":"MISSING",
                "stability":"MISSING",
                "diversity":_state(any(bool((windows.get(k) or {}).get("diversity_established",False)) for k in ("3","7","14"))),
                "longitudinal_history":_state(obs>1),
                "multi_window_evidence":_state(interpretable>0),
                "confirmation_depth":_state(obs>=3),
                "gap_closure":_state(sufficient and obs>=3),
            }
            states.append({"timestamp":p.get("timestamp"),"states":state})
        transitions=[]
        for a,b in zip(states,states[1:]):
            dims={k:{"from":a["states"][k],"to":b["states"][k],"transition":_transition(a["states"][k],b["states"][k]),"changed":a["states"][k]!=b["states"][k]} for k in DIMENSIONS}
            transitions.append({"from_timestamp":a.get("timestamp"),"to_timestamp":b.get("timestamp"),"dimensions":dims})
        candidates[name]={"observation_count":len(states),"transition_count":len(transitions),"states":states,"transitions":transitions,"latest_transition":transitions[-1] if transitions else None,"duplicate_refresh_resistant":True,"new_evidence_only":True,"human_review_only":True,"production_promoted":False}
    return {"ok":True,"title":"ATLAS V6 MATURITY CHANGE HISTORY / NEW-EVIDENCE TRANSITION DIAGNOSTICS","mode":"DESCRIPTIVE_MATURITY_NEW_EVIDENCE_TRANSITIONS","dimensions":list(DIMENSIONS),"candidates":candidates,"duplicate_refreshes_skipped":int(history.get("duplicate_refreshes_skipped") or 0),"automatic_scoring":False,"weighted_scoring":False,"readiness_percentage":None,"automatic_promotion":False,"production_strategy_modified":False,"trading_readiness":"NOT_READY","live_capital_allowed":False,"automatic_real_money_execution":False,"note":"Transitions describe PRESENT/MISSING state changes over retained qualifying observations only. They are not readiness scores, promotion rules, or live-trading approval."}
