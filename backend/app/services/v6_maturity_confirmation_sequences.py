"""Descriptive confirmation-sequence diagnostics over maturity persistence checks."""
from __future__ import annotations
from pathlib import Path
from typing import Any,Dict
from app.services.challenger_prospective import MEMBERSHIP_PATH
from app.services.v6_forward_monitor import HISTORY_PATH
from app.services.v6_maturity_transitions import DIMENSIONS
from app.services.v6_maturity_transition_persistence import maturity_transition_persistence


def maturity_confirmation_sequence_diagnostics(*,membership_path:Path=MEMBERSHIP_PATH,history_path:Path=HISTORY_PATH)->Dict[str,Any]:
    persistence=maturity_transition_persistence(membership_path=membership_path,history_path=history_path);candidates={}
    for name,row in (persistence.get("candidates") or {}).items():
        checks=row.get("checks") or [];dimensions={}
        for key in DIMENSIONS:
            sequence=[((c.get("dimensions") or {}).get(key) or {}).get("outcome") for c in checks]
            sequence=[x for x in sequence if x]
            dimensions[key]={"sequence":sequence,"sequence_length":len(sequence),"latest":sequence[-1] if sequence else None}
        candidates[name]={"observation_count":int(row.get("observation_count") or 0),"confirmation_check_count":int(row.get("confirmation_check_count") or 0),"minimum_observations_required":3,"dimensions":dimensions,"new_evidence_only":True,"duplicate_refresh_resistant":True,"human_review_only":True,"production_promoted":False}
    return {"ok":True,"title":"ATLAS V6 MATURITY CONFIRMATION SEQUENCE DIAGNOSTICS","mode":"DESCRIPTIVE_MATURITY_CONFIRMATION_SEQUENCE","dimensions":list(DIMENSIONS),"candidates":candidates,"duplicate_refreshes_skipped":int(persistence.get("duplicate_refreshes_skipped") or 0),"automatic_scoring":False,"weighted_scoring":False,"readiness_percentage":None,"automatic_promotion":False,"production_strategy_modified":False,"trading_readiness":"NOT_READY","live_capital_allowed":False,"automatic_real_money_execution":False,"note":"Sequences preserve chronological per-dimension maturity confirmation outcomes across retained qualifying new-evidence observations only. They are descriptive and are never collapsed into a readiness score, ranking, promotion rule, or live-trading approval."}
