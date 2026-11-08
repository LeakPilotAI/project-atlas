from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.trading_core import (
    ExitReason,
    MarketQuote,
    PaperEngine,
    PaperExecutionConfig,
    PositionStatus,
    Side,
    TradeIntent,
)


T0 = datetime(2026, 9, 10, 12, 0, tzinfo=timezone.utc)


def q(symbol: str, price: float, seconds: int) -> MarketQuote:
    return MarketQuote(symbol=symbol, price=price, timestamp=T0 + timedelta(seconds=seconds))


def intent(side: Side = Side.LONG, *, trade_id: str = "t1") -> TradeIntent:
    if side is Side.LONG:
        stop = 99.0
    else:
        stop = 101.0
    return TradeIntent(
        trade_id=trade_id,
        symbol="BTC",
        side=side,
        signal_price=100.0,
        stop_price=stop,
        target_r=1.8,
        risk_usd=10.0,
        signal_timestamp=T0,
        strategy_version="atlas-v4-test",
    )


def test_same_input_replays_identically():
    engine = PaperEngine(PaperExecutionConfig(entry_slippage_bps=1, exit_slippage_bps=1, fee_bps_per_side=2))
    quotes = [q("BTC", 100, 0), q("BTC", 100.4, 5), q("BTC", 101.9, 10)]
    a = engine.replay(intent(), quotes)
    b = engine.replay(intent(), quotes)
    assert a == b
    assert a[-1].position.status is PositionStatus.CLOSED
    assert a[-1].position.exit_reason is ExitReason.TARGET


def test_long_target_and_fees_are_deterministic():
    engine = PaperEngine(PaperExecutionConfig(entry_slippage_bps=0, exit_slippage_bps=0, fee_bps_per_side=2))
    steps = engine.replay(intent(), [q("BTC", 100, 0), q("BTC", 101.8, 10)])
    p = steps[-1].position
    assert p.exit_reason is ExitReason.TARGET
    assert p.gross_r == pytest.approx(1.8)
    assert p.fees_usd > 0
    assert p.net_r < p.gross_r


def test_short_target_uses_symmetric_math():
    engine = PaperEngine(PaperExecutionConfig(entry_slippage_bps=0, exit_slippage_bps=0, fee_bps_per_side=0))
    steps = engine.replay(intent(Side.SHORT), [q("BTC", 100, 0), q("BTC", 98.2, 10)])
    p = steps[-1].position
    assert p.exit_reason is ExitReason.TARGET
    assert p.gross_r == pytest.approx(1.8)
    assert p.net_r == pytest.approx(1.8)


def test_long_stop_is_negative_one_r_before_costs():
    engine = PaperEngine(PaperExecutionConfig(entry_slippage_bps=0, exit_slippage_bps=0, fee_bps_per_side=0))
    steps = engine.replay(intent(), [q("BTC", 100, 0), q("BTC", 99, 10)])
    p = steps[-1].position
    assert p.exit_reason is ExitReason.STOP
    assert p.gross_r == pytest.approx(-1.0)


def test_breakeven_only_arms_after_threshold():
    engine = PaperEngine(
        PaperExecutionConfig(
            entry_slippage_bps=0,
            exit_slippage_bps=0,
            fee_bps_per_side=0,
            breakeven_after_r=0.5,
        )
    )
    steps = engine.replay(intent(), [q("BTC", 100, 0), q("BTC", 100.6, 5), q("BTC", 100.0, 10)])
    p = steps[-1].position
    assert p.exit_reason is ExitReason.BREAKEVEN
    assert p.gross_r == pytest.approx(0.0)
    assert p.be_armed is True


def test_lock_stop_preserves_profit_after_mfe_threshold():
    engine = PaperEngine(
        PaperExecutionConfig(
            entry_slippage_bps=0,
            exit_slippage_bps=0,
            fee_bps_per_side=0,
            breakeven_after_r=0.3,
            lock_after_r=0.5,
            lock_r=0.2,
        )
    )
    steps = engine.replay(intent(), [q("BTC", 100, 0), q("BTC", 100.6, 5), q("BTC", 100.2, 10)])
    p = steps[-1].position
    assert p.exit_reason is ExitReason.LOCKED_STOP
    assert p.gross_r == pytest.approx(0.2)
    assert p.lock_armed is True


def test_mfe_mae_update_without_mutating_prior_position():
    engine = PaperEngine(PaperExecutionConfig(entry_slippage_bps=0, exit_slippage_bps=0, fee_bps_per_side=0))
    p0 = engine.open(intent(), q("BTC", 100, 0))
    p1 = engine.mark(p0, q("BTC", 100.7, 5)).position
    p2 = engine.mark(p1, q("BTC", 99.5, 10)).position
    assert p0.mfe_r == 0
    assert p1.mfe_r == pytest.approx(0.7)
    assert p2.mfe_r == pytest.approx(0.7)
    assert p2.mae_r == pytest.approx(0.5)


def test_rejects_non_chronological_quotes():
    engine = PaperEngine(PaperExecutionConfig(entry_slippage_bps=0))
    p = engine.open(intent(), q("BTC", 100, 10))
    with pytest.raises(ValueError, match="chronological"):
        engine.mark(p, q("BTC", 100.1, 5))


def test_rejects_symbol_mismatch():
    engine = PaperEngine()
    with pytest.raises(ValueError, match="symbol"):
        engine.open(intent(), q("ETH", 100, 0))


def test_entry_slippage_is_adverse_for_both_sides():
    engine = PaperEngine(PaperExecutionConfig(entry_slippage_bps=10, exit_slippage_bps=0, fee_bps_per_side=0))
    long_p = engine.open(intent(Side.LONG, trade_id="l"), q("BTC", 100, 0))
    short_p = engine.open(intent(Side.SHORT, trade_id="s"), q("BTC", 100, 0))
    assert long_p.entry_price > 100
    assert short_p.entry_price < 100
