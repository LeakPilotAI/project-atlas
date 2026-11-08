"""Execution 27: pre-registered Perps Setup V2 prospective hypothesis gate.

This registry freezes research questions and acceptance criteria before any
challenger is built. It deliberately contains no retrospectively optimized
entry thresholds and has no strategy/execution authority.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict

REGISTRY_VERSION = "perp-setup-v2-e27-prereg-v1"
BASELINE_STRATEGY = "perp_setup_auto_v2_resting_limit"
BASELINE_EXECUTION_MODEL = "paper-exec-v2-conservative-gap-target+adaptive-exit-v1"

MIN_CLOSED_PER_ARM = 60
MIN_DISTINCT_SYMBOLS = 8
MIN_FORWARD_DAYS = 14
MAX_SINGLE_SYMBOL_SHARE = 0.30
MAX_EXTREME_LOSS_R = 3.0

_COMMON_METRICS = [
    "net_pnl_r",
    "expectancy_r_after_recorded_costs",
    "win_rate",
    "max_drawdown_r",
    "worst_trade_r",
    "mfe_r",
    "mae_r",
    "setup_stop_rate",
    "stop_overshoot_r",
    "execution_slippage_bps",
]

HYPOTHESES: Dict[str, Dict[str, Any]] = {
    "H1_selection_quality": {
        "question": "Can pre-entry selection features reduce weak LONG entries without relying on post-entry path information?",
        "feature_families": ["signal_score", "momentum_pct", "trend_pct", "volatility_pct"],
        "post_entry_features_for_selection": [],
        "candidate_thresholds": None,
        "retrospective_cutoffs_promoted": False,
        "falsifier": "Forward challenger fails to improve expectancy/tail risk versus concurrent frozen baseline or improvement is not stable across symbols/time.",
    },
    "H2_early_adverse_path": {
        "question": "Are current adaptive LONG losses primarily explained by entry selection leading to early adverse movement rather than adaptive protective exits?",
        "selection_feature_families": ["signal_score", "momentum_pct", "trend_pct", "volatility_pct"],
        "outcome_diagnostics_only": ["mfe_r", "mae_r", "exit_reason", "stop_overshoot_r"],
        "candidate_thresholds": None,
        "retrospective_cutoffs_promoted": False,
        "falsifier": "Forward selected entries do not reduce setup-stop incidence/MAE while preserving or improving expectancy versus baseline.",
    },
    "H3_execution_tail_independence": {
        "question": "Does any selection challenger remain beneficial after execution-quality and stop-tail outcomes are measured separately?",
        "selection_feature_families": ["signal_score", "momentum_pct", "trend_pct", "volatility_pct"],
        "execution_diagnostics_only": ["paper_execution_model_version", "slippage_bps", "stop_overshoot_r"],
        "candidate_thresholds": None,
        "retrospective_cutoffs_promoted": False,
        "falsifier": "Apparent improvement disappears when execution quality/tail events are separated, or depends on incompatible legacy execution evidence.",
    },
}


def e27_preregistration() -> Dict[str, Any]:
    return {
        "ok": True,
        "title": "ATLAS E27 PERPS SETUP V2 PROSPECTIVE HYPOTHESIS GATE",
        "registry_version": REGISTRY_VERSION,
        "baseline": {
            "strategy": BASELINE_STRATEGY,
            "execution_model": BASELINE_EXECUTION_MODEL,
            "side": "LONG",
            "frozen": True,
            "short_unchanged": True,
        },
        "hypotheses": deepcopy(HYPOTHESES),
        "prospective_acceptance_gate": {
            "minimum_closed_trades_per_arm": MIN_CLOSED_PER_ARM,
            "minimum_distinct_symbols_per_arm": MIN_DISTINCT_SYMBOLS,
            "minimum_forward_calendar_days": MIN_FORWARD_DAYS,
            "maximum_single_symbol_share": MAX_SINGLE_SYMBOL_SHARE,
            "challenger_expectancy_after_recorded_costs_must_be_positive": True,
            "challenger_expectancy_must_exceed_concurrent_baseline": True,
            "challenger_max_drawdown_must_not_be_worse_than_baseline": True,
            "challenger_worst_trade_must_be_greater_than_or_equal_r": -MAX_EXTREME_LOSS_R,
            "setup_stop_rate_and_stop_tail_must_not_materially_worsen": True,
            "execution_quality_must_be_reported_separately": True,
            "symbol_and_time_diversity_required": True,
            "all_metrics": list(_COMMON_METRICS),
            "all_conditions_required": True,
        },
        "challenger_definition_gate": {
            "challenger_created": False,
            "candidate_thresholds_defined": False,
            "retrospective_optimization_allowed": False,
            "requires_separate_versioned_execution": True,
            "requires_concurrent_frozen_baseline": True,
            "reason": "E27 pre-registers hypotheses and acceptance criteria; it does not choose cutoffs from E26 retrospective slices.",
        },
        "evidence_integrity": {
            "forward_only_after_challenger_freeze": True,
            "membership_frozen_at_open": True,
            "pre_entry_fields_only_for_selection": True,
            "post_entry_fields_selection_authority": False,
            "unknown_metadata_backfilled": False,
            "historical_evidence_rewritten": False,
            "legacy_execution_models_poolable_with_current": False,
            "tiny_positive_buckets_promotable": False,
        },
        "production_strategy_modified": False,
        "strategy_action": None,
        "threshold_change": None,
        "sizing_change": None,
        "execution_change": None,
        "automatic_promotion": False,
        "promotion_allowed": False,
        "execution": "READ_ONLY_PAPER_RESEARCH",
        "live_capital_allowed": False,
        "automatic_real_money_execution": False,
    }
