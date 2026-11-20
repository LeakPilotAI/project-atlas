"""Actual investment persistence at disposable paths; observations never clear uncertainty."""
import hashlib
import subprocess
import sys

import pytest
from app.investment.paper_book import PaperBook
from app.investment.paper_book_audit import audit_fill_subset
from app.services.paper_writer_fixture import (
    close_fixture_writers,
    provision_fixture_writers,
    run_fixture_writer,
)
from test_durable_partial_shutdown import fixture


@pytest.mark.parametrize("boundary", ["before_snapshot", "after_snapshot"])
def test_split_publication_is_detected_without_blind_replay(tmp_path, boundary):
    path, _ = fixture(tmp_path)
    provision_fixture_writers(path, {"investment": "one"})
    state, ledger = tmp_path / "book.json", tmp_path / "book.jsonl"
    PaperBook(cash=100, state_path=state, ledger_path=ledger).save()
    original = state.read_bytes()
    script = """
import os,sys
from pathlib import Path
from app.investment.paper_book import PaperBook
from app.services.paper_writer_fixture import run_fixture_writer
book=PaperBook.load(Path(sys.argv[2]),ledger_path=Path(sys.argv[3]))
if sys.argv[4]=='before_snapshot':
    book.save=lambda:os._exit(53)
run_fixture_writer(sys.argv[1],writer='investment',incarnation='one',operation='buy',payload='a'*64,
    mutation=lambda:book.research_buy('FIXTURE',10,25,reason='offline-fixture'),
    fault=lambda phase:os._exit(53) if phase=='after_mutation' else None)
"""
    result = subprocess.run([sys.executable, "-c", script, str(path), str(state), str(ledger), boundary],
                            timeout=10, check=False)
    assert result.returncode == 53
    snapshot, entries = state.read_bytes(), ledger.read_bytes()
    audit = audit_fill_subset(snapshot, entries,
                             expected_snapshot_sha256=hashlib.sha256(snapshot).hexdigest(),
                             expected_ledger_sha256=hashlib.sha256(entries).hexdigest())
    assert audit["ledger_fill_n"] == 1
    if boundary == "before_snapshot":
        assert snapshot == original
        assert audit["status"] == "REQUIRES_RECONCILIATION"
        assert audit["ledger_payloads_missing_from_snapshot"] == 1
    else:
        assert audit["status"] == "MATCHED_RECORDED_FILL_SUBSET"
        assert audit["snapshot_fill_n"] == 1
    assert audit["full_book_consistency_established"] is False
    assert audit["startup_authorized"] is audit["recovery_authorized"] is False
    for _ in range(2):
        with pytest.raises(ValueError):
            run_fixture_writer(path, writer="investment", incarnation="one", operation="buy",
                               payload="a" * 64, mutation=lambda: pytest.fail("Unsafe callback replay"))
    assert close_fixture_writers(path, {"investment": "one"})["status"] == "INCOMPLETE"
    assert state.read_bytes() == snapshot and ledger.read_bytes() == entries
