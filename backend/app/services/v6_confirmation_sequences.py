"""Descriptive confirmation-sequence diagnostics over prospective persistence checks."""
from __future__ import annotations
from pathlib import Path
from typing import Any,Dict
from app.services.challenger_prospective import MEMBERSHIP_PATH
from app.services.v6_forward_monitor import HISTORY_PATH
from app.services.v6_transition_persistence import transition_persistence_diagnostics


def confirmation_sequence_diagnostics(*,membership_path:Path=MEMBERSHIP_PATH,history_path:Path=HISTORY_PATH)->Dict[str,Any]:
    persistence=transition_persistence_diagnostics(membership_path=membership_path,history_path=history_path);candidates={}
    for name,row in (persistence.get("candidates") or {}).items():
        checks=row.get("checks") or [];windows={}
        for key in ("3","7","14"):
            sequence=[((c.get("windows") or {}).get(key) or {}).get("outcome") for c in checks]
            sequence=[x for x in sequence if x]
            windows[key]={"sequence":sequence,"sequence_length":len(sequence),"latest":sequence[-1] if sequence else None}
        disagreement=[c.get("disagreement_outcome") for c in checks if c.get("disagreement_outcome")]
        candidates[name]={"observation_count":int(row.get("observation_count") or 0),"confirmation_check_count":int(row.get("confirmation_check_count") or 0),"minimum_observations_required":3,"windows":windows,"disagreement_sequence":disagreement,"disagreement_sequence_length":len(disagreement),"new_evidence_only":True,"human_review_only":True,"production_promoted":False}
    return {"ok":True,"title":"ATLAS V6 CONFIRMATION SEQUENCE DIAGNOSTICS","mode":"DESCRIPTIVE_CONFIRMATION_SEQUENCE","candidates":candidates,"duplicate_refreshes_skipped":int(persistence.get("duplicate_refreshes_skipped") or 0),"automatic_scoring":False,"automatic_promotion":False,"production_strategy_modified":False,"trading_readiness":"NOT_READY","live_capital_allowed":False,"automatic_real_money_execution":False,"note":"Sequences preserve chronological confirmation outcomes for each predeclared window and disagreement state. They are descriptive only and are never collapsed into a favorable score or production decision."}
