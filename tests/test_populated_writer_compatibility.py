import hashlib
import json
import subprocess
import sys
from datetime import timedelta

import pytest
from app.investment.paper_book import PaperBook
from app.services.paper_writer_fixture import (
    close_fixture_writers,
    provision_fixture_writers,
    run_fixture_writer,
)
from test_durable_partial_shutdown import fixture
from test_prediction_accounting_completeness import book, journal
from test_prediction_entry_window import NOW, candidate


@pytest.mark.parametrize("interrupted", [False, True])
def test_populated_investment_actual_writer_does_not_duplicate(tmp_path, interrupted):
    path, _ = fixture(tmp_path)
    provision_fixture_writers(path, {"investment": "one"})
    state, ledger = tmp_path / "book.json", tmp_path / "book.jsonl"
    book = PaperBook(cash=100, state_path=state, ledger_path=ledger)
    intent = b'{"action":"research_buy","symbol":"FIXTURE","price":10,"usd":25}'
    calls = []
    def mutation():
        calls.append(1)
        book.research_buy("FIXTURE", 10, 25, reason="offline-fixture")
        if interrupted:
            raise OSError("after actual fixture store commit before coordinator acknowledgement")
    args = {"writer": "investment", "incarnation": "one", "operation": "buy-once",
            "payload": hashlib.sha256(intent).hexdigest(), "mutation": mutation}
    if interrupted:
        with pytest.raises(OSError):
            run_fixture_writer(path, **args)
        with pytest.raises(ValueError):
            run_fixture_writer(path, **args)
        assert close_fixture_writers(path, {"investment": "one"})["status"] == "INCOMPLETE"
    else:
        run_fixture_writer(path, **args)
        run_fixture_writer(path, **args)
        assert close_fixture_writers(path, {"investment": "one"})["status"] == "DRAINED_FIXTURE_ONLY"
    recovered = PaperBook.load(state, ledger_path=ledger)
    assert recovered.cash == 75
    assert recovered.positions["FIXTURE"].shares == 2.5
    assert len(recovered.fills) == 1 and calls == [1]
    assert len([json.loads(line) for line in ledger.read_text().splitlines()]) == 1


@pytest.mark.parametrize("interrupted", [False, True])
def test_actual_prediction_close_committed_once_across_ack_gap(tmp_path, interrupted):
    path, _ = fixture(tmp_path)
    provision_fixture_writers(path, {"prediction": "one"})
    store = journal(tmp_path)
    opened = store.open_from_evaluation(candidate(), now=NOW)
    before = store.journal_path.read_bytes()
    calls = []

    def mutation():
        calls.append(1)
        store.close_from_orderbook(orderbook=book(), exit_reason="OFFLINE_FIXTURE",
                                   now=NOW + timedelta(minutes=1))
        if interrupted:
            raise OSError("committed fixture close; acknowledgement interrupted")

    args = {"writer": "prediction", "incarnation": "one", "operation": "close-once",
            "payload": hashlib.sha256(b"fixed-fixture-close-intent").hexdigest(),
            "mutation": mutation}
    if interrupted:
        with pytest.raises(OSError):
            run_fixture_writer(path, **args)
        with pytest.raises(ValueError):
            run_fixture_writer(path, **args)
    else:
        run_fixture_writer(path, **args)
        run_fixture_writer(path, **args)
    recovered = journal(tmp_path)
    rows = recovered._rows(recovered.journal_path)
    assert recovered.journal_path.read_bytes().startswith(before)
    assert len(rows) == 2 and calls == [1]
    assert rows[1]["trade_id"] == opened["trade_id"]
    assert rows[1]["event"] == "close" and rows[1]["net_pnl_dollars"] is not None
    assert recovered.open_trade() is None
    expected = "INCOMPLETE" if interrupted else "DRAINED_FIXTURE_ONLY"
    assert close_fixture_writers(path, {"prediction": "one"})["status"] == expected


@pytest.mark.parametrize("phase", ["before_admission", "after_mutation", "after_ack"])
def test_actual_investment_abrupt_commit_restart(tmp_path, phase):
    path, _ = fixture(tmp_path)
    provision_fixture_writers(path, {"investment": "one"})
    state, ledger = tmp_path / "book.json", tmp_path / "book.jsonl"
    code = """
import os, sys
from pathlib import Path
from app.investment.paper_book import PaperBook
from app.services.paper_writer_fixture import run_fixture_writer
book = PaperBook(cash=100, state_path=Path(sys.argv[2]), ledger_path=Path(sys.argv[3]))
run_fixture_writer(sys.argv[1], writer='investment', incarnation='one',
    operation='buy-once', payload='a'*64,
    mutation=lambda: book.research_buy('FIXTURE',10,25,reason='offline-fixture'),
    fault=lambda phase: os._exit(43) if phase==sys.argv[4] else None)
"""
    result = subprocess.run([sys.executable, "-c", code, str(path), str(state), str(ledger), phase],
                            timeout=10, check=False)
    assert result.returncode == 43
    # Fresh instance reconstructs only the committed fixture state.
    recovered = PaperBook.load(state, ledger_path=ledger) if state.exists() else PaperBook(
        cash=100, state_path=state, ledger_path=ledger)
    args = {"writer": "investment", "incarnation": "one", "operation": "buy-once",
            "payload": "a" * 64,
            "mutation": lambda: recovered.research_buy("FIXTURE", 10, 25, reason="offline-fixture")}
    if phase == "after_mutation":
        with pytest.raises(ValueError):
            run_fixture_writer(path, **args)
    else:
        run_fixture_writer(path, **args)
        run_fixture_writer(path, **args)
    persisted = PaperBook.load(state, ledger_path=ledger)
    assert persisted.cash == 75 and persisted.positions["FIXTURE"].shares == 2.5
    assert len(persisted.fills) == len(ledger.read_text().splitlines()) == 1
    expected = "INCOMPLETE" if phase == "after_mutation" else "DRAINED_FIXTURE_ONLY"
    assert close_fixture_writers(path, {"investment": "one"})["status"] == expected

