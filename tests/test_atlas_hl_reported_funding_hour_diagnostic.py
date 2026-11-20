"""Original Hyperliquid reported-hour label clarification, no finance."""
import copy

import pytest

from scripts.observation_runtime.atlas_hl_reported_funding_hour_diagnostic import (
    HOUR_MS, OBSERVATION_ONLY, classify_reported_hl_hour_label,
)

NOW_HOUR = 1_800_000_000_000 // HOUR_MS * HOUR_MS


def sample(**changes):
    source = {
        "coin": "BTC",
        "reported_next_funding_time_ms": NOW_HOUR,
        "observed_utc_ms": NOW_HOUR + 17 * 60_000 + 500,
        "funding_interval_hours": 1,
        "funding_rate": "0.0000125",
    }
    source.update(changes)
    return source


@pytest.mark.parametrize("coin", ("BTC", "ETH", "SOL"))
@pytest.mark.parametrize("elapsed", (0, 1000, 17*60000, 3599999))
def test_current_hour_label_is_pure_observation_not_a_settlement(coin, elapsed):
    original = sample(coin=coin, observed_utc_ms=NOW_HOUR + elapsed)
    pristine = copy.deepcopy(original)
    result = classify_reported_hl_hour_label(**original)
    assert original == pristine
    assert result["status"] == OBSERVATION_ONLY
    assert result["field_lag_ms"] == elapsed
    assert result["received_raw_time_ms"] == NOW_HOUR
    assert result["inferred_future_next_funding_ms"] is None
    assert result["declares_provider_semantics_authoritative"] is False
    assert result["relabels_field_as_verified_next_settlement"] is False
    for name in (
        "historical_settlement_oracle_verified", "financial_position_flat_verified",
        "actual_account_fee_tier_verified", "financial_source_rights_accepted",
        "paper_start_authorized", "live_money_authorized",
    ):
        assert result[name] is False


@pytest.mark.parametrize("reported", (
    NOW_HOUR - HOUR_MS, NOW_HOUR + HOUR_MS,
    NOW_HOUR - 1, NOW_HOUR + 1, NOW_HOUR + 17 * 60000,
))
def test_no_other_hour_or_fabricated_future_admitted(reported):
    with pytest.raises(ValueError, match="NOT_CURRENT_HOUR_PATTERN"):
        classify_reported_hl_hour_label(**sample(
            reported_next_funding_time_ms=reported))


@pytest.mark.parametrize("invalid", (
    {"coin": "AVGO"}, {"coin": True},
    {"reported_next_funding_time_ms": True},
    {"reported_next_funding_time_ms": "hour"},
    {"reported_next_funding_time_ms": 0},
    {"observed_utc_ms": False},
    {"observed_utc_ms": 10},
    {"funding_interval_hours": None},
    {"funding_interval_hours": 0},
    {"funding_interval_hours": True},
    {"funding_interval_hours": 1.0},
))
def test_malformed_observation_never_relabels_source(invalid):
    with pytest.raises(ValueError):
        classify_reported_hl_hour_label(**sample(**invalid))


@pytest.mark.parametrize("invalid_rate", (
    "NaN", "Infinity", "-Infinity", "0.05", "-0.05", "", "not_decimal",
    0.0001, None, True,
))
def test_invalid_rates_refused_without_ever_granting_trading(invalid_rate):
    with pytest.raises(ValueError, match="RATE_REFUSED"):
        classify_reported_hl_hour_label(**sample(funding_rate=invalid_rate))


def test_old_996ms_short_sample_cannot_be_promoted_by_funding_hour_classifier():
    # The helper does NOT inspect or grant two-forecast sample spacing.
    data = classify_reported_hl_hour_label(**sample())
    assert data["status"] == OBSERVATION_ONLY
    assert data["paper_start_authorized"] is False
    assert data["inferred_future_next_funding_ms"] is None
    assert "minimum_forecast_spacing" not in data
