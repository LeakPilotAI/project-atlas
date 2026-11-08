from app.investment.quality_dips_v2_validation import (
    conservative_upside_pct,
    evaluate_hurdle_observations,
    evaluate_position_states,
    hurdle_flags,
    validate_pit_order,
)


def test_conservative_upside_and_hurdles():
    assert conservative_upside_pct(100, 129) == 29.0
    flags = hurdle_flags(100, 150)
    assert flags == {"gte_29": True, "gte_40": True, "gte_50": True}


def test_invalid_values_do_not_create_hurdles():
    assert conservative_upside_pct(0, 150) is None
    assert hurdle_flags(None, 150) == {"gte_29": False, "gte_40": False, "gte_50": False}


def test_pit_order_passes_for_monotonic_symbol_history():
    rows = [
        {"symbol": "MSFT", "timestamp": "2026-01-01T00:00:00Z"},
        {"symbol": "MSFT", "timestamp": "2026-01-02T00:00:00Z"},
        {"symbol": "NVDA", "timestamp": "2026-01-01T00:00:00Z"},
    ]
    result = validate_pit_order(rows)
    assert result["valid"] is True
    assert result["lookahead_allowed"] is False
    assert result["same_window_retuning_allowed"] is False


def test_pit_order_fails_when_timestamp_moves_backward():
    rows = [
        {"symbol": "MSFT", "timestamp": "2026-01-02T00:00:00Z"},
        {"symbol": "MSFT", "timestamp": "2026-01-01T00:00:00Z"},
    ]
    result = validate_pit_order(rows)
    assert result["valid"] is False
    assert result["violations"]


def test_hurdle_summary_is_screening_frequency_only():
    rows = [
        {"symbol": "A", "timestamp": "2026-01-01T00:00:00Z", "price": 100, "conservative_value": 129},
        {"symbol": "A", "timestamp": "2026-01-02T00:00:00Z", "price": 100, "conservative_value": 140},
        {"symbol": "A", "timestamp": "2026-01-03T00:00:00Z", "price": 100, "conservative_value": 150},
    ]
    result = evaluate_hurdle_observations(rows)
    assert result["pit_order_valid"] is True
    assert result["hurdle_counts"] == {"gte_29": 3, "gte_40": 2, "gte_50": 1}
    assert "not realized return" in result["interpretation"]
    assert result["automatic_real_money_execution"] is False


def test_position_state_counts_and_entry_time_validation():
    rows = [
        {
            "symbol": "A",
            "timestamp": "2026-01-02T00:00:00Z",
            "entry_timestamp": "2026-01-01T00:00:00Z",
            "position_state": "HOLD",
        },
        {
            "symbol": "A",
            "timestamp": "2026-01-03T00:00:00Z",
            "entry_timestamp": "2026-01-01T00:00:00Z",
            "position_state": "HOLD_WATCH",
        },
    ]
    result = evaluate_position_states(rows)
    assert result["pit_order_valid"] is True
    assert result["entry_time_valid"] is True
    assert result["state_counts"]["HOLD"] == 1
    assert result["state_counts"]["HOLD_WATCH"] == 1
    assert result["live_capital_allowed"] is False


def test_position_state_flags_pre_entry_observation_as_invalid():
    rows = [
        {
            "symbol": "A",
            "timestamp": "2026-01-01T00:00:00Z",
            "entry_timestamp": "2026-01-02T00:00:00Z",
            "position_state": "HOLD",
        },
    ]
    result = evaluate_position_states(rows)
    assert result["entry_time_valid"] is False
    assert result["entry_time_violations"]


def test_unknown_position_states_are_counted_not_invented():
    rows = [
        {"symbol": "A", "timestamp": "2026-01-01T00:00:00Z", "position_state": "MAGIC"},
    ]
    result = evaluate_position_states(rows)
    assert result["unknown_state_count"] == 1
