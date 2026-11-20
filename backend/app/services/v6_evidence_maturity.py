"""Descriptive research-evidence maturity summary without readiness scoring."""
from __future__ import annotations
from pathlib import Path
from typing import Any, Dict
from app.services.challenger_prospective import MEMBERSHIP_PATH
from app.services.v6_forward_monitor import HISTORY_PATH
from app.services.v6_research_status import research_status
from app.services.v6_stability import stability_report
from app.services.v6_window_diversity import diversity_report
from app.services.v6_diversity_trends import diversity_trends
from app.services.v6_multi_window_history import multi_window_consistency_history
from app.services.v6_confirmation_sequences import confirmation_sequence_diagnostics
from app.services.v6_evidence_sufficiency_gaps import evidence_sufficiency_gaps


def _state(present: bool) -> str:
    return "PRESENT" if present else "MISSING"


def research_evidence_maturity(*,membership_path:Path=MEMBERSHIP_PATH,history_path:Path=HISTORY_PATH,**status_paths:Any)->Dict[str,Any]:
    paths=dict(status_paths);paths["membership_path"]=membership_path
    status=research_status(**paths);stability=stability_report(path=history_path)
    common={"membership_path":membership_path,"history_path":history_path}
    diversity=diversity_report(**common);longitudinal=diversity_trends(**common);history=multi_window_consistency_history(**common);sequences=confirmation_sequence_diagnostics(**common);gaps=evidence_sufficiency_gaps(**common)
    progress=status.get("readiness_progress") or {};forward=progress.get("forward") or {};candidates={}
    # research_status always exposes the four declared challenger rows, even when all
    # durable inputs are absent. Do not let those schema placeholders manufacture
    # maturity candidates: require evidence-bearing durable state from at least one
    # source before a challenger enters this descriptive summary.
    evidence_names=set(stability.get("candidates") or {})|set(diversity.get("candidates") or {})|set(longitudinal.get("candidates") or {})|set(history.get("candidates") or {})|set(sequences.get("candidates") or {})|set(gaps.get("candidates") or {})
    forward_names={name for name,row in forward.items() if int((row or {}).get("opened") or 0)>0 or int((row or {}).get("closed") or 0)>0}
    names=evidence_names|forward_names
    eligible=set(stability.get("human_review_eligible") or []);diverse=set(diversity.get("diversity_established") or [])
    for name in sorted(names):
        f=forward.get(name) or {};lr=(longitudinal.get("candidates") or {}).get(name) or {};hr=(history.get("candidates") or {}).get(name) or {};sr=(sequences.get("candidates") or {}).get(name) or {};gr=(gaps.get("candidates") or {}).get(name) or {}
        windows=gr.get("windows") or {};window_sufficient=bool(windows) and all(bool((windows.get(k) or {}).get("evidence_sufficient",False)) for k in ("3","7","14"))
        confirmation_sufficient=bool(gr.get("confirmation_layer_sufficient",False));gap_closed=window_sufficient and confirmation_sufficient
        dimensions={
            "forward_sample":{"state":_state(int(f.get("closed") or 0)>0),"closed":int(f.get("closed") or 0)},
            "uncertainty_support":{"state":_state(bool(f.get("positive_lower_ci95",f.get("uncertainty_supports_positive_edge",False)))),"supports_positive_edge":bool(f.get("positive_lower_ci95",f.get("uncertainty_supports_positive_edge",False)))},
            "stability":{"state":_state(name in eligible),"human_review_eligible":name in eligible},
            "diversity":{"state":_state(name in diverse),"diversity_established":name in diverse},
            "longitudinal_history":{"state":_state(int(lr.get("snapshot_count") or 0)>0),"snapshot_count":int(lr.get("snapshot_count") or 0)},
            "multi_window_evidence":{"state":_state(bool(hr.get("latest"))),"observation_count":int(hr.get("observation_count") or 0)},
            "confirmation_depth":{"state":_state(int(sr.get("confirmation_check_count") or 0)>0),"confirmation_check_count":int(sr.get("confirmation_check_count") or 0)},
            "gap_closure":{"state":_state(gap_closed),"all_windows_sufficient":window_sufficient,"confirmation_layer_sufficient":confirmation_sufficient},
        }
        candidates[name]={"dimensions":dimensions,"present_dimensions":[k for k,v in dimensions.items() if v["state"]=="PRESENT"],"missing_dimensions":[k for k,v in dimensions.items() if v["state"]=="MISSING"],"aggregate_score":None,"readiness_percentage":None,"human_review_only":True,"production_promoted":False}
    return {"ok":True,"title":"ATLAS V6 RESEARCH EVIDENCE MATURITY / MISSING-EVIDENCE SUMMARY","mode":"DESCRIPTIVE_MATURITY_PRESENCE_MISSING","candidates":candidates,"automatic_scoring":False,"weighted_scoring":False,"best_window_selection":False,"automatic_promotion":False,"production_strategy_modified":False,"trading_readiness":"NOT_READY","live_capital_allowed":False,"automatic_real_money_execution":False,"note":"Dimension presence/missing states are descriptive research context only. They are not a readiness score, percentage, ranking, promotion decision, or live-trading approval."}
