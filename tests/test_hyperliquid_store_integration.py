import asyncio
import hashlib
import sqlite3
from datetime import timedelta
from decimal import Decimal

import pytest
from app.services.daily_paper_liquidation import (
    append_partial_fixture,
    create_fixture_ledger,
    liquidate,
)
from app.services.hyperliquid_paper_handoff import (
    journal_fixture_handoff,
    manual_journal_fixture_consistency,
    native_full_close_fixture_projection,
)
from app.services.paper_bound_daily_report import publish_bound_daily
from app.services.paper_cash_evidence import append_cash_fixture
from app.services.paper_exit_audit import audit_fixture_exits
from app.trading_core.perp_manual_state_store import ManualPerpStateStore
from app.trading_core.perp_manual_trade_lifecycle import close_plan, enter_setup
from test_hyperliquid_paper_handoff import (
    NOW,
    STAMP,
    actual_journal,
    handoff,
    open_actual,
)


def manual_plan(symbol, side):
    direction = 1 if side == "LONG" else -1
    return enter_setup({"setup_key": f"{symbol}:{side}:fixture", "symbol": symbol, "side": side, "price": 100,
                        "levels": {"l1": 100, "l2": 100 - direction * .5, "l3": 100 - direction,
                                   "stop": 100 - direction * 2, "tp1": 100 + direction * 4,
                                   "tp2": 100 + direction * 6}}, fill_price=100, now=NOW)


def account(path):
    append_cash_fixture(path, {"id": "fixture-opening", "kind": "OPENING", "currency": "USD", "amount": "1000",
                               "timestamp": "2026-10-23T00:00:00+00:00", "source_digest": "declared-fixture-capital"})


@pytest.mark.parametrize("partials", [False, True])
def test_actual_manual_journal_to_cash_report_and_restart(tmp_path, partials):
    module, journal = actual_journal(tmp_path)
    plans, ids = [], []
    for symbol, side in [("BTC", "LONG"), ("ETH", "SHORT"), ("SOL", "LONG")]:
        ident = open_actual(journal, symbol, side)
        plans.append({**manual_plan(symbol, side), "fixture_journal_trade_id": ident})
        ids.append(ident)
    state = ManualPerpStateStore(tmp_path / "manual.json")
    state.save(plans=plans, setup_history=[])
    assert ManualPerpStateStore(state.path).load()["plans"] == plans
    original = module.JOURNAL_PATH.read_bytes()
    source = handoff(original)
    bound = manual_journal_fixture_consistency(state.path.read_bytes(), expected_sha256=hashlib.sha256(state.path.read_bytes()).hexdigest(), journal=source)
    assert len(bound["entered_ids"]) == 3 and not bound["native_positions_flat"]
    path = tmp_path / "handoff.sqlite"
    create_fixture_ledger(path, source["open_positions"])
    account(path)
    quotes = {}
    for position in source["open_positions"]:
        symbol, ident = position["symbol"], position["trade_id"]
        price = "96" if position["side"] == "SHORT" else "104"
        quotes[symbol] = {"price": price, "observed_at": STAMP + 10, "verified": True, "source_id": "fixture"}
        if partials:
            fill = {"schema": "PAPER_PARTIAL_FILL_V1", "trade_id": ident, "fill_id": ident + ":partial",
                    "quantity": "0.125", "price": "98" if position["side"] == "SHORT" else "102", "timestamp": STAMP + 5}
            append_partial_fixture(path, ident, fill)
            append_partial_fixture(path, ident, fill)
            with pytest.raises(ValueError, match="partial-close"):
                native_full_close_fixture_projection(source, ident, committed_partial_fills=[fill])
        else:
            assert native_full_close_fixture_projection(source, ident, committed_partial_fills=[])["production_authorized"] is False
    for _ in range(2):
        result = liquidate(path, "fixture-day", quotes, now=STAMP + 10, max_age=1)
        report = publish_bound_daily(path, day="2026-10-23", timezone="UTC", currency="USD")
        expected = Decimal("5.13") if partials else Decimal("5.88")
        assert Decimal(result["currency_totals_exact"]["USD"]) == expected
        assert Decimal(report["realized_net"]) == expected
        assert Decimal(report["closing_cash"]) == 1000 + expected
    assert audit_fixture_exits(path)["reconciled"] is True
    assert report["status"] == "CASH_RECONCILED_NOT_OPERATIONAL_ACCEPTANCE"
    assert report["total_equity"] is None
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT COUNT(*) FROM exits").fetchone()[0] == 3
        assert db.execute("SELECT COUNT(*) FROM partial_fills").fetchone()[0] == (3 if partials else 0)
        assert db.execute("SELECT COUNT(*) FROM bound_daily").fetchone()[0] == 1
    if partials:
        assert module.JOURNAL_PATH.read_bytes() == original
        assert len(module.PaperJournal().list_open()) == 3  # No fabricated native full closes.
        assert all(p["status"] == "ENTERED" for p in ManualPerpStateStore(state.path).load()["plans"])
    else:
        module._now = lambda: NOW + timedelta(seconds=10)
        for ident in ids:
            opened = next(p for p in source["open_positions"] if p["trade_id"] == ident)
            asyncio.run(journal.close_trade(ident, exit_price=float(quotes[opened["symbol"]]["price"]), result="WIN"))
        # Caller supplies the new observed clock; the old source revision is never reused.
        raw = module.JOURNAL_PATH.read_bytes()
        closed_source = journal_fixture_handoff(raw, expected_sha256=hashlib.sha256(raw).hexdigest(), observed_at=STAMP + 11)
        assert closed_source["open_positions"] == []
        assert sum(Decimal(v["net_currency"]) for v in closed_source["derived_closed_accounting"].values()) == expected
        state.save(plans=[close_plan(p, exit_price=float(quotes[p["symbol"]]["price"]), now=NOW + timedelta(seconds=10)) for p in plans], setup_history=[])
        assert module.PaperJournal().list_open() == []
        assert all(p["status"] == "CLOSED" for p in ManualPerpStateStore(state.path).load()["plans"])
        bound = manual_journal_fixture_consistency(state.path.read_bytes(), expected_sha256=hashlib.sha256(state.path.read_bytes()).hexdigest(), journal=closed_source)
        assert bound["native_positions_flat"] and not bound["shutdown_authorized"]
