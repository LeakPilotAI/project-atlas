from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.trading_core.models import MarketQuote, PaperExecutionConfig, Side, TradeIntent
from app.trading_core.replay import compare_many, compare_to_legacy, replay_summary


def _intent():
    return TradeIntent(
        trade_id="t1",
        symbol="BTC",
        side=Side.LONG,
        signal_price=100.0,
        stop_price=99.0,
        target_r=1.8,
        risk_usd=1.0,
        signal_timestamp=datetime(2026, 9, 10, tzinfo=timezone.utc),
        strategy_version="test-v4",
    )


def _quotes():
    t0 = datetime(2026, 9, 10, tzinfo=timezone.utc)
    return [
        MarketQuote("BTC", 100.0, t0),
        MarketQuote("BTC", 100.5, t0 + timedelta(seconds=1)),
        MarketQuote("BTC", 101.8, t0 + timedelta(seconds=2)),
    ]


def test_replay_summary_is_json_friendly_and_closed():
    out = replay_summary(
        _intent(),
        _quotes(),
        PaperExecutionConfig(entry_slippage_bps=0, exit_slippage_bps=0, fee_bps_per_side=0),
    )
    assert out["trade_id"] == "t1"
    assert out["status"] == "CLOSED"
    assert out["exit_reason"] == "TARGET"
    assert out["net_r"] == 1.8
    assert out["events"] == ["OPEN", "MARK", "TARGET"]


def test_compare_to_legacy_detects_match():
    v4 = {"trade_id": "t1", "symbol": "BTC", "net_r": 1.8, "exit_reason": "TARGET"}
    legacy = {"trade_id": "t1", "symbol": "BTC", "net_pnl_r": 1.8, "exit_reason": "TARGET"}
    row = compare_to_legacy(v4, legacy)
    assert row["status"] == "MATCH"
    assert row["delta_r"] == 0.0
    assert row["exit_reason_match"] is True


def test_compare_to_legacy_detects_divergence():
    v4 = {"trade_id": "t1", "symbol": "BTC", "net_r": 1.5, "exit_reason": "LOCKED_STOP"}
    legacy = {"trade_id": "t1", "symbol": "BTC", "R_multiple": -1.0, "result": "STOP"}
    row = compare_to_legacy(v4, legacy)
    assert row["status"] == "DIVERGED"
    assert row["delta_r"] == 2.5


def test_compare_many_aggregates_without_hiding_unknown_legacy_r():
    pairs = [
        (
            {"trade_id": "a", "symbol": "BTC", "net_r": 1.0, "exit_reason": "TARGET"},
            {"trade_id": "a", "symbol": "BTC", "net_pnl_r": 1.0, "exit_reason": "TARGET"},
        ),
        (
            {"trade_id": "b", "symbol": "ETH", "net_r": -1.0, "exit_reason": "STOP"},
            {"trade_id": "b", "symbol": "ETH", "net_pnl_r": None, "exit_reason": "STOP"},
        ),
    ]
    out = compare_many(pairs)
    assert out["n"] == 2
    assert out["comparable_n"] == 1
    assert out["matches"] == 1
    assert out["diverged"] == 1
    assert out["mean_delta_r"] == 0.0
