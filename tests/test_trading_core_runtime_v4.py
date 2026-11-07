from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.trading_core.models import PaperExecutionConfig
from app.trading_core.runtime import LegacySignalAdapter, V4ShadowRuntime


def _signal(side="LONG"):
    return {
        "trade_id": "abc123",
        "symbol": "ETH",
        "side": side,
        "signal_price": 100.0,
        "stop_price": 99.0 if side == "LONG" else 101.0,
        "target_r": 1.8,
        "risk_usd": 1.0,
        "signal_timestamp": "2026-09-10T00:00:00+00:00",
    }


def test_legacy_adapter_builds_immutable_intent():
    intent = LegacySignalAdapter().to_intent(_signal())
    assert intent.trade_id == "abc123"
    assert intent.symbol == "ETH"
    assert intent.side.value == "LONG"
    assert intent.target_r == 1.8
    assert intent.strategy_version == "atlas-v4-shadow-adapter-1"


def test_shadow_runtime_dedupes_same_open_trade_id():
    rt = V4ShadowRuntime()
    t0 = datetime(2026, 9, 10, tzinfo=timezone.utc)
    p1 = rt.open_from_legacy(_signal(), 100.0, t0)
    p2 = rt.open_from_legacy(_signal(), 100.5, t0 + timedelta(seconds=1))
    assert p1 is p2
    assert len(rt.positions) == 1


def test_shadow_runtime_long_closes_deterministically():
    rt = V4ShadowRuntime(PaperExecutionConfig(entry_slippage_bps=0, exit_slippage_bps=0, fee_bps_per_side=0))
    t0 = datetime(2026, 9, 10, tzinfo=timezone.utc)
    p = rt.open_from_legacy(_signal(), 100.0, t0)
    assert p.is_open
    step = rt.mark("abc123", p.target_price, t0 + timedelta(seconds=5))
    assert not step.position.is_open
    assert step.event == "TARGET"
    assert round(step.position.net_r, 6) == 1.8


def test_shadow_runtime_short_closes_deterministically():
    rt = V4ShadowRuntime(PaperExecutionConfig(entry_slippage_bps=0, exit_slippage_bps=0, fee_bps_per_side=0))
    t0 = datetime(2026, 9, 10, tzinfo=timezone.utc)
    p = rt.open_from_legacy(_signal("SHORT"), 100.0, t0)
    step = rt.mark("abc123", p.target_price, t0 + timedelta(seconds=5))
    assert step.event == "TARGET"
    assert round(step.position.net_r, 6) == 1.8


def test_shadow_runtime_rejects_unknown_trade():
    rt = V4ShadowRuntime()
    try:
        rt.mark("missing", 100.0, datetime(2026, 9, 10, tzinfo=timezone.utc))
    except KeyError:
        pass
    else:
        raise AssertionError("expected unknown trade to raise KeyError")
