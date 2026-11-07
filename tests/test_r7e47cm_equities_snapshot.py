from datetime import datetime, timedelta, timezone

import pytest

from scripts.observation_runtime.r7e47cm_equities_snapshot import (
    SnapshotRefused,
    build_snapshot,
)


def candle(timestamp, price=100, volume=1200):
    return {
        "timestamp": timestamp,
        "Close": price,
        "Volume": volume,
    }


def test_premarket_snapshot():
    now = datetime(2026, 10, 19, 12, 1, tzinfo=timezone.utc)
    result = build_snapshot(
        "aapl",
        [candle(now - timedelta(seconds=60))],
        now=now,
    )

    assert result["session"] == "PRE_MARKET"
    assert result["price"] == 100
    assert result["freshness"] == "FRESH"


def test_regular_market_snapshot():
    now = datetime(2026, 10, 19, 14, 1, tzinfo=timezone.utc)
    result = build_snapshot(
        "MSFT",
        [candle(now - timedelta(seconds=60))],
        now=now,
    )

    assert result["session"] == "REGULAR"


def test_stale_candle_refused():
    now = datetime(2026, 10, 19, 14, 0, tzinfo=timezone.utc)

    with pytest.raises(SnapshotRefused):
        build_snapshot(
            "AAPL",
            [candle(now - timedelta(minutes=10))],
            now=now,
        )


def test_future_candle_refused():
    now = datetime(2026, 10, 19, 14, 0, tzinfo=timezone.utc)

    with pytest.raises(SnapshotRefused):
        build_snapshot(
            "AAPL",
            [candle(now + timedelta(minutes=1))],
            now=now,
        )


def test_invalid_price_refused():
    now = datetime(2026, 10, 19, 14, 0, tzinfo=timezone.utc)

    with pytest.raises(SnapshotRefused):
        build_snapshot(
            "AAPL",
            [candle(now, price=-1)],
            now=now,
        )


def test_missing_timestamp_refused():
    now = datetime(2026, 10, 19, 14, 0, tzinfo=timezone.utc)

    with pytest.raises(SnapshotRefused):
        build_snapshot(
            "AAPL",
            [{"Close": 100, "Volume": 200}],
            now=now,
        )


def test_latest_valid_candle_selected():
    now = datetime(2026, 10, 19, 14, 0, tzinfo=timezone.utc)

    result = build_snapshot(
        "AAPL",
        [
            candle(now - timedelta(minutes=2), price=99),
            candle(now - timedelta(minutes=1), price=101),
        ],
        now=now,
    )

    assert result["price"] == 101
