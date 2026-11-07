import hashlib

import pytest
from app.services.paper_writer_fixture import (
    close_fixture_writers,
    provision_fixture_writers,
    reconcile_external_fixture,
    run_fixture_writer,
)
from test_durable_partial_shutdown import fixture


def test_committed_unacked_file_can_reconcile_without_reexecution(tmp_path):
    path, _ = fixture(tmp_path)
    provision_fixture_writers(path, {"manual": "one"})
    target = tmp_path / "manual.json"
    data = b'{"version":1,"positions":[]}'
    payload = hashlib.sha256(data).hexdigest()
    calls = []
    def mutation():
        calls.append(1)
        target.write_bytes(data)
        raise OSError("fixture crash after publication")
    args = {"writer": "manual", "incarnation": "one", "operation": "save", "payload": payload}
    with pytest.raises(OSError):
        run_fixture_writer(path, **args, mutation=mutation)
    assert close_fixture_writers(path, {"manual": "one"})["status"] == "INCOMPLETE"
    reconcile_external_fixture(path, root=tmp_path, relative_file="manual.json", **args)
    run_fixture_writer(path, **args, mutation=mutation)
    assert calls == [1]
    assert close_fixture_writers(path, {"manual": "one"})["status"] == "DRAINED_FIXTURE_ONLY"


def test_conflicting_external_bytes_do_not_ack(tmp_path):
    path, _ = fixture(tmp_path)
    provision_fixture_writers(path, {"manual": "one"})
    target = tmp_path / "manual.json"
    target.write_bytes(b"wrong")
    with pytest.raises(ValueError):
        reconcile_external_fixture(path, root=tmp_path, relative_file="manual.json", writer="manual",
                                   incarnation="one", operation="save", payload="a" * 64)


def test_actual_manual_store_at_disposable_path(tmp_path):
    import json
    import os

    from app.trading_core.perp_manual_state_store import (
        STATE_VERSION,
        ManualPerpStateStore,
    )
    path, _ = fixture(tmp_path)
    provision_fixture_writers(path, {"manual": "one"})
    store = ManualPerpStateStore(tmp_path / "manual-state.json")
    encoded = (json.dumps({"version": STATE_VERSION, "plans": [], "setup_history": []},
                          sort_keys=True, separators=(",", ":")) + os.linesep).encode()
    digest = hashlib.sha256(encoded).hexdigest()
    run_fixture_writer(path, writer="manual", incarnation="one", operation="save", payload=digest,
                       mutation=lambda: store.save(plans=[], setup_history=[]))
    assert store.path.read_bytes() == encoded
    assert store.load()["plans"] == []
    assert close_fixture_writers(path, {"manual": "one"})["status"] == "DRAINED_FIXTURE_ONLY"


def test_actual_investment_store_at_disposable_path(tmp_path):
    import json
    import os

    from app.investment.paper_book import PaperBook
    path, _ = fixture(tmp_path)
    provision_fixture_writers(path, {"investment": "one"})
    book = PaperBook(cash=100, state_path=tmp_path / "book.json", ledger_path=tmp_path / "book.jsonl")
    data = {"cash": book.cash, "realized_pnl": book.realized_pnl, "peak_equity": book.peak_equity,
            "positions": {}, "orders": [], "fills": [], "benchmark": book.benchmark.__dict__}
    encoded = json.dumps(data, indent=2, allow_nan=False).replace("\n", os.linesep).encode()
    args = {"writer": "investment", "incarnation": "one", "operation": "snapshot", "payload": hashlib.sha256(encoded).hexdigest()}
    run_fixture_writer(path, **args, mutation=book.save)
    assert book.state_path.read_bytes() == encoded
    assert PaperBook.load(book.state_path, ledger_path=tmp_path / "book.jsonl").cash == 100
    assert close_fixture_writers(path, {"investment": "one"})["status"] == "DRAINED_FIXTURE_ONLY"


def test_actual_prediction_append_at_disposable_path(tmp_path):
    import json

    from app.prediction.paper_engine import PredictionPaperJournal
    path, _ = fixture(tmp_path)
    provision_fixture_writers(path, {"prediction": "one"})
    journal = PredictionPaperJournal(journal_path=tmp_path / "prediction.jsonl", candidate_path=tmp_path / "candidates.jsonl")
    row = {"event": "fixture_evidence", "operation_id": "test-only"}
    digest = hashlib.sha256((json.dumps(row, separators=(",", ":"), allow_nan=False) + "\n").encode()).hexdigest()
    args = {"writer": "prediction", "incarnation": "one", "operation": "append", "payload": digest}
    run_fixture_writer(path, **args, mutation=lambda: journal._append(journal.journal_path, row))
    run_fixture_writer(path, **args, mutation=lambda: journal._append(journal.journal_path, row))
    assert journal._rows(journal.journal_path) == [row]
    assert close_fixture_writers(path, {"prediction": "one"})["status"] == "DRAINED_FIXTURE_ONLY"
