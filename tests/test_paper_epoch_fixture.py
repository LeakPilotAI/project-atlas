import json
import os
import sqlite3
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from pathlib import Path

import pytest
from app.services.paper_epoch_fixture import EpochFixture, create_epoch_fixture
from app.services.paper_strategy_fixture import entry_command, exit_command

STAMP = 1792764000  # 2026-10-23; supplied fixture clock,not trusted authority.


def manifest(epoch="fixture-a", strategy="HYPERLIQUID_MANUAL"):
    return {"schema": "PAPER_EPOCH_FIXTURE_V1", "epoch": epoch, "strategy": strategy,
            "currency": "USD", "opening_cash": "1000", "opened_at": STAMP, "timezone": "America/New_York",
            "release": "fixture-release", "provenance": "DECLARED_SYNTHETIC_CAPITAL_NOT_SOURCE_PROOF",
            "cost_policy": "FIXTURE_ENTRY_NOTIONAL_ROUNDTRIP_V1", "fees_bps": "2", "slippage_bps": "2",
            "initial_net_r": "0"}


def quote(price="100", symbol="BTC", stamp=STAMP):
    return {"symbol": symbol, "price": price, "source_id": "fixture-only", "observed_at": stamp}


def entry(store, ident="entry-1", symbol="BTC"):
    return entry_command(store, operation_id=ident, symbol=symbol, quantity="0.5", quote=quote(symbol=symbol),
                         timestamp=STAMP, origin_ref=ident, manual=True, risk_price="2")


def test_inception_exclusive_immutable_and_no_authority(tmp_path):
    path = tmp_path / "epoch.sqlite"
    store = create_epoch_fixture(path, manifest())
    with pytest.raises(FileExistsError): create_epoch_fixture(path, manifest())
    wrong = manifest(); wrong["opening_cash"] = "2000"
    with pytest.raises(ValueError): EpochFixture(path, expected_manifest=wrong).snapshot()
    result = store.snapshot()
    assert result["cash"] == "1000" and result["equity"] is None
    assert not result["startup_authorized"] and not result["shutdown_authorized"]


def test_atomic_receipts_partial_full_retry_restart_and_report(tmp_path):
    path = tmp_path / "epoch.sqlite"
    s = create_epoch_fixture(path, manifest())
    command = entry(s)
    receipt = s.execute(command)
    assert s.execute(command) == receipt
    for n, qty, price in [(1, "0.125", "102"), (2, "0.375", "104")]:
        c = exit_command(s, operation_id=f"exit-{n}", position_id=receipt["position_id"], quantity=qty,
                         quote=quote(price), timestamp=STAMP, manual=True)
        ack = s.execute(c)
        assert EpochFixture(path, expected_manifest=manifest()).execute(c) == ack
    state = s.snapshot()
    assert Decimal(state["cash"]) == Decimal("1001.71") and Decimal(state["net"]) == Decimal("1.71")
    assert Decimal(state["positions"][receipt["position_id"]]["remaining"]) == 0
    report = s.daily_report("2026-10-23")
    assert s.daily_report("2026-10-23") == report
    assert report["state"] == "RECONCILED_FIXTURE_ONLY" and not report["shutdown_authorized"]
    with s.connect() as db:
        assert db.execute("SELECT COUNT(*) FROM events").fetchone()[0] == 3
        assert db.execute("SELECT COUNT(*) FROM daily").fetchone()[0] == 1


@pytest.mark.parametrize("damage", ["auto", "epoch", "stale", "capacity", "risk", "loss", "conflict", "unknown-field"])
def test_entry_restrictions(tmp_path, damage):
    m = manifest()
    if damage == "loss": m["initial_net_r"] = "-3"
    s = create_epoch_fixture(tmp_path / "epoch.sqlite", m)
    c = entry(s)
    if damage == "auto": c["manual"] = False
    if damage == "epoch": c["epoch"] = "foreign"
    if damage == "stale": c["quote"]["observed_at"] -= 31
    if damage == "risk": c["quantity"] = "0.501"
    if damage == "unknown-field": c["authorization"] = True
    if damage == "capacity":
        for asset in ("BTC", "ETH", "SOL"): s.execute(entry(s, asset, asset))
        c = entry(s)
    if damage == "conflict":
        s.execute(c)
        c["quantity"] = "0.25"
    with pytest.raises(ValueError): s.execute(c)


def test_concurrent_identical_commands_commit_once(tmp_path):
    s = create_epoch_fixture(tmp_path / "epoch.sqlite", manifest())
    c = entry(s)
    with ThreadPoolExecutor(4) as pool:
        receipts = list(pool.map(lambda _: s.execute(c), range(4)))
    assert all(r == receipts[0] for r in receipts)
    assert s.snapshot()["revision"] == 1


@pytest.mark.parametrize("phase", ["before_event", "before_commit", "after_commit"])
def test_abrupt_process_crash_recovery(tmp_path, phase):
    path = tmp_path / "epoch.sqlite"
    s = create_epoch_fixture(path, manifest())
    c = entry(s)
    config = tmp_path / "config.json"
    config.write_text(json.dumps([str(path), manifest(), c, phase]), encoding="utf-8")
    code = '''import json,os,sys
from app.services.paper_epoch_fixture import EpochFixture
p,m,c,phase=json.load(open(sys.argv[1],encoding="utf-8"))
def fault(point):
 if point==phase:os._exit(73)
EpochFixture(p,expected_manifest=m).execute(c,fault=fault)
'''
    child = subprocess.run([sys.executable, "-c", code, str(config)], cwd=Path(__file__).resolve().parents[1],
                           env={**os.environ, "PYTHONPATH": "backend"}, timeout=15, capture_output=True, check=False)
    assert child.returncode == 73, child.stderr
    assert s.snapshot()["revision"] == (1 if phase == "after_commit" else 0)
    ack = s.execute(c)
    assert s.execute(c) == ack and s.snapshot()["revision"] == 1


@pytest.mark.parametrize("damage", ["event", "receipt", "inception", "projection"])
def test_corrupt_committed_state_fails_closed(tmp_path, damage):
    path = tmp_path / "epoch.sqlite"
    s = create_epoch_fixture(path, manifest())
    s.execute(entry(s), projection_required=damage == "projection")
    with sqlite3.connect(path) as db:
        if damage == "event": db.execute("UPDATE events SET digest='wrong'")
        if damage == "receipt": db.execute("UPDATE events SET receipt='{}'")
        if damage == "inception": db.execute("UPDATE inception SET body='{}'")
        if damage == "projection": db.execute("DELETE FROM projections")
    with pytest.raises(ValueError): s.snapshot()


def test_cross_account_identity_and_open_report_refusal(tmp_path):
    a = create_epoch_fixture(tmp_path / "a.sqlite", manifest())
    b = create_epoch_fixture(tmp_path / "b.sqlite", manifest("fixture-b"))
    c = entry(a)
    with pytest.raises(ValueError): b.execute(c)
    a.execute(c)
    assert b.snapshot()["revision"] == 0 and b.snapshot()["cash"] == "1000"
    assert a.daily_report("2026-10-23")["state"] == "INCOMPLETE"
    with pytest.raises(ValueError): a.daily_report("not-a-day")


@pytest.mark.parametrize("damage", ["overclose", "revision", "missing-price", "wrong-symbol", "future-quote"])
def test_exit_evidence_and_revision_refusal(tmp_path, damage):
    s = create_epoch_fixture(tmp_path / "epoch.sqlite", manifest())
    pos = s.execute(entry(s))["position_id"]
    c = exit_command(s, operation_id="close", position_id=pos, quantity="0.5", quote=quote("104"), timestamp=STAMP, manual=True)
    if damage == "overclose": c["quantity"] = "0.501"
    if damage == "revision": c["expected_position_revision"] = 0
    if damage == "missing-price": del c["quote"]["price"]
    if damage == "wrong-symbol": c["quote"]["symbol"] = "SOL"
    if damage == "future-quote": c["quote"]["observed_at"] += 1
    with pytest.raises(ValueError): s.execute(c)
    assert s.snapshot()["revision"] == 1
