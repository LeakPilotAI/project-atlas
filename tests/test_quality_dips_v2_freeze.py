from app.investment.quality_dips_v2_freeze import (
    DEFAULT_V2_FREEZE,
    DevelopmentPolicyFreeze,
    audit_untouched_holdout,
    classify_partition,
    default_manifest,
    freeze_manifest,
)


def test_default_manifest_freezes_policy_and_no_live():
    manifest = default_manifest()
    assert manifest["status"] == "DEVELOPMENT_POLICY_FROZEN"
    assert manifest["holdout_untouched"] is True
    assert manifest["same_window_retuning_allowed"] is False
    assert manifest["lookahead_allowed"] is False
    assert manifest["execution"] == "MANUAL_ONLY"
    assert manifest["live_capital_allowed"] is False
    assert manifest["automatic_real_money_execution"] is False
    assert len(manifest["policy_sha256"]) == 64


def test_default_freeze_locks_quality_dips_v2_hurdles():
    manifest = default_manifest()
    policy = manifest["policy"]
    assert policy["min_upside_hurdle_pct"] == 29.0
    assert policy["deep_value_hurdle_pct"] == 40.0
    assert policy["generational_hurdle_pct"] == 50.0
    assert [policy[f"l{i}_hurdle_pct"] for i in range(1, 5)] == [29.0, 35.0, 40.0, 50.0]


def test_freeze_manifest_is_deterministic():
    first = freeze_manifest(DEFAULT_V2_FREEZE)
    second = freeze_manifest(DEFAULT_V2_FREEZE)
    assert first["policy_sha256"] == second["policy_sha256"]


def test_freeze_rejects_lookahead_or_same_window_retuning():
    bad = DevelopmentPolicyFreeze(
        cycle="X",
        frozen_at="2026-09-17",
        development_start="2024-01-01",
        development_end="2025-06-30",
        holdout_start="2025-07-01",
        holdout_end="2025-12-31",
        policy_version="x",
        min_upside_hurdle_pct=29,
        deep_value_hurdle_pct=40,
        generational_hurdle_pct=50,
        l1_hurdle_pct=29,
        l2_hurdle_pct=35,
        l3_hurdle_pct=40,
        l4_hurdle_pct=50,
        lookahead_allowed=True,
    )
    try:
        freeze_manifest(bad)
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_partition_classification_respects_frozen_boundaries():
    manifest = default_manifest()
    assert classify_partition("2025-06-30T12:00:00", manifest) == "DEVELOPMENT"
    assert classify_partition("2025-07-01T12:00:00", manifest) == "HOLDOUT"
    assert classify_partition("2026-01-01T00:00:00", manifest) == "OUT_OF_SCOPE"


def test_untouched_holdout_audit_green_for_clean_split():
    manifest = default_manifest()
    result = audit_untouched_holdout(
        [{"timestamp": "2025-06-01T00:00:00"}],
        [{"timestamp": "2025-08-01T00:00:00"}],
        manifest,
    )
    assert result["status"] == "HOLDOUT_BOUNDARY_GREEN"
    assert result["holdout_untouched"] is True
    assert result["violations"] == []


def test_untouched_holdout_audit_blocks_cross_partition_rows():
    manifest = default_manifest()
    result = audit_untouched_holdout(
        [{"timestamp": "2025-08-01T00:00:00"}],
        [{"timestamp": "2025-06-01T00:00:00"}],
        manifest,
    )
    assert result["status"] == "HOLDOUT_BOUNDARY_BLOCKED"
    assert result["holdout_untouched"] is False
    assert len(result["violations"]) == 2
