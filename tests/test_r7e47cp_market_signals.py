from datetime import datetime, timezone

import pytest

from scripts.observation_runtime.r7e47cp_market_signals import (
    analyze_market,
)
from scripts.observation_runtime.r7e47cm_equities_snapshot import (
    SnapshotRefused,
)


def candle(iso, price, volume):
    return {
        "timestamp": datetime.fromisoformat(iso),
        "Close": price,
        "Volume": volume,
    }


def test_premarket_gap_and_volume():
    now = datetime(2026, 10, 19, 12, 2, tzinfo=timezone.utc)

    result = analyze_market(
        "AAPL",
        [
            candle("2026-10-19T07:59:00-04:00", 102, 1000),
            candle("2026-10-19T08:01:00-04:00", 103, 2000),
        ],
        100,
        now=now,
    )

    assert result["session"] == "PRE_MARKET"
    assert result["premarket_gap_percent"] == 3.0
    assert result["premarket_volume"] == 3000
    assert result["regular_volume"] == 0


def test_regular_session_separates_volume():
    now = datetime(2026, 10, 19, 13, 32, tzinfo=timezone.utc)

    result = analyze_market(
        "MSFT",
        [
            candle("2026-10-19T08:00:00-04:00", 102, 1000),
            candle("2026-10-19T09:31:00-04:00", 105, 3000),
        ],
        100,
        now=now,
    )

    assert result["session"] == "REGULAR"
    assert result["premarket_volume"] == 1000
    assert result["regular_volume"] == 3000
    assert result["premarket_gap_percent"] == 2.0
    assert result["change_from_previous_close_percent"] == 5.0


def test_missing_relative_volume_baseline_explicit():
    now = datetime(2026, 10, 19, 13, 32, tzinfo=timezone.utc)

    result = analyze_market(
        "AAPL",
        [candle("2026-10-19T09:31:00-04:00", 101, 1000)],
        100,
        now=now,
    )

    assert result["relative_volume"] is None
    assert result["relative_volume_status"] == "BASELINE_REQUIRED"


def test_invalid_previous_close_refused():
    now = datetime(2026, 10, 19, 13, 32, tzinfo=timezone.utc)

    with pytest.raises(SnapshotRefused):
        analyze_market(
            "AAPL",
            [candle("2026-10-19T09:31:00-04:00", 101, 1000)],
            0,
            now=now,
        )
