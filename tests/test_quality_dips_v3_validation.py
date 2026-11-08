from app.investment.quality_dips_v3_validation import validate_v3_pit_rows


def test_v3_pit_windows_and_states():
    rows = [
        {"symbol":"MSFT","timestamp":"2024-02-01T00:00:00","patient_state":"WATCH"},
        {"symbol":"MSFT","timestamp":"2025-06-01T00:00:00","patient_state":"ACCUMULATION"},
        {"symbol":"MSFT","timestamp":"2025-07-10T00:00:00","patient_state":"DEEP_VALUE"},
        {"symbol":"NVDA","timestamp":"2025-08-01T00:00:00","patient_state":"GENERATIONAL"},
    ]
    out = validate_v3_pit_rows(rows)
    assert out["valid"] is True
    assert out["windows"]["DEVELOPMENT"] == 2
    assert out["windows"]["HOLDOUT"] == 2
    assert out["state_counts"]["HOLDOUT"]["GENERATIONAL"] == 1
    assert out["lookahead_allowed"] is False
    assert out["holdout_retuning_allowed"] is False
    assert out["automatic_real_money_execution"] is False


def test_v3_pit_rejects_backward_timestamp():
    rows = [
        {"symbol":"MSFT","timestamp":"2025-02-02T00:00:00","patient_state":"WATCH"},
        {"symbol":"MSFT","timestamp":"2025-02-01T00:00:00","patient_state":"WATCH"},
    ]
    out = validate_v3_pit_rows(rows)
    assert out["valid"] is False
    assert out["violations"]


def test_v3_pit_rejects_unknown_state():
    out = validate_v3_pit_rows([
        {"symbol":"MSFT","timestamp":"2025-07-10T00:00:00","patient_state":"MAGIC"}
    ])
    assert out["valid"] is False
