"""Descriptive recurrence diagnostics for maturity confirmation-sequence run boundaries."""
from __future__ import annotations
from pathlib import Path
from typing import Any,Dict
from app.services.challenger_prospective import MEMBERSHIP_PATH
from app.services.v6_forward_monitor import HISTORY_PATH
from app.services.v6_maturity_transitions import DIMENSIONS
from app.services.v6_maturity_sequence_run_boundaries import maturity_sequence_run_boundary_diagnostics


def _recurrence(boundaries:list[dict[str,Any]])->list[dict[str,Any]]:
    grouped:dict[str,dict[str,Any]]={}
    for boundary in boundaries:
        transition=str(boundary.get("transition") or "")
        if not transition:
            continue
        row=grouped.setdefault(transition,{"transition":transition,"from_outcome":boundary.get("from_outcome"),"to_outcome":boundary.get("to_outcome"),"count":0,"occurrences":[],"latest_occurrence":None})
        occurrence={"boundary_index":int(boundary.get("boundary_index") or 0),"from_length":int(boundary.get("from_length") or 0),"to_length":int(boundary.get("to_length") or 0)}
        row["count"]+=1;row["occurrences"].append(occurrence);row["latest_occurrence"]=occurrence
    return list(grouped.values())


def maturity_sequence_run_boundary_recurrence_diagnostics(*,membership_path:Path=MEMBERSHIP_PATH,history_path:Path=HISTORY_PATH)->Dict[str,Any]:
    boundary_data=maturity_sequence_run_boundary_diagnostics(membership_path=membership_path,history_path=history_path);candidates={}
    for name,row in (boundary_data.get("candidates") or {}).items():
        dims={}
        for key in DIMENSIONS:
            src=(row.get("dimensions") or {}).get(key) or {};boundaries=list(src.get("boundaries") or []);recurrences=_recurrence(boundaries)
            dims[key]={"boundary_count":int(src.get("boundary_count") or 0),"boundaries":boundaries,"distinct_transition_count":len(recurrences),"recurrences":recurrences,"latest_boundary":src.get("latest_boundary"),"current_run_outcome":src.get("current_run_outcome"),"current_run_length":int(src.get("current_run_length") or 0)}
        candidates[name]={"observation_count":int(row.get("observation_count") or 0),"confirmation_check_count":int(row.get("confirmation_check_count") or 0),"minimum_observations_required":3,"dimensions":dims,"duplicate_refresh_resistant":True,"new_evidence_only":True,"human_review_only":True,"production_promoted":False}
    return {"ok":True,"title":"ATLAS V6 MATURITY SEQUENCE RUN BOUNDARY RECURRENCE DIAGNOSTICS","mode":"DESCRIPTIVE_MATURITY_RUN_BOUNDARY_RECURRENCE","dimensions":list(DIMENSIONS),"candidates":candidates,"duplicate_refreshes_skipped":int(boundary_data.get("duplicate_refreshes_skipped") or 0),"automatic_scoring":False,"weighted_scoring":False,"readiness_percentage":None,"automatic_promotion":False,"production_strategy_modified":False,"trading_readiness":"NOT_READY","live_capital_allowed":False,"automatic_real_money_execution":False,"note":"Exact adjacent-run transition forms are grouped and counted descriptively. Recurrence frequency and run-length context do not create readiness scores, rankings, tuning actions, promotion rules, or live-trading approval."}
