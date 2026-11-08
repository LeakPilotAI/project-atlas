"""Hyperliquid published fundingHistory event time is not always hour-aligned.

Offline-only tests: keep genuine event precision, canonical UTC hour, and
fail-closed 30-second financial-recovery cutoff. No provider access.
"""
from copy import deepcopy

import pytest

from app.adapters.hyperliquid import (
    MAX_FUNDING_PUBLICATION_LAG_MS,
    _paper_funding_observation,
)


HOUR = 1683849600000  # Official provider example uses HOUR + 76 milliseconds.


def rate(at=HOUR + 76):
    return {"coin": "BTC", "fundingRate": "-0.00022196",
            "premium": "-0.00052196", "time": at}


def parse(rows, *, start=HOUR, end=HOUR + 3600000, observed=HOUR + 200):
    return _paper_funding_observation(
        "BTC", rows, start, end, observed - 5, observed
    )


def test_official_provider_documented_76ms_lag_passes_with_both_timestamps():
    original = rate()
    cloned = deepcopy(original)
    out = parse([original])
    assert original == cloned
    assert out["schema"] == "ATLAS_HYPERLIQUID_FUNDING_HISTORY_V1"
    assert out["rate_history_complete"] is True
    assert out["settlement_evidence_complete"] is False
    assert out["financial_execution_authorized"] is False
    assert out["startup_authorized"] is False
    assert out["records"] == [{
        "settlement_at_ms": HOUR,
        "provider_event_at_ms": HOUR + 76,
        "publication_delay_ms": 76,
        "hourly_rate": "-0.00022196",
        "premium": "-0.00052196",
        "settlement_oracle": None,
    }]


def test_exact_boundary_retains_backwards_compatible_settlement_cut():
    out = parse([rate(HOUR)], observed=HOUR + 1)
    assert out["records"][0]["settlement_at_ms"] == HOUR
    assert out["records"][0]["provider_event_at_ms"] == HOUR
    assert out["records"][0]["publication_delay_ms"] == 0


def test_multiple_consecutive_utc_hours_keep_distinct_event_and_accounting_times():
    rows = [rate(HOUR + 76), rate(HOUR + 3600000 + 112)]
    out = parse(rows, end=HOUR + 7200000, observed=HOUR + 3600000 + 200)
    assert [r["settlement_at_ms"] for r in out["records"]] == [
        HOUR, HOUR + 3600000,
    ]
    assert [r["publication_delay_ms"] for r in out["records"]] == [76, 112]


@pytest.mark.parametrize("offset", [30000, 30001, 1433000, 3600000, -1, -30000])
def test_late_wrong_hour_or_pre_boundary_provider_event_never_backdated(offset):
    assert MAX_FUNDING_PUBLICATION_LAG_MS == 30000
    target = HOUR + offset
    if offset == MAX_FUNDING_PUBLICATION_LAG_MS:
        assert parse([rate(target)], observed=target + 1)["records"][0]["publication_delay_ms"] == offset
    else:
        with pytest.raises(ValueError):
            parse([rate(target)], observed=max(HOUR + 200, target + 1))


def test_future_publication_refused_even_if_in_accepted_hour_window():
    with pytest.raises(ValueError):
        parse([rate(HOUR + 76)], observed=HOUR + 75)


@pytest.mark.parametrize("fault", ["missing", "duplicate", "out-of-order", "wrong-coin",
                                   "nonfinite", "unbounded", "wrong-schema"])
def test_corrupt_ambiguous_or_missing_hourly_funding_remains_refused(fault):
    rows = [rate(HOUR + 76), rate(HOUR + 3600000 + 112)]
    if fault == "missing":
        rows.pop()
    elif fault == "duplicate":
        rows[1]["time"] = HOUR + 77
    elif fault == "out-of-order":
        rows.reverse()
    elif fault == "wrong-coin":
        rows[1]["coin"] = "ETH"
    elif fault == "nonfinite":
        rows[1]["fundingRate"] = "NaN"
    elif fault == "unbounded":
        rows[0]["fundingRate"] = "0.05"
    elif fault == "wrong-schema":
        rows[0]["settlementOracle"] = "123"
    with pytest.raises(ValueError):
        parse(rows, end=HOUR + 7200000, observed=HOUR + 3600000 + 200)
