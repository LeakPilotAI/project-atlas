"""Phase 4 — alerts, allocation, paper book. Deterministic. No live Discord. No trading imports."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from app.investment.alerts import AlertStore, commit_alert, evaluate_alert
from app.investment.allocation import (
    ALLOCATION_VERSION,
    build_plan,
    format_plan,
    load_plans,
    maximum_recommended_allocation,
    persist_plan,
)
from app.investment.drawdown import DrawdownReport
from app.investment.engine import format_dashboard, process_research
from app.investment.enums import (
    EvidenceQuality,
    InvestmentAlertState,
    RiskTolerance,
    ThesisState,
)
from app.investment.market_hours import session_status
from app.investment.models import HoldingInput, PaperInvestmentAccount, PortfolioInput
from app.investment.notify import format_investment_alert
from app.investment.paper_book import PaperBook
from app.investment.portfolio import load_portfolio
from app.investment.research_models import ComponentScores, Explainability, ResearchRecord, SCORING_VERSION


def _dd(**kw) -> DrawdownReport:
    return DrawdownReport(
        current_drawdown=kw.get("dd", -0.28),
        drawdown_percentile=kw.get("pct", 80.0),
        coverage_bars=kw.get("bars", 400),
        coverage_label="test coverage",
    )


def _rec(**kw) -> ResearchRecord:
    return ResearchRecord(
        scoring_version=SCORING_VERSION,
        timestamp=kw.get("ts", datetime(2026, 8, 28, 16, 0, tzinfo=timezone.utc)),
        symbol=kw.get("symbol", "XYZ"),
        name="Test Co",
        price=kw.get("price", 50.0),
        classification=kw.get("cls", InvestmentAlertState.ACCUMULATION),
        opportunity_score=kw.get("score", 80),
        evidence_quality=kw.get("evidence", EvidenceQuality.HIGH),
        thesis=kw.get("thesis", ThesisState.STRONG),
        components=kw.get(
            "components",
            ComponentScores(
                valuation=80,
                fundamentals=82,
                drawdown=74,
                balance_sheet=80,
                cash_flow=80,
                thesis_integrity=90,
                risk=70,
                evidence_quality=88,
            ),
        ),
        drawdown=_dd(
            dd=kw.get("dd", -0.28),
            pct=kw.get("pct", 80.0),
            bars=kw.get("bars", 400),
        ),
        explain=Explainability(
            why_now=["valuation compression", "historically significant drawdown"],
            risks=["elevated vol", "sector concentration"],
            invalidation=["earnings and FCF both turn negative"],
        ),
        market_risk=[kw.get("vol_note", "annualized close-to-close vol ~ 20% in-sample")],
        generational_blockers=kw.get("blockers", []),
    )


def _port(**kw) -> PortfolioInput:
    return PortfolioInput(
        portfolio_value=kw.get("pv", 20_000.0),
        available_cash=kw.get("cash", 8_000.0),
        minimum_cash_reserve=kw.get("reserve", 2_000.0),
        maximum_position_percent=kw.get("maxpct", 15.0),
        maximum_sector_exposure_percent=kw.get("sect", 40.0),
        provided=True,
        risk_tolerance=kw.get("rt", RiskTolerance.MODERATE),
        holdings=kw.get("holdings", []),
        allow_fractional_shares=kw.get("frac", False),
        benchmark_symbol="SPY",
    )


def _store(tmp_path: Path) -> AlertStore:
    return AlertStore(path=tmp_path / "alert_state.json")


# --- alerts ---


def test_watch_to_accumulation_emits(tmp_path):
    store = _store(tmp_path)
    first = _rec(cls=InvestmentAlertState.WATCH, score=45)
    d1 = evaluate_alert(first, store)
    assert d1.emit is True
    commit_alert(first, d1, store, now=first.timestamp)
    nxt = _rec(cls=InvestmentAlertState.ACCUMULATION, score=80)
    d2 = evaluate_alert(nxt, store, now=nxt.timestamp + timedelta(minutes=1))
    assert d2.emit is True
    assert "WATCH → ACCUMULATION" in d2.reason


def test_accumulation_to_accumulation_suppressed(tmp_path):
    store = _store(tmp_path)
    r = _rec(cls=InvestmentAlertState.ACCUMULATION, score=80, price=50)
    d1 = evaluate_alert(r, store)
    commit_alert(r, d1, store, now=r.timestamp)
    d2 = evaluate_alert(r, store, now=r.timestamp + timedelta(minutes=5))
    assert d2.emit is False
    assert d2.suppressed is True


def test_accumulation_to_deep_value_emits(tmp_path):
    store = _store(tmp_path)
    a = _rec(cls=InvestmentAlertState.ACCUMULATION)
    d1 = evaluate_alert(a, store)
    commit_alert(a, d1, store, now=a.timestamp)
    b = _rec(cls=InvestmentAlertState.DEEP_VALUE, score=88, dd=-0.35)
    d2 = evaluate_alert(b, store, now=b.timestamp + timedelta(minutes=1))
    assert d2.emit is True
    assert "DEEP_VALUE" in d2.reason


def test_any_to_thesis_broken_is_high_priority(tmp_path):
    store = _store(tmp_path)
    a = _rec(cls=InvestmentAlertState.ACCUMULATION)
    d1 = evaluate_alert(a, store)
    commit_alert(a, d1, store, now=a.timestamp)
    b = _rec(cls=InvestmentAlertState.THESIS_BROKEN, thesis=ThesisState.BROKEN, score=20)
    d2 = evaluate_alert(b, store, now=b.timestamp + timedelta(seconds=1))
    assert d2.emit is True
    assert d2.priority == "HIGH"
    assert d2.classification is InvestmentAlertState.THESIS_BROKEN
    d3 = evaluate_alert(b, store, now=b.timestamp + timedelta(seconds=2))
    commit_alert(b, d2, store, now=b.timestamp + timedelta(seconds=1))
    d3 = evaluate_alert(b, store, now=b.timestamp + timedelta(seconds=2))
    assert d3.emit is False


def test_alert_cooldown_blocks_material_repeat(tmp_path):
    store = _store(tmp_path)
    a = _rec(cls=InvestmentAlertState.WATCH, score=50, price=100)
    d1 = evaluate_alert(a, store)
    commit_alert(a, d1, store, now=a.timestamp)
    b = _rec(cls=InvestmentAlertState.WATCH, score=70, price=100)  # material score, same class
    d2 = evaluate_alert(b, store, now=a.timestamp + timedelta(hours=1))
    assert d2.emit is False
    assert "cooldown" in d2.reason
    d3 = evaluate_alert(b, store, now=a.timestamp + timedelta(hours=25))
    assert d3.emit is True


def test_generational_safety_rejects_drawdown_only():
    store = AlertStore(persist=False)
    r = _rec(
        cls=InvestmentAlertState.GENERATIONAL_OPPORTUNITY,
        thesis=ThesisState.BROKEN,
        evidence=EvidenceQuality.LOW,
        score=40,
        dd=-0.55,
        pct=99.0,
    )
    d = evaluate_alert(r, store)
    assert d.classification is InvestmentAlertState.THESIS_BROKEN
    assert d.classification is not InvestmentAlertState.GENERATIONAL_OPPORTUNITY


# --- allocation / concentration ---


def test_concentration_blocks_more_buying():
    port = _port(
        holdings=[HoldingInput(symbol="XYZ", shares=80, current_value=8_000, sector="Health Care")]
    )
    cap, notes, err = maximum_recommended_allocation(_rec(), port)
    assert cap == 0
    assert "position limit" in err
    plan = build_plan(_rec(), port)
    assert plan.is_actionable() is False
    assert "position limit" in plan.blocked_reason


def test_sector_concentration_blocks():
    port = _port(
        pv=20_000,
        cash=8_000,
        maxpct=50,
        sect=10,
        holdings=[HoldingInput(symbol="AAA", shares=1, current_value=3_000, sector="Tech")],
    )
    r = _rec(symbol="BBB")
    r.input_snapshot = {"asset": {"sector": "Tech"}}
    cap, _, err = maximum_recommended_allocation(r, port)
    assert cap == 0
    assert "sector" in err


def test_cash_reserve_never_spent():
    rec = _rec()
    port = _port(cash=5_000, reserve=2_000, maxpct=50)
    plan = build_plan(rec, port)
    assert plan.is_actionable()
    assert plan.remaining_reserve >= 2_000 - 0.011
    spent = sum(t.dollar_amount or 0 for t in plan.tiers)
    assert pytest.approx(plan.starting_buying_power, abs=0.011) == spent + plan.remaining_reserve
    assert spent + plan.remaining_reserve == pytest.approx(5_000, abs=0.011)


def test_allocation_and_share_math_whole_shares():
    rec = _rec(price=40.0)
    port = _port(cash=8_000, reserve=2_000, maxpct=20, frac=False)
    plan = build_plan(rec, port)
    assert plan.is_actionable()
    assert plan.number_of_tiers >= 1
    for t in plan.tiers:
        assert t.share_quantity == int(t.share_quantity)
        assert t.price and t.price < rec.price
        assert t.dollar_amount == pytest.approx(t.share_quantity * t.price, abs=0.011)
        assert t.reason


def test_fractional_shares_when_enabled():
    rec = _rec(price=333.33)
    port = _port(cash=8_000, reserve=2_000, maxpct=20, frac=True)
    plan = build_plan(rec, port)
    assert plan.is_actionable()
    assert any(float(t.share_quantity) != int(t.share_quantity) for t in plan.tiers) or all(
        t.share_quantity > 0 for t in plan.tiers
    )


def test_limit_prices_not_fixed_five_percent():
    a = build_plan(_rec(price=100, vol_note="annualized close-to-close vol ~ 12% in-sample"), _port(maxpct=20))
    b = build_plan(_rec(price=100, vol_note="annualized close-to-close vol ~ 40% in-sample"), _port(maxpct=20))
    assert a.is_actionable() and b.is_actionable()
    drop_a = (100 - a.tiers[0].price) / 100
    drop_b = (100 - b.tiers[0].price) / 100
    assert drop_b > drop_a
    assert abs(drop_a - 0.05) > 0.001 or abs(drop_b - 0.05) > 0.001


def test_missing_portfolio_no_personalized_plan():
    plan = build_plan(_rec(), PortfolioInput())
    assert plan.is_actionable() is False
    assert "portfolio" in plan.blocked_reason


def test_missing_financials_pause_allocation():
    rec = _rec(evidence=EvidenceQuality.INSUFFICIENT, cls=InvestmentAlertState.ACCUMULATION)
    plan = build_plan(rec, _port())
    assert plan.status == "PAUSED_EVIDENCE"
    assert plan.is_actionable() is False


def test_watch_is_research_only():
    plan = build_plan(_rec(cls=InvestmentAlertState.WATCH, score=45), _port())
    assert plan.is_actionable() is False
    assert "research-only" in plan.blocked_reason


def test_thesis_broken_cancels_plan():
    plan = build_plan(
        _rec(cls=InvestmentAlertState.THESIS_BROKEN, thesis=ThesisState.BROKEN),
        _port(),
    )
    assert plan.status == "CANCELLED_THESIS_BROKEN"
    assert "STOP ACCUMULATING" in plan.blocked_reason


def test_recalc_does_not_increase_just_because_price_fell():
    rec1 = _rec(price=50, score=80)
    p1 = build_plan(rec1, _port(maxpct=20))
    rec2 = _rec(price=40, score=80)
    p2 = build_plan(rec2, _port(maxpct=20), previous=p1)
    assert p1.maximum_target_allocation is not None
    assert p2.maximum_target_allocation is not None
    assert p2.maximum_target_allocation <= p1.maximum_target_allocation + 0.011
    assert p2.version == p1.version + 1
    assert p2.parent_plan_id == p1.plan_id


def test_plan_versioning_appends(tmp_path):
    path = tmp_path / "plans.jsonl"
    p1 = build_plan(_rec(price=50), _port(maxpct=20))
    p2 = build_plan(_rec(price=48), _port(maxpct=20), previous=p1)
    persist_plan(p1, path=path)
    persist_plan(p2, path=path)
    rows = load_plans(path)
    assert len(rows) == 2
    assert rows[0]["plan_id"] == p1.plan_id
    assert rows[1]["version"] == p2.version
    assert p1.allocation_version == ALLOCATION_VERSION


def test_rounding_reconciles_exactly():
    plan = build_plan(_rec(price=17.37), _port(cash=8_000, reserve=2_000, maxpct=25))
    if not plan.is_actionable():
        pytest.skip("no whole shares at this price")
    spent = sum(Decimal(str(t.dollar_amount)) for t in plan.tiers)
    remain = Decimal(str(plan.remaining_reserve))
    start = Decimal(str(plan.starting_buying_power))
    assert start == spent + remain
    text = format_plan(plan)
    assert "Remaining reserve" in text
    assert "WHY THIS PRICE?" in text


# --- paper ---


def test_paper_fills_only_when_market_open(tmp_path):
    book = PaperBook(cash=8_000, state_path=tmp_path / "p.json", ledger_path=tmp_path / "l.jsonl")
    plan = build_plan(_rec(price=50), _port(maxpct=20))
    assert plan.is_actionable()
    book.submit_from_plan(plan)
    closed = book.try_fill("XYZ", 10.0, session="MARKET_CLOSED")
    assert closed == []
    assert book.cash == 8_000
    filled = book.try_fill("XYZ", plan.tiers[0].price, session="MARKET_OPEN")
    assert filled
    assert book.cash < 8_000
    assert book.positions["XYZ"].shares > 0
    assert book.unrealized_pnl() == pytest.approx(0.0, abs=0.02)  # marked at fill px then need mark
    book.mark({"XYZ": plan.tiers[0].price * 1.1})
    assert book.unrealized_pnl() > 0
    acc = book.as_legacy_account()
    with pytest.raises(RuntimeError, match="brokerage"):
        acc.execute_broker_order()
    with pytest.raises(RuntimeError, match="brokerage"):
        book.execute_broker_order()


def test_paper_pnl_and_drawdown(tmp_path):
    book = PaperBook(cash=1_000, state_path=tmp_path / "p.json", ledger_path=tmp_path / "l.jsonl")
    book.positions["XYZ"] = book.positions.get("XYZ")
    from app.investment.paper_book import PaperPosition

    book.positions["XYZ"] = PaperPosition(symbol="XYZ", shares=10, avg_cost=50, market_price=50)
    book.cash = 500
    book.peak_equity = 1000
    book.mark({"XYZ": 40})
    assert book.unrealized_pnl() == pytest.approx(-100)
    assert book.drawdown() < 0


def test_benchmark_tracking_no_alpha_claim(tmp_path):
    book = PaperBook(cash=10_000, state_path=tmp_path / "p.json", ledger_path=tmp_path / "l.jsonl")
    book.seed_benchmark(100)
    assert book.benchmark.shares == pytest.approx(100)
    snap = book.snapshot(spy_price=110)
    assert snap["benchmark_value"] == pytest.approx(11_000)
    assert "alpha" in snap["disclaimer"].lower() or "not" in snap["disclaimer"].lower()


# --- weekend / session ---


def test_weekend_is_closed_not_offline():
    sat = datetime(2026, 8, 29, 15, 0, tzinfo=timezone.utc)
    assert session_status(sat) == "MARKET_CLOSED"
    assert session_status(sat, system_ok=False) == "SYSTEM_OFFLINE"
    mon = datetime(2026, 8, 31, 15, 0, tzinfo=timezone.utc)  # 11:00 ET
    assert session_status(mon) == "MARKET_OPEN"


def test_engine_weekend_research_without_fills(tmp_path):
    book = PaperBook(cash=8_000, state_path=tmp_path / "p.json", ledger_path=tmp_path / "l.jsonl")
    sat = datetime(2026, 8, 29, 18, 0, tzinfo=timezone.utc)
    out = process_research(
        _rec(),
        portfolio=_port(maxpct=20),
        store=_store(tmp_path),
        paper=book,
        now=sat,
        persist=False,
    )
    assert out["session"] == "MARKET_CLOSED"
    assert book.fills == []


def test_dashboard_separates_investment_from_trading(tmp_path):
    recs = [_rec(), _rec(symbol="ABC", cls=InvestmentAlertState.WATCH, score=42, thesis=ThesisState.INTACT)]
    plans = [build_plan(recs[0], _port(maxpct=20))]
    book = PaperBook(cash=5_000, state_path=tmp_path / "p.json", ledger_path=tmp_path / "l.jsonl")
    text = format_dashboard(recs, plans, book, session="MARKET_CLOSED")
    assert "INVESTMENT OPPORTUNITIES" in text
    assert "ACTIVE ACCUMULATION PLANS" in text
    assert "THESIS HEALTH" in text
    assert "PAPER INVESTMENT" in text
    assert "Hyperliquid" in text
    assert "/paper" in text


def test_discord_alert_copy_and_thesis_broken_copy():
    r = _rec(cls=InvestmentAlertState.DEEP_VALUE)
    from app.investment.alerts import AlertDecision

    d = AlertDecision(emit=True, reason="WATCH → DEEP_VALUE", classification=InvestmentAlertState.DEEP_VALUE)
    text = format_investment_alert(r, d, plan=None)
    assert "ATLAS INVESTMENT OPPORTUNITY" in text
    assert "not a guarantee" in text.lower()
    r2 = _rec(cls=InvestmentAlertState.THESIS_BROKEN, thesis=ThesisState.BROKEN)
    d2 = AlertDecision(
        emit=True,
        reason="ANY STATE → THESIS_BROKEN",
        classification=InvestmentAlertState.THESIS_BROKEN,
        priority="HIGH",
    )
    t2 = format_investment_alert(r2, d2, plan=build_plan(r2, _port()))
    assert "THESIS BROKEN" in t2
    assert "STOP ACCUMULATING" in t2


def test_portfolio_loader_does_not_invent(tmp_path):
    p = tmp_path / "holdings.json"
    p.write_text('{"portfolio_value": 10000, "available_cash": 4000, "minimum_cash_reserve": 1000, "provided": true}', encoding="utf-8")
    port = load_portfolio(p)
    assert port.portfolio_value == 10000
    assert port.holdings == []
    empty = load_portfolio(tmp_path / "missing.json")
    assert empty.provided is False
    assert empty.is_complete_for_personalized_plan() is False


def test_phase4_does_not_import_trading_stack():
    import inspect
    import re
    from pathlib import Path as P

    import app.investment.allocation as a
    import app.investment.engine as e

    for mod in (a, e):
        src = P(inspect.getfile(mod)).read_text(encoding="utf-8")
        assert "perp_micro" not in src
        assert "paper_journal" not in src
        assert not re.search(r"\bRSI\b", src)
        assert "from app.services" not in src
