import hashlib
import json
import os
import sqlite3
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from threading import Event

import pytest
from app.services.daily_paper_liquidation import create_fixture_ledger
from app.services.hyperliquid_paper_handoff import manual_journal_fixture_consistency
from app.services.hyperliquid_partial_fixture import (
    append_partial_exit_fixture,
    create_partial_fixture,
    partial_fixture_view,
    publish_partial_daily_fixture,
)
from app.trading_core.perp_manual_state_store import ManualPerpStateStore
from test_hyperliquid_paper_handoff import STAMP, actual_journal, handoff, open_actual
from test_hyperliquid_store_integration import account, manual_plan


def fixture(root, *, symbol="BTC", side="LONG", basket=False):
    module, journal = actual_journal(root)
    pairs = [("BTC", "LONG"), ("ETH", "SHORT"), ("SOL", "LONG")] if basket else [(symbol, side)]
    plans = []
    for asset, direction in pairs:
        ident = open_actual(journal, asset, direction)
        plans.append({**manual_plan(asset, direction), "fixture_journal_trade_id": ident})
    store = ManualPerpStateStore(root / "manual.json")
    store.save(plans=plans, setup_history=[])
    store.load()
    raw = module.JOURNAL_PATH.read_bytes()
    source = handoff(raw)
    manual = store.path.read_bytes()
    consistency = manual_journal_fixture_consistency(manual, expected_sha256=hashlib.sha256(manual).hexdigest(), journal=source)
    ledger, overlay = root / "ledger.sqlite", root / "partial.sqlite"
    create_fixture_ledger(ledger, source["open_positions"])
    account(ledger)
    pin = create_partial_fixture(overlay, namespace="fixture-session", journal=source, consistency=consistency)
    return overlay, ledger, pin, module, store, (raw, manual)


def view(f):
    return partial_fixture_view(f[0], f[1], expected_baseline=f[2])


def request(f, *, revision=0, quantity="0.125", price="102", ident="partial-1"):
    v = view(f)
    symbol = v["positions"][0]["symbol"]
    return {"schema": "HYPERLIQUID_PARTIAL_REQUEST_V2", "position_id": v["positions"][0]["position_id"],
            "fill_id": ident, "quantity": quantity, "quote": {"symbol": symbol, "price": price,
            "source_id": "deterministic-fixture", "observed_at": STAMP + 2, "verified": True},
            "timestamp": STAMP + 2, "session_id": "fixture-day", "expected_revision": revision}


def append(f, r, **kwargs):
    return append_partial_exit_fixture(f[0], f[1], r, expected_baseline=f[2], now=STAMP + 2, **kwargs)


@pytest.mark.parametrize("symbol,side", [("BTC", "LONG"), ("ETH", "SHORT"), ("SOL", "LONG")])
def test_partial_final_source_preservation_cash_and_restart(tmp_path, symbol, side):
    f = fixture(tmp_path, symbol=symbol, side=side)
    first = request(f, price="98" if side == "SHORT" else "102")
    ack = append(f, first)
    assert append(f, first) == ack
    v = view(f)
    p = v["positions"][0]
    assert p["accounting"]["remaining_quantity"] == "0.375"
    assert Decimal(p["accounting"]["net_currency"]) == Decimal("0.24")
    assert p["status"] == "PARTIALLY_CLOSED" and Decimal(p["remaining_entry_notional"]) == Decimal("37.5")
    assert sum(Decimal(x) for x in p["cost_components"].values()) == Decimal("0.01")
    final = request(f, revision=1, quantity="0.375", price="96" if side == "SHORT" else "104", ident="final-2")
    final_ack = append(f, final)
    assert append(f, final) == final_ack and view(f)["revision"] == 2
    p = view(f)["positions"][0]
    assert p["status"] == "CLOSED_FIXTURE_LEDGER_ONLY"
    assert Decimal(p["accounting"]["net_currency"]) == Decimal("1.71")
    assert Decimal(p["accounting"]["net_r_original_risk"]) == Decimal("1.71")
    assert not view(f)["native_positions_flat"] and not view(f)["shutdown_authorized"]
    receipt = publish_partial_daily_fixture(f[0], f[1], expected_baseline=f[2], day="2026-10-23", timezone="UTC", currency="USD")
    report = receipt["report"]
    assert receipt["revision"] == 2 and not receipt["shutdown_authorized"]
    assert Decimal(report["closing_cash"]) == Decimal("1001.71")
    assert f[3].JOURNAL_PATH.read_bytes() == f[5][0] and f[4].path.read_bytes() == f[5][1]
    assert len(f[3].PaperJournal().list_open()) == 1 and f[4].load()["plans"][0]["status"] == "ENTERED"


@pytest.mark.parametrize("damage", ["stale", "future", "quantity", "overclose", "identity", "version", "revision", "clock", "price", "source"])
def test_invalid_partial_never_mutates_or_erases_native_position(tmp_path, damage):
    f = fixture(tmp_path)
    r = request(f)
    if damage == "stale": r["quote"]["observed_at"] -= 31
    if damage == "future": r["quote"]["observed_at"] += 1
    if damage == "quantity": r["quantity"] = "NaN"
    if damage == "overclose": r["quantity"] = "0.501"
    if damage == "identity": r["position_id"] = "foreign"
    if damage == "version": r["schema"] = "V99"
    if damage == "revision": r["expected_revision"] = 1
    if damage == "clock": r["timestamp"] -= 1
    if damage == "price": r["quote"]["price"] = "0"
    if damage == "source": r["quote"]["source_id"] = ""
    with pytest.raises(ValueError): append(f, r)
    assert view(f)["revision"] == 0
    assert f[3].JOURNAL_PATH.read_bytes() == f[5][0]


def test_conflicting_callbacks_and_concurrent_operations_refuse(tmp_path):
    f = fixture(tmp_path)
    r = request(f)
    begun, release = Event(), Event()

    def fault(phase):
        if phase == "after_intent":
            begun.set()
            assert release.wait(5)

    with ThreadPoolExecutor(2) as pool:
        first = pool.submit(append, f, r, fault=fault)
        assert begun.wait(5)
        with pytest.raises(ValueError): append(f, r)
        with pytest.raises(ValueError): view(f)
        release.set()
        first.result(timeout=5)
    assert append(f, r)["revision"] == 1
    with pytest.raises(ValueError): append(f, {**r, "quantity": "0.2"})
    assert view(f)["positions"][0]["accounting"]["unique_fill_n"] == 1


@pytest.mark.parametrize("phase", ["before_intent", "after_intent", "ledger_after_partial", "ledger_before_commit",
                                    "ledger_after_commit", "before_ack", "before_ack_commit", "after_ack"])
def test_real_child_crash_preserves_cross_store_uncertainty(tmp_path, phase):
    f = fixture(tmp_path)
    r = request(f, quantity="0.5", price="104", ident="full-final")
    payload = tmp_path / "request.json"
    payload.write_text(json.dumps(r), encoding="utf-8")
    code = '''import json,os,sys
from app.services.hyperliquid_partial_fixture import append_partial_exit_fixture
def fault(phase):
 if phase==sys.argv[5]:os._exit(67)
append_partial_exit_fixture(sys.argv[1],sys.argv[2],json.load(open(sys.argv[3],encoding="utf-8")),expected_baseline=sys.argv[4],now=int(sys.argv[6]),fault=fault)
'''
    result = subprocess.run([sys.executable, "-c", code, str(f[0]), str(f[1]), str(payload), f[2], phase, str(STAMP + 2)],
                            env={**os.environ}, timeout=15, capture_output=True, check=False)
    assert result.returncode == 67, result.stderr.decode(errors="replace")
    if phase in ("before_intent", "after_ack"):
        append(f, r)
        assert view(f)["positions"][0]["accounting"]["complete"]
    else:
        with pytest.raises(ValueError): view(f)
        with pytest.raises(ValueError): append(f, r)
        with pytest.raises(ValueError):
            publish_partial_daily_fixture(f[0], f[1], expected_baseline=f[2], day="2026-10-23", timezone="UTC", currency="USD")
    with sqlite3.connect(f[1]) as db:
        fills = db.execute("SELECT COUNT(*) FROM partial_fills").fetchone()[0]
        exits = db.execute("SELECT COUNT(*) FROM exits").fetchone()[0]
        assert fills == exits and fills <= 1
    assert f[3].JOURNAL_PATH.read_bytes() == f[5][0] and len(f[3].PaperJournal().list_open()) == 1


@pytest.mark.parametrize("damage", ["baseline", "event", "fill", "position", "finalization", "untracked-fill"])
def test_corrupted_store_or_cross_store_disagreement_refuses(tmp_path, damage):
    f = fixture(tmp_path)
    append(f, request(f, quantity="0.5", price="104"))
    with sqlite3.connect(f[0] if damage in ("baseline", "event") else f[1]) as db:
        if damage == "baseline": db.execute("UPDATE baseline SET body='{}'")
        if damage == "event": db.execute("UPDATE operations SET event='{}'")
        if damage == "fill": db.execute("DELETE FROM partial_fills")
        if damage == "position": db.execute("DELETE FROM positions")
        if damage == "finalization": db.execute("DELETE FROM exits")
        if damage == "untracked-fill": db.execute("INSERT INTO partial_fills VALUES('foreign','foreign','{}')")
    with pytest.raises((ValueError, KeyError)): view(f)
    assert f[4].load()["plans"][0]["status"] == "ENTERED"


def test_three_positions_versioned_reports_and_no_premature_flat(tmp_path):
    f = fixture(tmp_path, basket=True)
    initial = view(f)
    for n, p in enumerate(initial["positions"]):
        for step, quantity in enumerate(("0.125", "0.375")):
            r = request(f, revision=n * 2 + step, quantity=quantity, ident=f"fill-{n}-{step}")
            r["position_id"] = p["position_id"]
            r["quote"]["symbol"] = p["symbol"]
            r["quote"]["price"] = (("98" if step == 0 else "96") if p["side"] == "SHORT" else ("102" if step == 0 else "104"))
            append(f, r)
            if n < 2 or step == 0:
                with pytest.raises(ValueError):
                    publish_partial_daily_fixture(f[0], f[1], expected_baseline=f[2], day="2026-10-23", timezone="UTC", currency="USD")
    receipts = [publish_partial_daily_fixture(f[0], f[1], expected_baseline=f[2], day="2026-10-23", timezone="UTC", currency="USD") for _ in range(2)]
    assert receipts[0] == receipts[1] and receipts[0]["revision"] == 6
    assert Decimal(receipts[0]["report"]["closing_cash"]) == Decimal("1005.13")
    assert len(f[3].PaperJournal().list_open()) == 3
    assert all(p["status"] == "ENTERED" for p in f[4].load()["plans"])


def test_stable_identity_ignores_mutable_source_revision_but_binds_namespace(tmp_path):
    from app.services.hyperliquid_partial_fixture import _identity
    f = fixture(tmp_path)
    source = handoff(f[3].JOURNAL_PATH.read_bytes())
    original = source["open_positions"][0]
    changed = {**original, "source_record_revision": 100, "source_sha256": "f" * 64}
    assert _identity("fixture-session", original) == _identity("fixture-session", changed)
    assert _identity("foreign-session", original) != _identity("fixture-session", original)
    assert _identity("fixture-session", {**original, "trade_id": "foreign"}) != _identity("fixture-session", original)


def test_v1_full_close_is_unchanged_and_never_rewritten_as_partial(tmp_path):
    import asyncio
    from datetime import timedelta

    from app.services.hyperliquid_paper_handoff import journal_fixture_handoff
    from test_hyperliquid_paper_handoff import NOW
    module, journal = actual_journal(tmp_path)
    ident = open_actual(journal)
    prefix = module.JOURNAL_PATH.read_bytes()
    module._now = lambda: NOW + timedelta(seconds=2)
    asyncio.run(journal.close_trade(ident, exit_price=104, result="WIN"))
    raw = module.JOURNAL_PATH.read_bytes()
    assert raw.startswith(prefix) and b'HYPERLIQUID_PARTIAL' not in raw
    source = journal_fixture_handoff(raw, expected_sha256=hashlib.sha256(raw).hexdigest(), observed_at=STAMP + 3)
    assert source["closed_ids"] == [ident] and source["open_positions"] == []
    assert Decimal(source["derived_closed_accounting"][ident]["net_currency"]) == Decimal("1.96")
    assert module.JOURNAL_PATH.read_bytes() == raw


@pytest.mark.parametrize("phase", ["ledger_before_commit", "ledger_after_commit", "before_ack_commit"])
def test_interrupted_write_retains_pending_intent_and_refuses_report(tmp_path, phase):
    f = fixture(tmp_path)
    r = request(f, quantity="0.5", price="104")
    failure = OSError("fixture interrupted persistence")

    def fault(point):
        if point == phase:
            raise failure

    with pytest.raises(OSError) as error: append(f, r, fault=fault)
    assert error.value is failure
    with pytest.raises(ValueError): append(f, r)
    with pytest.raises(ValueError):
        publish_partial_daily_fixture(f[0], f[1], expected_baseline=f[2], day="2026-10-23", timezone="UTC", currency="USD")
    assert f[4].load()["plans"][0]["status"] == "ENTERED"
