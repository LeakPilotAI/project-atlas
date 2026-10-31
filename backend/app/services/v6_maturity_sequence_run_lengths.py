"""Descriptive run-length / recent-streak diagnostics for maturity confirmation sequences."""
from __future__ import annotations
from pathlib import Path
from typing import Any,Dict
from app.services.challenger_prospective import MEMBERSHIP_PATH
from app.services.v6_forward_monitor import HISTORY_PATH
from app.services.v6_maturity_transitions import DIMENSIONS
from app.services.v6_maturity_confirmation_sequences import maturity_confirmation_sequence_diagnostics


def _runs(sequence:list[str])->list[dict[str,Any]]:
    if not sequence:return []
    runs=[];current=sequence[0];length=1
    for value in sequence[1:]:
        if value==current:length+=1
        else:
            runs.append({"outcome":current,"length":length});current=value;length=1
    runs.append({"outcome":current,"length":length})
    return runs


def maturity_sequence_run_length_diagnostics(*,membership_path:Path=MEMBERSHIP_PATH,history_path:Path=HISTORY_PATH)->Dict[str,Any]:
    sequences=maturity_confirmation_sequence_diagnostics(membership_path=membership_path,history_path=history_path);candidates={}
    for name,row in (sequences.get("candidates") or {}).items():
        dims={}
        for key in DIMENSIONS:
            src=(row.get("dimensions") or {}).get(key) or {};sequence=list(src.get("sequence") or []);runs=_runs(sequence);latest=runs[-1] if runs else None;previous=runs[-2] if len(runs)>1 else None
            dims[key]={"sequence":sequence,"sequence_length":len(sequence),"latest":src.get("latest"),"run_count":len(runs),"runs":runs,"current_run_length":int((latest or {}).get("length") or 0),"current_run_outcome":((latest or {}).get("outcome")),"previous_run_outcome":((previous or {}).get("outcome")),"previous_run_length":int((previous or {}).get("length") or 0),"run_boundary_present":len(runs)>1}
        candidates[name]={"observation_count":int(row.get("observation_count") or 0),"confirmation_check_count":int(row.get("confirmation_check_count") or 0),"minimum_observations_required":3,"dimensions":dims,"duplicate_refresh_resistant":True,"new_evidence_only":True,"human_review_only":True,"production_promoted":False}
    return {"ok":True,"title":"ATLAS V6 MATURITY SEQUENCE RUN-LENGTH / RECENT-STREAK DIAGNOSTICS","mode":"DESCRIPTIVE_MATURITY_SEQUENCE_RUN_LENGTH","dimensions":list(DIMENSIONS),"candidates":candidates,"duplicate_refreshes_skipped":int(sequences.get("duplicate_refreshes_skipped") or 0),"automatic_scoring":False,"weighted_scoring":False,"readiness_percentage":None,"automatic_promotion":False,"production_strategy_modified":False,"trading_readiness":"NOT_READY","live_capital_allowed":False,"automatic_real_money_execution":False,"note":"Run-length diagnostics describe consecutive identical maturity confirmation outcomes only. They report current and prior runs without assigning a score, ranking, tuning action, promotion rule, or live-trading approval."}
