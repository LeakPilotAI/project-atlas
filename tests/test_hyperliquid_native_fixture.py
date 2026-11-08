import ast
import json
import os
import sqlite3
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from pathlib import Path
from threading import Event

import pytest
from app.services.hyperliquid_native_fixture import (
    NativeFixtureFacade,
    create_native_fixture,
)
from app.services.hyperliquid_partial_fixture import _body, _digest
from app.trading_core.perp_manual_state_store import (
    ManualPerpStateError,
    ManualPerpStateStore,
)
from test_hyperliquid_paper_handoff import STAMP
from test_hyperliquid_partial_fixture import fixture


def restart(f, pin):
    return NativeFixtureFacade(f[0], f[1], baseline=f[2], association=pin, journal=f[3].PaperJournal(),
                               journal_path=f[3].JOURNAL_PATH, manual_store=ManualPerpStateStore(f[4].path))


def setup(root, *, basket=False):
    f = fixture(root, basket=basket)
    pin = create_native_fixture(f[0], f[1], baseline=f[2], journal=f[3].PaperJournal(),
                                journal_path=f[3].JOURNAL_PATH, manual_store=f[4])
    return f, pin, restart(f, pin)


def request(facade, *, symbol="BTC", revision=0, ident="exit-1", quantity="0.125", price="102"):
    p = next(p for p in facade.snapshot()["view"]["positions"] if p["symbol"] == symbol)
    return {"schema": "HYPERLIQUID_NATIVE_EXIT_V2", "position_id": p["position_id"], "operation_id": ident,
            "expected_position_revision": revision, "quantity": quantity, "timestamp": STAMP + 2,
            "session_id": "fixture-day", "quote": {"symbol": symbol, "price": price,
                "source_id": "fixture-only", "verified": True, "observed_at": STAMP + 2}}


def test_separate_revisions_partial_full_projection_and_restart(tmp_path):
    f, pin, facade = setup(tmp_path, basket=True)
    for n, symbol in enumerate(("BTC", "ETH", "SOL")):
        r = request(facade, symbol=symbol, ident=f"{symbol}-partial", price="98" if symbol == "ETH" else "102")
        receipt = facade.record_exit(r, now=STAMP + 2)
        assert receipt["position_revision"] == 1 and receipt["source_revision"] == n + 1
        assert restart(f, pin).record_exit(r, now=STAMP + 2) == receipt
    for n, symbol in enumerate(("BTC", "ETH", "SOL")):
        r = request(facade, symbol=symbol, revision=1, ident=f"{symbol}-full", quantity="0.375", price="96" if symbol == "ETH" else "104")
        receipt = facade.record_exit(r, now=STAMP + 2)
        assert receipt["position_revision"] == 2 and receipt["source_revision"] == n + 4
    snap = restart(f, pin).snapshot()
    assert snap["source_revision"] == snap["applied_source_revision"] == 6
    assert set(snap["position_revisions"].values()) == {2}
    assert f[3].JOURNAL_PATH.read_bytes() == f[5][0]  # Historical/native journal bytes untouched.
    assert len(f[3].PaperJournal().list_open()) == 3 and not snap["view"]["native_positions_flat"]
    for p in f[4].load()["plans"]:
        assert p["status"] == "ENTERED"  # Legacy state is never falsely FLAT.
        projection = p["fixture_v2"]
        assert projection["lifecycle_status"] == "CLOSED_FIXTURE_LEDGER_ONLY"
        assert projection["applied_source_revision"] == 6 and projection["applied_position_revision"] == 2
        assert Decimal(projection["accounting"]["remaining_quantity"]) == 0
    report = facade.daily_report(day="2026-10-23", timezone="UTC", currency="USD")
    assert Decimal(report["report"]["closing_cash"]) == Decimal("1005.13") and not report["shutdown_authorized"]
    assert report["native_association"] == pin and report["native_applied_source_revision"] == 6


@pytest.mark.parametrize("damage", ["stale-revision", "schema", "identity", "duplicate-conflict"])
def test_rejected_requests_do_not_create_second_native_fill(tmp_path, damage):
    f, _, facade = setup(tmp_path)
    r = request(facade)
    facade.record_exit(r, now=STAMP + 2)
    bad = {**r, "operation_id": "next"}
    if damage == "schema": bad["schema"] = "UNKNOWN"
    if damage == "identity": bad["position_id"] = "foreign"
    if damage == "duplicate-conflict": bad.update(operation_id=r["operation_id"], quantity="0.2")
    with pytest.raises(ValueError): facade.record_exit(bad, now=STAMP + 2)
    assert facade.snapshot()["source_revision"] == 1
    assert len(f[3].PaperJournal().list_open()) == 1


def test_concurrent_pending_projection_blocks_replay_and_reporting(tmp_path):
    f, pin, facade = setup(tmp_path)
    r = request(facade)
    begun, release = Event(), Event()

    def fault(phase):
        if phase == "after_canonical":
            begun.set()
            assert release.wait(5)

    with ThreadPoolExecutor(2) as pool:
        first = pool.submit(facade.record_exit, r, now=STAMP + 2, fault=fault)
        assert begun.wait(5)
        with pytest.raises(ValueError): restart(f, pin).record_exit(r, now=STAMP + 2)
        with pytest.raises(ValueError): facade.daily_report(day="2026-10-23", timezone="UTC", currency="USD")
        release.set()
        receipt = first.result(timeout=5)
    assert restart(f, pin).record_exit(r, now=STAMP + 2) == receipt


@pytest.mark.parametrize("phase", ["before_intent", "after_intent", "canonical_after_intent", "canonical_ledger_after_commit",
                                    "after_canonical", "after_projection", "before_ack_commit", "after_ack"])
def test_actual_process_crash_never_replays_unacknowledged_projection(tmp_path, phase):
    f, pin, facade = setup(tmp_path)
    r = request(facade, quantity="0.5", price="104")
    payload = tmp_path / "request.json"
    payload.write_text(json.dumps(r), encoding="utf-8")
    code = '''import json,os,sys
from pathlib import Path
from test_hyperliquid_paper_handoff import actual_journal
from app.services.hyperliquid_native_fixture import NativeFixtureFacade
from app.trading_core.perp_manual_state_store import ManualPerpStateStore
root=Path(sys.argv[1]);module,journal=actual_journal(root)
facade=NativeFixtureFacade(root/'partial.sqlite',root/'ledger.sqlite',baseline=sys.argv[2],association=sys.argv[3],journal=journal,journal_path=module.JOURNAL_PATH,manual_store=ManualPerpStateStore(root/'manual.json'))
def fault(phase):
 if phase==sys.argv[4]:os._exit(71)
facade.record_exit(json.load(open(root/'request.json',encoding='utf-8')),now=int(sys.argv[5]),fault=fault)
'''
    result = subprocess.run([sys.executable, "-c", code, str(tmp_path), f[2], pin, phase, str(STAMP + 2)],
                            env=dict(os.environ), capture_output=True, timeout=15, check=False)
    assert result.returncode == 71, result.stderr.decode(errors="replace")
    revived = restart(f, pin)
    if phase in ("before_intent", "after_ack"):
        revived.record_exit(r, now=STAMP + 2)
        assert revived.snapshot()["source_revision"] == 1
    else:
        with pytest.raises(ValueError): revived.snapshot()
        with pytest.raises(ValueError): revived.record_exit(r, now=STAMP + 2)
        with pytest.raises(ValueError): revived.daily_report(day="2026-10-23", timezone="UTC", currency="USD")
    with sqlite3.connect(f[1]) as db:
        assert db.execute("SELECT COUNT(*) FROM partial_fills").fetchone()[0] <= 1
    assert f[3].JOURNAL_PATH.read_bytes() == f[5][0]


@pytest.mark.parametrize("damage", ["head", "receipt", "manual", "native-journal", "association-pin"])
def test_corruption_or_source_substitution_refuses_restart(tmp_path, damage):
    f, pin, facade = setup(tmp_path)
    facade.record_exit(request(facade), now=STAMP + 2)
    if damage in ("head", "receipt"):
        with sqlite3.connect(f[0]) as db:
            if damage == "head":
                head = json.loads(db.execute("SELECT body FROM native_head").fetchone()[0])
                head["source_revision"] = True
                db.execute("UPDATE native_head SET body=?,digest=?", (_body(head), _digest(head)))
            else: db.execute("UPDATE native_operations SET receipt='{}'")
    if damage == "manual": f[4].path.write_text('{}', encoding="utf-8")
    if damage == "native-journal": f[3].JOURNAL_PATH.write_bytes(f[5][0] + b'{}\n')
    if damage == "association-pin": pin = "0" * 64
    with pytest.raises((ValueError, KeyError, ManualPerpStateError)): restart(f, pin).snapshot()


@pytest.mark.parametrize("phase", ["after_association", "after_initial_projection"])
def test_interrupted_initialization_never_reinitializes_or_grants_admission(tmp_path, phase):
    f = fixture(tmp_path)

    def fault(point):
        if phase == point: raise OSError("fixture initialization interrupted")

    with pytest.raises(OSError):
        create_native_fixture(f[0], f[1], baseline=f[2], journal=f[3].PaperJournal(), journal_path=f[3].JOURNAL_PATH,
                              manual_store=f[4], fault=fault)
    with sqlite3.connect(f[0]) as db:
        head = json.loads(db.execute("SELECT body FROM native_head").fetchone()[0])
    with pytest.raises(ValueError): restart(f, _digest(head["association"])).snapshot()


def test_no_production_dispatch_imports_or_startup_activation():
    root = Path(__file__).resolve().parents[1]
    target = root / "backend/app/services/hyperliquid_native_fixture.py"
    for path in (root / "backend/app").rglob("*.py"):
        if path == target:
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8-sig"))):
            if isinstance(node, ast.ImportFrom):
                assert "hyperliquid_native_fixture" not in (node.module or ""), path
            if isinstance(node, ast.Import):
                assert all("hyperliquid_native_fixture" not in alias.name for alias in node.names), path


def test_changed_in_memory_native_quantity_is_not_trusted(tmp_path):
    _, _, facade = setup(tmp_path)
    native = facade.journal.list_open()[0]
    native["position_size"] = 999
    with pytest.raises(ValueError): facade.snapshot()


def test_native_snapshot_commit_without_ack_preserves_pending_and_blocks_report(tmp_path, monkeypatch):
    import app.trading_core.perp_manual_state_store as native
    f, pin, facade = setup(tmp_path)
    r = request(facade, quantity="0.5", price="104")
    original = native.sync_parent
    error = OSError("fixture manual publication durability failed")

    def sync(path):
        if path == f[4].path: raise error
        return original(path)

    monkeypatch.setattr(native, "sync_parent", sync)
    with pytest.raises(OSError) as failure: facade.record_exit(r, now=STAMP + 2)
    assert failure.value is error and f[4].pending_path.exists()
    with pytest.raises((ValueError, ManualPerpStateError)): restart(f, pin).record_exit(r, now=STAMP + 2)
    with pytest.raises((ValueError, ManualPerpStateError)): facade.daily_report(day="2026-10-23", timezone="UTC", currency="USD")
    assert f[3].JOURNAL_PATH.read_bytes() == f[5][0]


def test_stale_price_preserves_native_position_and_unacknowledged_intent(tmp_path):
    f, pin, facade = setup(tmp_path)
    r = request(facade)
    r["quote"]["observed_at"] -= 31
    with pytest.raises(ValueError): facade.record_exit(r, now=STAMP + 2)
    with pytest.raises(ValueError): restart(f, pin).record_exit(r, now=STAMP + 2)
    with pytest.raises(ValueError): facade.daily_report(day="2026-10-23", timezone="UTC", currency="USD")
    with sqlite3.connect(f[1]) as db:
        assert db.execute("SELECT COUNT(*) FROM partial_fills").fetchone()[0] == 0
    assert len(f[3].PaperJournal().list_open()) == 1


def test_rehashed_missing_projection_association_is_still_incomplete(tmp_path):
    f, _, facade = setup(tmp_path, basket=True)
    state = f[4].load()
    f[4].save(plans=state["plans"][:-1], setup_history=state["setup_history"])
    import hashlib
    with sqlite3.connect(f[0]) as db:
        head = json.loads(db.execute("SELECT body FROM native_head").fetchone()[0])
        head["manual_sha256"] = hashlib.sha256(f[4].path.read_bytes()).hexdigest()
        db.execute("UPDATE native_head SET body=?,digest=?", (_body(head), _digest(head)))
    with pytest.raises(ValueError): facade.snapshot()


def test_report_holds_cooperative_admission_until_publication(tmp_path, monkeypatch):
    import app.services.hyperliquid_native_fixture as native
    f, _, facade = setup(tmp_path)
    facade.record_exit(request(facade, quantity="0.5", price="104"), now=STAMP + 2)
    original = native.publish_partial_daily_fixture

    def publish(*args, **kwargs):
        with sqlite3.connect(f[0], timeout=0) as contender, pytest.raises(sqlite3.OperationalError, match="locked"):
            contender.execute("BEGIN IMMEDIATE")
        return original(*args, **kwargs)

    monkeypatch.setattr(native, "publish_partial_daily_fixture", publish)
    assert facade.daily_report(day="2026-10-23", timezone="UTC", currency="USD")["native_applied_source_revision"] == 1
