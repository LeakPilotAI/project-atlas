from app.services.e27_preregistration import e27_preregistration


def test_e27_freezes_baseline_and_does_not_define_retrospective_thresholds():
    report=e27_preregistration()
    assert report["baseline"]["frozen"] is True
    assert report["baseline"]["side"] == "LONG"
    assert report["baseline"]["short_unchanged"] is True
    assert all(h["candidate_thresholds"] is None for h in report["hypotheses"].values())
    assert all(h["retrospective_cutoffs_promoted"] is False for h in report["hypotheses"].values())
    assert report["challenger_definition_gate"]["challenger_created"] is False
    assert report["challenger_definition_gate"]["candidate_thresholds_defined"] is False


def test_e27_preregisters_forward_acceptance_before_challenger():
    gate=e27_preregistration()["prospective_acceptance_gate"]
    assert gate["minimum_closed_trades_per_arm"] == 60
    assert gate["minimum_distinct_symbols_per_arm"] == 8
    assert gate["minimum_forward_calendar_days"] == 14
    assert gate["challenger_expectancy_after_recorded_costs_must_be_positive"] is True
    assert gate["challenger_expectancy_must_exceed_concurrent_baseline"] is True
    assert gate["challenger_max_drawdown_must_not_be_worse_than_baseline"] is True
    assert gate["all_conditions_required"] is True


def test_e27_selection_cannot_use_post_entry_outcomes():
    report=e27_preregistration()
    assert report["hypotheses"]["H1_selection_quality"]["post_entry_features_for_selection"] == []
    assert report["evidence_integrity"]["pre_entry_fields_only_for_selection"] is True
    assert report["evidence_integrity"]["post_entry_fields_selection_authority"] is False
    assert report["evidence_integrity"]["legacy_execution_models_poolable_with_current"] is False


def test_e27_has_no_strategy_or_live_capital_authority():
    report=e27_preregistration()
    assert report["production_strategy_modified"] is False
    assert report["strategy_action"] is None
    assert report["threshold_change"] is None
    assert report["sizing_change"] is None
    assert report["execution_change"] is None
    assert report["automatic_promotion"] is False
    assert report["promotion_allowed"] is False
    assert report["live_capital_allowed"] is False
    assert report["automatic_real_money_execution"] is False
