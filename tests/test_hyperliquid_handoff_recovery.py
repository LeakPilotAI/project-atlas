import errno
import hashlib
import sqlite3
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest
from app.services.daily_paper_fixture_adapter import isolated_shutdown
from app.services.daily_paper_liquidation import create_fixture_ledger
from app.services.hyperliquid_paper_handoff import validate_fixture_entry
from app.services.paper_writer_fixture import (
    close_fixture_writers,
    provision_fixture_writers,
    run_fixture_writer,
)
from app.trading_core.perp_manual_state_store import (
    ManualPerpStateError,
    ManualPerpStateStore,
)
from test_hyperliquid_paper_handoff import STAMP, actual_journal, handoff, open_actual
from test_hyperliquid_store_integration import account
from test_r7e47r_durable_acknowledgements import source_module

PAYLOAD = hashlib.sha256(b'fixture-only:manual:BTC:LONG:risk1:fee2:slip2').hexdigest()


def coordinator(tmp_path, roster=None):
    path = tmp_path / "writers.sqlite"
    create_fixture_ledger(path, [])
    provision_fixture_writers(path, roster or {"journal": "fixture-one"})
    return path


@pytest.mark.parametrize("committed", [False, True])
def test_actual_append_failure_never_acknowledges_and_does_not_blindly_replay(tmp_path, monkeypatch, committed):
    path = coordinator(tmp_path)
    module, journal = actual_journal(tmp_path)
    original = module.write_flushed
    error = OSError(errno.ENOSPC, "fixture disk full at append boundary")

    def write(*args):
        if committed: original(*args)
        raise error

    monkeypatch.setattr(module, "write_flushed", write)
    kwargs = {"writer": "journal", "incarnation": "fixture-one", "operation": "manual-BTC-1",
              "payload": PAYLOAD, "mutation": lambda: open_actual(journal)}
    with pytest.raises(OSError) as failure: run_fixture_writer(path, **kwargs)
    assert failure.value is error and journal.list_open() == []
    with pytest.raises(ValueError): run_fixture_writer(path, **kwargs)
    assert close_fixture_writers(path, {"journal": "fixture-one"})["status"] == "INCOMPLETE"
    raw = module.JOURNAL_PATH.read_bytes()
    if committed:
        assert len(handoff(raw)["open_positions"]) == len(module.PaperJournal().list_open()) == 1
    else:
        with pytest.raises(ValueError): handoff(raw)
    with pytest.raises(OSError): journal.flush()


def test_manual_publication_failure_preserves_prior_state_and_pending_evidence(tmp_path, monkeypatch):
    import app.trading_core.perp_manual_state_store as native
    module, journal = actual_journal(tmp_path)
    store = ManualPerpStateStore(tmp_path / "manual.json")
    store.save(plans=[], setup_history=[])
    before = store.path.read_bytes()
    open_actual(journal)
    path = coordinator(tmp_path, {"manual": "fixture-one"})

    def fail(*_args): raise OSError("fixture replace denied")

    monkeypatch.setattr(native.os, "replace", fail)
    args = {"writer": "manual", "incarnation": "fixture-one", "operation": "manual-snapshot",
            "payload": PAYLOAD, "mutation": lambda: store.save(plans=[{"fixture_journal_id": journal.list_open()[0]["trade_id"]}], setup_history=[])}
    with pytest.raises(OSError): run_fixture_writer(path, **args)
    assert store.path.read_bytes() == before and store.pending_path.exists()
    with pytest.raises(ManualPerpStateError): ManualPerpStateStore(store.path).load()
    with pytest.raises(ValueError): run_fixture_writer(path, **args)
    assert len(module.PaperJournal().list_open()) == 1
    assert close_fixture_writers(path, {"manual": "fixture-one"})["status"] == "INCOMPLETE"


@pytest.mark.parametrize("phase", ["before_admission", "after_mutation", "after_ack", "during_append"])
def test_actual_journal_abrupt_process_restart(tmp_path, phase):
    path = coordinator(tmp_path)
    module, journal = actual_journal(tmp_path)
    prefix = b""
    if phase == "during_append":
        open_actual(journal, "ETH")
        prefix = module.JOURNAL_PATH.read_bytes()
    code = """
import os,sys
from pathlib import Path
from test_hyperliquid_paper_handoff import actual_journal,open_actual
from app.services.paper_writer_fixture import run_fixture_writer
module,journal=actual_journal(Path(sys.argv[2]))
if sys.argv[3]=='during_append':
 def partial(handle,text):
  handle.write(text[:len(text)//2]);handle.flush();os.fsync(handle.fileno());os._exit(61)
 module.write_flushed=partial
run_fixture_writer(sys.argv[1],writer='journal',incarnation='fixture-one',operation='manual-BTC-1',payload=sys.argv[4],
 mutation=lambda:open_actual(journal),fault=lambda at:os._exit(61) if at==sys.argv[3] else None)
"""
    result = subprocess.run([sys.executable, "-c", code, str(path), str(tmp_path), phase, PAYLOAD], timeout=15, check=False)
    assert result.returncode == 61
    args = {"writer": "journal", "incarnation": "fixture-one", "operation": "manual-BTC-1",
            "payload": PAYLOAD, "mutation": lambda: open_actual(module.PaperJournal())}
    if phase in ("after_mutation", "during_append"):
        with pytest.raises(ValueError): run_fixture_writer(path, **args)
    else:
        run_fixture_writer(path, **args)
        run_fixture_writer(path, **args)
    raw = module.JOURNAL_PATH.read_bytes()
    if phase == "during_append":
        assert raw.startswith(prefix) and [p["symbol"] for p in module.PaperJournal().list_open()] == ["ETH"]
        with pytest.raises(ValueError): handoff(raw)
        with pytest.raises(OSError): module.PaperJournal().flush()
    else:
        assert len(handoff(raw)["open_positions"]) == 1
    expected = "INCOMPLETE" if phase in ("after_mutation", "during_append") else "DRAINED_FIXTURE_ONLY"
    assert close_fixture_writers(path, {"journal": "fixture-one"})["status"] == expected


def test_concurrent_same_operation_never_duplicates_actual_entry(tmp_path):
    path = coordinator(tmp_path)
    module, journal = actual_journal(tmp_path)
    entered, release = Event(), Event()

    def write():
        entered.set()
        assert release.wait(5)
        open_actual(journal)

    args = {"writer": "journal", "incarnation": "fixture-one", "operation": "manual-BTC-1", "payload": PAYLOAD}
    with ThreadPoolExecutor(2) as pool:
        first = pool.submit(run_fixture_writer, path, **args, mutation=write)
        assert entered.wait(5)
        try:
            with pytest.raises(ValueError): run_fixture_writer(path, **args, mutation=lambda: pytest.fail("Duplicate callback"))
        finally: release.set()
        first.result(timeout=10)
    assert len(handoff(module.JOURNAL_PATH.read_bytes())["open_positions"]) == 1


def test_stale_prices_leave_source_positions_and_shutdown_incomplete(tmp_path):
    module, journal = actual_journal(tmp_path)
    open_actual(journal)
    source = module.JOURNAL_PATH.read_bytes()
    path = tmp_path / "ledger.sqlite"
    create_fixture_ledger(path, handoff(source)["open_positions"])
    account(path)
    stopped = []
    result = isolated_shutdown(path, "fixture-day", {"BTC": {"price": "104", "observed_at": STAMP,
                                                            "verified": True, "source_id": "fixture"}},
                               now=STAMP + 31, max_age=30, quiesce=lambda: True, drain=lambda: True,
                               stop_owned=lambda: stopped.append(True),
                               report_options={"day": "2026-10-23", "timezone": "UTC", "currency": "USD"})
    assert result["outcome"] == "INCOMPLETE" and stopped == []
    assert module.JOURNAL_PATH.read_bytes() == source and len(module.PaperJournal().list_open()) == 1
    with sqlite3.connect(path) as db: assert db.execute("SELECT COUNT(*) FROM exits").fetchone()[0] == 0


def test_actual_risk_control_store_corruption_blocks_fixture_entries(tmp_path):
    module = source_module("backend/app/services/paper_risk_controls.py", "paper_risk_controls")
    store = module.PaperRiskControlStore(tmp_path / "risk.json")
    store.save()
    store.path.write_text('{"kill_switch":false,"session_net_r":NaN}', encoding="utf-8")
    recovered = module.PaperRiskControlStore(store.path)
    assert recovered.reliable is False
    with pytest.raises(ValueError):
        validate_fixture_entry(symbol="BTC", side="LONG", risk_usd="1", manual_confirmation=True,
                               quote={"symbol": "BTC", "price": "100", "observed_at": STAMP,
                                      "verified": True, "source_id": "fixture"}, now=STAMP,
                               open_positions=[], session_net_r=0, kill_switch=False,
                               controls_reliable=recovered.reliable)
