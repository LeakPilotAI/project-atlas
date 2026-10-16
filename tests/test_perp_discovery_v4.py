from __future__ import annotations

from app.trading_core.models import Side
from app.trading_core.perp_discovery import analyze_candles, rank_setup, shortlist_markets


def _candles(start: float, step: float, n: int = 48):
    return [{"close": start + step * i} for i in range(n)]


def test_up_structure_promotes_long():
    structure = analyze_candles(_candles(100.0, 0.30))
    assert structure.side is Side.LONG
    assert structure.confidence > 0
    assert structure.trend_pct > 0
    assert structure.momentum_pct > 0

    ranked = rank_setup(
        symbol="BTC",
        price=114.0,
        volume_24h=20_000_000,
        open_interest=8_000_000,
        funding_rate=-0.0001,
        structure=structure,
    )
    assert ranked is not None
    assert ranked.side is Side.LONG
    assert ranked.score > 50


def test_down_structure_promotes_short():
    structure = analyze_candles(_candles(120.0, -0.30))
    assert structure.side is Side.SHORT
    assert structure.trend_pct < 0
    assert structure.momentum_pct < 0

    ranked = rank_setup(
        symbol="ETH",
        price=106.0,
        volume_24h=5_000_000,
        open_interest=2_000_000,
        funding_rate=0.0001,
        structure=structure,
    )
    assert ranked is not None
    assert ranked.side is Side.SHORT
    assert ranked.score > 40


def test_flat_structure_is_not_forced_into_trade():
    candles = [{"close": 100.0 + (0.02 if i % 2 else -0.02)} for i in range(48)]
    structure = analyze_candles(candles)
    assert structure.side is None
    assert rank_setup(
        symbol="SOL",
        price=100.0,
        volume_24h=2_000_000,
        open_interest=900_000,
        funding_rate=0.0,
        structure=structure,
    ) is None


def test_insufficient_history_is_rejected():
    structure = analyze_candles(_candles(100.0, 0.2, n=10))
    assert structure.side is None
    assert structure.reason == "insufficient candle history"


def test_shortlist_uses_tradability_before_expensive_candles():
    rows = [
        {"symbol": "LOW", "price": 1.0, "volume_24h": 100_000, "open_interest": 50_000},
        {"symbol": "BTC", "price": 100_000, "volume_24h": 20_000_000, "open_interest": 8_000_000},
        {"symbol": "ETH", "price": 2_500, "volume_24h": 5_000_000, "open_interest": 2_000_000},
    ]
    out = shortlist_markets(rows, limit=2)
    assert [r["symbol"] for r in out] == ["BTC", "ETH"]
