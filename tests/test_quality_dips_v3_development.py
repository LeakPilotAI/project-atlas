from app.investment.quality_dips_v3_development import build_development_report


def test_development_report_freezes_parameters():
    rows = [
        {"symbol":"MSFT","timestamp":"2024-02-01T00:00:00","patient_state":"WATCH"},
        {"symbol":"MSFT","timestamp":"2025-05-01T00:00:00","patient_state":"ACCUMULATION"},
        {"symbol":"MSFT","timestamp":"2025-08-01T00:00:00","patient_state":"DEEP_VALUE"},
    ]
    out = build_development_report(rows)
    assert out["decision"] == "DEVELOPMENT_VALIDATION_READY"
    assert out["observations"] == 2
    assert out["parameter_freeze"]["frozen_after_development"] is True
    assert out["parameter_freeze"]["holdout_retuning_allowed"] is False
    assert out["automatic_real_money_execution"] is False


def test_development_report_blocks_on_invalid_pit_order():
    rows = [
        {"symbol":"MSFT","timestamp":"2025-05-02T00:00:00","patient_state":"WATCH"},
        {"symbol":"MSFT","timestamp":"2025-05-01T00:00:00","patient_state":"WATCH"},
    ]
    assert build_development_report(rows)["decision"] == "BLOCKED"
