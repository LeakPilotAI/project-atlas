from __future__ import annotations

import pytest

from app.trading_core.domains import ATLAS_ENGINE_LAYOUT, DomainViolation, EngineDomain, require_hyperliquid_market
from app.trading_core.models import Side
from app.trading_core.perp_manual_planner import build_manual_perp_plan


def test_engine_layout_is_three_distinct_domains():
    assert ATLAS_ENGINE_LAYOUT.isolated is True
    assert ATLAS_ENGINE_LAYOUT.perp is EngineDomain.HYPERLIQUID_PERP
    assert ATLAS_ENGINE_LAYOUT.investment is EngineDomain.EQUITY_INVESTMENT
    assert ATLAS_ENGINE_LAYOUT.orchestration is EngineDomain.ORCHESTRATION


def test_hyperliquid_firewall_rejects_equity_not_in_live_universe():
    with pytest.raises(DomainViolation):
        require_hyperliquid_market("MSFT", {"BTC", "ETH", "SOL"})


def test_hyperliquid_firewall_normalizes_verified_market():
    assert require_hyperliquid_market(" btc ", {"BTC", "ETH"}) == "BTC"


def test_manual_long_plan_has_layered_limits_and_tp_above_entry():
    p = build_manual_perp_plan(
        symbol="BTC",
        side=Side.LONG,
        reference_price=100_000.0,
        volatility_pct=2.0,
        hyperliquid_symbols={"BTC", "ETH", "SOL"},
    )
    assert p.stop < p.l3 < p.l2 < p.l1 < p.reference_price
    assert p.tp1 > p.l1
    assert p.tp2 > p.tp1
    assert p.target_rr == pytest.approx(1.8)


def test_manual_short_plan_has_layered_limits_and_tp_below_entry():
    p = build_manual_perp_plan(
        symbol="ETH",
        side=Side.SHORT,
        reference_price=4_000.0,
        volatility_pct=1.5,
        hyperliquid_symbols={"BTC", "ETH", "SOL"},
    )
    assert p.reference_price < p.l1 < p.l2 < p.l3 < p.stop
    assert p.tp1 < p.l1
    assert p.tp2 < p.tp1


def test_manual_plan_refuses_symbol_outside_hyperliquid():
    with pytest.raises(DomainViolation):
        build_manual_perp_plan(
            symbol="AAPL",
            side=Side.LONG,
            reference_price=200.0,
            volatility_pct=2.0,
            hyperliquid_symbols={"BTC", "ETH", "SOL"},
        )


def test_manual_plan_rejects_invalid_inputs():
    with pytest.raises(ValueError):
        build_manual_perp_plan(
            symbol="SOL",
            side=Side.LONG,
            reference_price=0.0,
            volatility_pct=2.0,
            hyperliquid_symbols={"SOL"},
        )
