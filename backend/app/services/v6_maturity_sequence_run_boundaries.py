"""Descriptive transitions between adjacent maturity confirmation-sequence runs."""
from __future__ import annotations
from pathlib import Path
from typing import Any,Dict
from app.services.challenger_prospective import MEMBERSHIP_PATH
from app.services.v6_forward_monitor import HISTORY_PATH
from app.services.v6_maturity_transitions import DIMENSIONS
from app.services.v6_maturity_sequence_run_lengths import maturity_sequence_run_length_diagnostics


def _boundaries(runs:list[dict[str,Any]])->list[dict[str,Any]]:
    out=[]
    for i,(left,right) in enumerate(zip(runs,runs[1:]),start=1):
        out.append({"boundary_index":i,"from_outcome":left.get("outcome"),"from_length":int(left.get("length") or 0),"to_outcome":right.get("outcome"),"to_length":int(right.get("length") or 0),"transition":f"{left.get('outcome')}->{right.get('outcome')}"})
    return out


def maturity_sequence_run_boundary_diagnostics(*,membership_path:Path=MEMBERSHIP_PATH,history_path:Path=HISTORY_PATH)->Dict[str,Any]:
    run_lengths=maturity_sequence_run_length_diagnostics(membership_path=membership_path,history_path=history_path);candidates={}
    for name,row in (run_lengths.get("candidates") or {}).items():
        dims={}
        for key in DIMENSIONS:
            src=(row.get("dimensions") or {}).get(key) or {};runs=list(src.get("runs") or []);boundaries=_boundaries(runs)
            dims[key]={"sequence":list(src.get("sequence") or []),"sequence_length":int(src.get("sequence_length") or 0),"run_count":int(src.get("run_count") or 0),"runs":runs,"boundary_count":len(boundaries),"boundaries":boundaries,"latest_boundary":boundaries[-1] if boundaries else None,"current_run_outcome":src.get("current_run_outcome"),"current_run_length":int(src.get("current_run_length") or 0)}
        candidates[name]={"observation_count":int(row.get("observation_count") or 0),"confirmation_check_count":int(row.get("confirmation_check_count") or 0),"minimum_observations_required":3,"dimensions":dims,"duplicate_refresh_resistant":True,"new_evidence_only":True,"human_review_only":True,"production_promoted":False}
    return {"ok":True,"title":"ATLAS V6 MATURITY SEQUENCE RUN BOUNDARY TRANSITION DIAGNOSTICS","mode":"DESCRIPTIVE_MATURITY_RUN_BOUNDARY_TRANSITIONS","dimensions":list(DIMENSIONS),"candidates":candidates,"duplicate_refreshes_skipped":int(run_lengths.get("duplicate_refreshes_skipped") or 0),"automatic_scoring":False,"weighted_scoring":False,"readiness_percentage":None,"automatic_promotion":False,"production_strategy_modified":False,"trading_readiness":"NOT_READY","live_capital_allowed":False,"automatic_real_money_execution":False,"note":"Run boundaries describe chronological transitions between adjacent same-outcome runs only. Boundary count and run lengths are descriptive and do not create readiness scores, rankings, tuning actions, promotion rules, or live-trading approval."}
