"""Descriptive stability/repetition diagnostics over maturity confirmation sequences."""
from __future__ import annotations
from pathlib import Path
from typing import Any,Dict
from app.services.challenger_prospective import MEMBERSHIP_PATH
from app.services.v6_forward_monitor import HISTORY_PATH
from app.services.v6_maturity_transitions import DIMENSIONS
from app.services.v6_maturity_confirmation_sequences import maturity_confirmation_sequence_diagnostics


def _classify(sequence:list[str])->str:
    if len(sequence)<2:return "INSUFFICIENT_HISTORY"
    if len(set(sequence))==1:return "REPEATED_OUTCOME"
    if len(sequence)>=3 and all(sequence[i]!=sequence[i-1] for i in range(1,len(sequence))):return "ALTERNATING_PATTERN"
    return "MIXED_SEQUENCE"


def maturity_sequence_stability_diagnostics(*,membership_path:Path=MEMBERSHIP_PATH,history_path:Path=HISTORY_PATH)->Dict[str,Any]:
    sequences=maturity_confirmation_sequence_diagnostics(membership_path=membership_path,history_path=history_path);candidates={}
    for name,row in (sequences.get("candidates") or {}).items():
        dims={}
        for key in DIMENSIONS:
            src=(row.get("dimensions") or {}).get(key) or {};sequence=list(src.get("sequence") or [])
            dims[key]={"sequence":sequence,"sequence_length":len(sequence),"latest":src.get("latest"),"pattern":_classify(sequence),"repeated_latest":len(sequence)>=2 and sequence[-1]==sequence[-2]}
        candidates[name]={"observation_count":int(row.get("observation_count") or 0),"confirmation_check_count":int(row.get("confirmation_check_count") or 0),"minimum_observations_required":3,"dimensions":dims,"duplicate_refresh_resistant":True,"new_evidence_only":True,"human_review_only":True,"production_promoted":False}
    return {"ok":True,"title":"ATLAS V6 MATURITY SEQUENCE STABILITY / REPETITION DIAGNOSTICS","mode":"DESCRIPTIVE_MATURITY_SEQUENCE_STABILITY","dimensions":list(DIMENSIONS),"candidates":candidates,"duplicate_refreshes_skipped":int(sequences.get("duplicate_refreshes_skipped") or 0),"automatic_scoring":False,"weighted_scoring":False,"readiness_percentage":None,"automatic_promotion":False,"production_strategy_modified":False,"trading_readiness":"NOT_READY","live_capital_allowed":False,"automatic_real_money_execution":False,"note":"Patterns describe chronological repetition only: REPEATED_OUTCOME, ALTERNATING_PATTERN, MIXED_SEQUENCE, or INSUFFICIENT_HISTORY. They are not readiness scores, rankings, promotion rules, or live-trading approval."}
