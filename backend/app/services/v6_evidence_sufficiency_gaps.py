"""Descriptive evidence-sufficiency gaps for prospective multi-window research."""
from __future__ import annotations
from pathlib import Path
from typing import Any, Dict
from app.services.challenger_prospective import MEMBERSHIP_PATH
from app.services.v6_forward_monitor import HISTORY_PATH
from app.services.v6_multi_window_history import multi_window_consistency_history


def evidence_sufficiency_gaps(*,membership_path:Path=MEMBERSHIP_PATH,history_path:Path=HISTORY_PATH)->Dict[str,Any]:
    history=multi_window_consistency_history(membership_path=membership_path,history_path=history_path);candidates={}
    for name,row in (history.get("candidates") or {}).items():
        latest=row.get("latest") or {};windows={}
        for key in ("3","7","14"):
            w=(latest.get("windows") or {}).get(key) or {};required=int(w.get("minimum_memberships") or 0);current=int(w.get("membership_count") or 0)
            windows[key]={"days":int(w.get("days") or int(key)),"current_memberships":current,"required_memberships":required,"membership_gap":max(0,required-current),"evidence_sufficient":bool(w.get("evidence_sufficient",False))}
        observations=int(row.get("observation_count") or 0);required_observations=3
        candidates[name]={"observation_count":observations,"minimum_observations_required":required_observations,"confirmation_observation_gap":max(0,required_observations-observations),"confirmation_layer_sufficient":observations>=required_observations,"windows":windows,"new_evidence_only":True,"human_review_only":True,"production_promoted":False}
    return {"ok":True,"title":"ATLAS V6 EVIDENCE SUFFICIENCY GAP DIAGNOSTICS","mode":"DESCRIPTIVE_EVIDENCE_GAPS","candidates":candidates,"duplicate_refreshes_skipped":int(history.get("duplicate_refreshes_skipped") or 0),"readiness_score":None,"automatic_scoring":False,"best_window_selection":False,"automatic_promotion":False,"production_strategy_modified":False,"trading_readiness":"NOT_READY","live_capital_allowed":False,"automatic_real_money_execution":False,"note":"Gaps describe distance from predeclared membership and confirmation-observation minimums only. They are not a readiness percentage, production score, ranking, or promotion decision."}
