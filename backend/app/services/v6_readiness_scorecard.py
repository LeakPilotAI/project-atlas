"""Consolidated Atlas V6 research readiness scorecard.

Research evidence only. The scorecard fails closed and cannot promote production,
unlock live capital, or place orders.
"""
from __future__ import annotations
from typing import Any, Dict, Optional

MIN_FORWARD_CLOSED = 100
MIN_REPLAY_COVERAGE = 0.70


def _f(v: Any) -> float:
    try: return float(v)
    except (TypeError, ValueError): return 0.0


def build_scorecard(*, prospective: Dict[str, Any], exit_replay: Dict[str, Any], shadow_paper: Dict[str, Any]) -> Dict[str, Any]:
    marker = prospective.get("marker") if isinstance(prospective, dict) else None
    challengers = prospective.get("challengers") if isinstance(prospective, dict) else {}
    challengers = challengers if isinstance(challengers, dict) else {}
    forward: Dict[str, Any] = {}
    research_candidates = []
    for name, row in challengers.items():
        row = row if isinstance(row, dict) else {}
        m = row.get("metrics") if isinstance(row.get("metrics"), dict) else {}
        u = row.get("uncertainty") if isinstance(row.get("uncertainty"), dict) else {}
        closed = int(row.get("closed") or 0)
        expectancy = _f(m.get("expectancy"))
        ci = u.get("expectancy_ci95") or u.get("expectancy_ci")
        ci_low = _f(ci[0]) if isinstance(ci, (list, tuple)) and len(ci) >= 2 else None
        sample_ok = closed >= MIN_FORWARD_CLOSED
        expectancy_ok = expectancy > 0
        uncertainty_ok = ci_low is not None and ci_low > 0
        evidence_ok = bool(sample_ok and expectancy_ok and uncertainty_ok)
        forward[name] = {"opened":int(row.get("opened") or 0),"closed":closed,"open":int(row.get("open") or 0),"expectancy":expectancy,"expectancy_ci95":ci,"sample_sufficient":sample_ok,"positive_expectancy":expectancy_ok,"uncertainty_supports_positive_edge":uncertainty_ok,"research_evidence_ready":evidence_ok}
        if evidence_ok: research_candidates.append(name)

    closed_with_open = int(exit_replay.get("closed_with_open") or 0) if isinstance(exit_replay, dict) else 0
    candidates = exit_replay.get("candidates") if isinstance(exit_replay, dict) else {}
    candidates = candidates if isinstance(candidates, dict) else {}
    max_path = max([int((v or {}).get("path_eligible") or 0) for v in candidates.values()] or [0])
    replay_coverage = max_path / closed_with_open if closed_with_open else 0.0
    replay_ok = bool(closed_with_open > 0 and replay_coverage >= MIN_REPLAY_COVERAGE)

    nominations = shadow_paper.get("prospective_nominations") if isinstance(shadow_paper, dict) else []
    nominations = nominations if isinstance(nominations, list) else []
    pooled = bool(shadow_paper.get("populations_pooled")) if isinstance(shadow_paper, dict) else False

    initialized = bool(isinstance(marker, dict) and marker.get("started_at"))
    return {
        "ok": True,
        "title": "ATLAS V6 RESEARCH READINESS SCORECARD",
        "mode": "FAIL_CLOSED_RESEARCH_ONLY",
        "engineering_health": {"scorecard_service": "AVAILABLE", "prospective_initialized": initialized},
        "forward_evidence": forward,
        "research_candidates": research_candidates,
        "exit_replay": {"closed_with_open":closed_with_open,"max_path_eligible":max_path,"path_coverage":round(replay_coverage,6),"minimum_path_coverage":MIN_REPLAY_COVERAGE,"coverage_sufficient":replay_ok,"uses_final_mfe_to_trigger":bool(exit_replay.get("uses_final_mfe_to_trigger",True))},
        "shadow_paper": {"populations_pooled":pooled,"prospective_nomination_count":len(nominations),"prospective_nominations":nominations},
        "research_evidence_ready": bool(initialized and research_candidates and replay_ok and not pooled),
        "trading_readiness": "NOT_READY",
        "live_capital_allowed": False,
        "automatic_promotion": False,
        "production_strategy_modified": False,
        "automatic_real_money_execution": False,
        "note": "Research evidence readiness is not trading/live-capital readiness. Explicit review and later promotion policy are still required."
    }


def readiness_scorecard() -> Dict[str, Any]:
    from app.services.challenger_prospective import prospective_report
    from app.services.challenger_exit_replay import exit_replay_report
    from app.services.shadow_paper_interactions import interaction_report
    return build_scorecard(prospective=prospective_report(), exit_replay=exit_replay_report(), shadow_paper=interaction_report())
