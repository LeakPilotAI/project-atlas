"""Lightweight consolidated V6 research evidence status.

Normal reads consume durable membership/cache/history only. No prospective,
retrospective, exit-replay, interaction, or scorecard recomputation occurs here.
"""
from __future__ import annotations
from pathlib import Path
from typing import Any
from app.services.v6_research_status import research_status
from app.services.v6_evidence_trends import evidence_trends
from app.services.v6_stability import stability_report
from app.services.v6_window_diversity import diversity_report
from app.services.v6_diversity_trends import diversity_trends
from app.services.v6_forward_monitor import HISTORY_PATH


def research_evidence_ui(*,history_path:Path=HISTORY_PATH,**status_paths:Any)->dict[str,Any]:
    status=research_status(**status_paths)
    trends=evidence_trends(path=history_path)
    stability=stability_report(path=history_path)
    membership_path=status_paths.get("membership_path")
    diversity_kwargs={"history_path":history_path}
    diversity_trend_kwargs={"history_path":history_path}
    if membership_path is not None:
        diversity_kwargs["membership_path"]=membership_path
        diversity_trend_kwargs["membership_path"]=membership_path
    diversity=diversity_report(**diversity_kwargs)
    longitudinal=diversity_trends(**diversity_trend_kwargs)
    progress=status.get("readiness_progress") or {}
    latest={}
    for name,series in (trends.get("series") or {}).items():
        if series:latest[name]=series[-1]
    long_summary={name:{"trend":row.get("trend"),"snapshot_count":int(row.get("snapshot_count") or 0),"longitudinal_evidence_sufficient":bool(row.get("longitudinal_evidence_sufficient",False)),"latest":row.get("latest")} for name,row in (longitudinal.get("candidates") or {}).items()}
    return {"ok":True,"title":"ATLAS V6 RESEARCH EVIDENCE","mode":"LIGHTWEIGHT_DURABLE_READ_ONLY","normal_command_center_recompute":False,"readiness_progress":progress,"evidence":{"snapshot_count":int(trends.get("snapshot_count") or 0),"latest_by_challenger":latest,"trend_summary":trends.get("summary") or {}},"candidate_state":{"research_nominations_cached":int(((progress.get("shadow_paper") or {}).get("prospective_nomination_count")) or 0),"comparison_endpoint":"/api/validation/challengers/comparison","comparison_refresh_on_normal_status":False},"stability":{"human_review_eligible":stability.get("human_review_eligible") or [],"candidates":stability.get("candidates") or {},"required_qualifying_snapshots":3,"minimum_separation_hours":6.0},"diversity":{"established":diversity.get("diversity_established") or [],"candidates":diversity.get("candidates") or {},"snapshot_available":bool(diversity.get("snapshot_available",False)),"required_calendar_days":3,"required_regimes":2,"minimum_memberships_per_regime":10,"diversity_is_production_approval":False},"longitudinal_diversity":{"candidates":long_summary,"snapshot_count":int(longitudinal.get("snapshot_count") or 0),"required_longitudinal_snapshots":3,"method":"CUMULATIVE_POINT_IN_TIME","fixed_duration_windows_evaluated":False,"trend_is_production_approval":False},"separation":{"research_nomination_is_production_approval":False,"human_review_is_production_approval":False,"research_evidence_is_trading_readiness":False,"diversity_is_trading_readiness":False,"longitudinal_diversity_is_trading_readiness":False},"heavy_research_recompute":False,"automatic_promotion":False,"production_strategy_modified":False,"trading_readiness":"NOT_READY","live_capital_allowed":False,"automatic_real_money_execution":False}
