"""Actual reviewed journal class with singleton omitted; explicit disposable paths only."""
import asyncio
import hashlib
import json
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from app.services.hyperliquid_paper_handoff import (
    fixture_scope,
    journal_fixture_handoff,
    validate_fixture_entry,
)
from test_r7e47r_durable_acknowledgements import source_module

NOW = datetime(2026, 10, 23, 14, tzinfo=UTC)
STAMP = int(NOW.timestamp())


def actual_journal(root):
    module = source_module("backend/app/services/paper_journal.py", "paper_journal")
    module.JOURNAL_PATH = root / "journal.jsonl"
    module.CANDIDATE_PATH = root / "candidates.jsonl"
    module._now = lambda: NOW
    return module, module.PaperJournal()


def open_actual(journal, symbol="BTC", side="LONG"):
    return asyncio.run(journal.open_trade(symbol=symbol, side=side, entry=100, stop=98 if side == "LONG" else 102,
                                         tp1=104 if side == "LONG" else 96, tp2=106 if side == "LONG" else 94,
                                         risk_usd=1, counts_for_live=False, fees_bps=2, slippage_bps=2,
                                         source="fixture_hyperliquid_manual", features={"fixture_manual_confirmation": True,
                                                                                     "fixture_operation_id": f"entry:{symbol}:{side}"}))


def handoff(raw):
    return journal_fixture_handoff(raw, expected_sha256=hashlib.sha256(raw).hexdigest(), observed_at=STAMP + 1)


def test_scope_retains_stricter_existing_contract():
    scope = fixture_scope()
    assert scope["initial_cash"] == "1000" and scope["max_risk_usd"] == "1"
    assert scope["max_positions"] == 3 and scope["symbols"] == ["BTC", "ETH", "SOL"]
    assert scope["manual_only"] and not scope["production_authorized"] and not scope["funding_modeled"]


@pytest.mark.parametrize("damage", [None, "risk", "auto", "asset", "quote-asset", "stale", "future", "capacity", "loss", "control"])
def test_fixture_entry_refuses_scope_or_risk_violation(damage):
    args = {"symbol": "BTC", "side": "LONG", "risk_usd": "1", "manual_confirmation": True,
            "quote": {"symbol": "BTC", "price": "100", "observed_at": STAMP, "verified": True, "source_id": "fixture"},
            "now": STAMP, "open_positions": [], "session_net_r": 0, "kill_switch": False, "controls_reliable": True}
    if damage == "risk": args["risk_usd"] = "25"
    if damage == "auto": args["manual_confirmation"] = False
    if damage == "asset": args["symbol"] = "OTHER"
    if damage == "quote-asset": args["quote"]["symbol"] = "ETH"
    if damage == "stale": args["quote"]["observed_at"] = STAMP - 31
    if damage == "future": args["quote"]["observed_at"] = STAMP + 1
    if damage == "capacity": args["open_positions"] = [{"trade_type": "PAPER"}] * 3
    if damage == "loss": args["session_net_r"] = -3
    if damage == "control": args["controls_reliable"] = False
    if damage:
        with pytest.raises(ValueError): validate_fixture_entry(**args)
    else:
        assert validate_fixture_entry(**args)["paper_trading_authorized"] is False


@pytest.mark.parametrize("side", ["LONG", "SHORT"])
def test_actual_journal_source_revisions_and_full_close_costs(tmp_path, side):
    module, journal = actual_journal(tmp_path)
    ident = open_actual(journal, side=side)
    initial = module.JOURNAL_PATH.read_bytes()
    assert handoff(initial)["open_positions"][0]["quantity"] == "0.5"
    open_actual(journal, side=side)  # actual interface suppresses duplicate logical open
    assert module.JOURNAL_PATH.read_bytes() == initial
    price = 104 if side == "LONG" else 96
    asyncio.run(journal.close_trade(ident, exit_price=price, result="WIN", exit_reason="MANUAL_FIXTURE"))
    closed = module.JOURNAL_PATH.read_bytes()
    result = handoff(closed)
    assert result["open_positions"] == [] and result["closed_ids"] == [ident]
    assert Decimal(result["derived_closed_accounting"][ident]["net_currency"]) == Decimal("1.96")
    assert result["source_completeness_independently_proven"] is False
    asyncio.run(journal.close_trade(ident, exit_price=price, result="WIN"))
    assert module.JOURNAL_PATH.read_bytes() == closed


@pytest.mark.parametrize("damage", ["partial-tail", "duplicate-field", "duplicate-open", "cost", "future", "interrupted", "pnl"])
def test_strict_handoff_refuses_corrupt_or_incomplete_actual_records(tmp_path, damage):
    module, journal = actual_journal(tmp_path)
    ident = open_actual(journal)
    if damage in ("interrupted", "pnl"):
        if damage == "interrupted": journal.interrupt_open_for_shutdown()
        else: asyncio.run(journal.close_trade(ident, exit_price=104, result="WIN"))
    rows = [json.loads(line) for line in module.JOURNAL_PATH.read_bytes().splitlines()]
    if damage == "duplicate-open": rows.append(rows[0])
    if damage == "cost": rows[0]["slippage_bps"] = 0
    if damage == "future": rows[0]["entry_timestamp"] = "2050-01-01T00:00:00+00:00"
    if damage == "pnl": rows[-1]["net_pnl_r"] = 999
    raw = ("".join(json.dumps(row) + "\n" for row in rows)).encode()
    if damage == "partial-tail": raw = raw[:-1]
    if damage == "duplicate-field": raw = raw.replace(b'"event": "open"', b'"event":"mark","event":"open"')
    with pytest.raises(ValueError): handoff(raw)
