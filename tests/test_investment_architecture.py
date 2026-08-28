"""Phase 1 investment architecture — no scoring, no trading-engine mutation."""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from app.investment.enums import (
    AssetType,
    DataQuality,
    EvidenceQuality,
    InvestmentAlertState,
    ThesisState,
)
from app.investment.models import (
    AllocationPlan,
    HoldingInput,
    InvestmentAsset,
    InvestmentOpportunity,
    MeasuredValue,
    PaperInvestmentAccount,
    PortfolioInput,
)
from app.investment.providers import NullProvider, stamp_quality
from app.investment.safety import (
    SAFETY_RULES,
    allocation_without_portfolio,
    no_brokerage_execution,
    refuse_high_conviction_if_missing,
)
from app.investment.storage import (
    LEDGER_PATH,
    TRADING_PAPER_JOURNAL,
    assert_storage_separated,
)


def test_asset_model_defaults_unknown() -> None:
    a = InvestmentAsset(symbol="msft")
    assert a.symbol == "MSFT"
    assert a.asset_type is AssetType.UNKNOWN
    assert a.price.quality is DataQuality.MISSING
    assert a.market_cap.value is None
    assert a.price.is_usable() is False


def test_data_quality_states() -> None:
    names = {q.name for q in DataQuality}
    assert names == {"FRESH", "STALE", "MISSING", "CONFLICTING", "UNKNOWN"}


def test_thesis_and_alert_states() -> None:
    assert {t.name for t in ThesisState} == {
        "STRONG",
        "INTACT",
        "UNDER_PRESSURE",
        "DAMAGED",
        "BROKEN",
        "UNKNOWN",
    }
    assert {s.name for s in InvestmentAlertState} == {
        "WATCH",
        "ACCUMULATION",
        "DEEP_VALUE",
        "GENERATIONAL_OPPORTUNITY",
        "NO_ACTION",
        "THESIS_BROKEN",
    }


def test_opportunity_is_not_a_probability() -> None:
    opp = InvestmentOpportunity(asset=InvestmentAsset(symbol="AAPL"))
    assert opp.opportunity_score is None
    assert opp.confidence is None
    assert opp.evidence_quality is EvidenceQuality.UNKNOWN
    with pytest.raises(RuntimeError, match="not probabilities"):
        opp.as_probability_claim()


def test_portfolio_and_allocation_blocked_without_capital() -> None:
    empty = PortfolioInput()
    assert empty.is_complete_for_allocation() is False
    plan = allocation_without_portfolio(empty)
    assert isinstance(plan, AllocationPlan)
    assert plan.is_actionable() is False
    assert "portfolio" in plan.blocked_reason

    filled = PortfolioInput(
        portfolio_value=20000.0,
        available_cash=8000.0,
        holdings=[HoldingInput(symbol="MSFT", shares=10)],
        provided=True,
    )
    assert filled.is_complete_for_allocation() is True
    plan2 = allocation_without_portfolio(filled)
    assert "not implemented" in plan2.blocked_reason


def test_null_provider_never_invents_fundamentals() -> None:
    async def _run() -> None:
        n = NullProvider()
        px = await n.get_price("MSFT")
        pe = await n.get_metric("MSFT", "pe_ratio")
        val = await n.get_valuation("MSFT")
        assert px.quality is DataQuality.MISSING
        assert pe.value is None
        assert val.availability is False

    import asyncio

    asyncio.run(_run())


def test_stamp_quality_missing_is_not_fresh() -> None:
    m = stamp_quality(value=None, source="test", timestamp=None)
    assert m.quality is DataQuality.MISSING


def test_high_conviction_refused_when_critical_missing() -> None:
    opp = InvestmentOpportunity(
        asset=InvestmentAsset(symbol="ORCL"),
        classification=InvestmentAlertState.GENERATIONAL_OPPORTUNITY,
        evidence_quality=EvidenceQuality.INSUFFICIENT,
        missing_critical=["free_cash_flow", "shares_diluted"],
    )
    reasons = refuse_high_conviction_if_missing(opp)
    assert reasons
    assert any("missing" in r or "insufficient" in r for r in reasons)


def test_paper_investment_never_brokers_and_is_separate_ledger() -> None:
    acct = PaperInvestmentAccount(cash=1000.0)
    with pytest.raises(RuntimeError, match="brokerage"):
        acct.execute_broker_order("BUY", "MSFT", 1)
    with pytest.raises(RuntimeError, match="brokerage"):
        no_brokerage_execution()
    assert_storage_separated()
    assert LEDGER_PATH != TRADING_PAPER_JOURNAL
    assert "investment" in str(LEDGER_PATH)
    assert LEDGER_PATH.name != TRADING_PAPER_JOURNAL.name


def test_trading_and_investment_packages_are_separate() -> None:
    import app.investment as inv
    import app.services.paper_journal as pj

    inv_dir = Path(inspect.getfile(inv)).resolve().parent
    pj_dir = Path(inspect.getfile(pj)).resolve().parent
    assert inv_dir.name == "investment"
    assert pj_dir.name == "services"
    assert "paper_journal" not in inv.__file__
    src = Path(inv.__file__).read_text(encoding="utf-8")
    assert "perp_micro" not in src
    assert "RSI" not in src
    assert len(SAFETY_RULES) >= 12


def test_no_hardcoded_ticker_universe_in_models() -> None:
    text = Path(inspect.getfile(InvestmentAsset)).read_text(encoding="utf-8")
    for ticker in ("MSFT", "AAPL", "NVDA"):
        assert f'"{ticker}"' not in text
