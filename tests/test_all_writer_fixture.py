import sqlite3

import pytest
from app.services.paper_writer_fixture import (
    close_fixture_writers,
    drain_fixture_writers,
    fixture_writer_operation,
    provision_fixture_writers,
    run_fixture_writer,
)
from test_durable_partial_shutdown import fixture


def test_pending_write_blocks_drain_and_retry_can_ack(tmp_path):
    path, _ = fixture(tmp_path)
    roster = {"manual": "one", "prediction": "two", "journal": "three", "investment": "four", "lifecycle": "five"}
    provision_fixture_writers(path, roster)
    args = {"writer": "manual", "incarnation": "one", "operation": "write-1", "payload": "a" * 64}
    fixture_writer_operation(path, **args)
    assert close_fixture_writers(path, roster)["status"] == "INCOMPLETE"
    with pytest.raises(ValueError):
        fixture_writer_operation(path, **{**args, "operation": "new"})
    fixture_writer_operation(path, **args, acknowledge=True)
    fixture_writer_operation(path, **args, acknowledge=True)
    assert close_fixture_writers(path, roster)["status"] == "DRAINED_FIXTURE_ONLY"


@pytest.mark.parametrize("damage", ["missing", "restart", "uncertain", "child-active"])
def test_missing_restarted_or_child_writer_never_clean(tmp_path, damage):
    path, _ = fixture(tmp_path)
    roster = {"parent": "p", "child": "c"}
    provision_fixture_writers(path, roster)
    if damage == "child-active":
        fixture_writer_operation(path, writer="child", incarnation="c", operation="pending", payload="a" * 64)
        assert close_fixture_writers(path, roster)["status"] == "INCOMPLETE"
        return
    with sqlite3.connect(path) as db:
        if damage == "missing":
            db.execute("DELETE FROM writer_roster WHERE id='child'")
        elif damage == "restart":
            db.execute("UPDATE writer_roster SET incarnation='new' WHERE id='child'")
        else:
            db.execute("UPDATE writer_roster SET uncertain=1 WHERE id='child'")
    with pytest.raises(ValueError):
        close_fixture_writers(path, roster)


def test_fixture_save_adapter_retains_ambiguous_failure(tmp_path):
    path, _ = fixture(tmp_path)
    roster = {"manual-save": "one"}
    provision_fixture_writers(path, roster)
    calls = []
    def mutation():
        calls.append("write")
        raise OSError("after external fixture write")
    args = {"writer": "manual-save", "incarnation": "one", "operation": "save", "payload": "a" * 64, "mutation": mutation}
    with pytest.raises(OSError):
        run_fixture_writer(path, **args)
    with pytest.raises(ValueError):
        run_fixture_writer(path, **args)
    assert calls == ["write"]
    assert close_fixture_writers(path, roster)["status"] == "INCOMPLETE"


def test_drain_timeout_never_clears_pending_then_ack_retry(tmp_path):
    path, _ = fixture(tmp_path)
    provision_fixture_writers(path, {"manual": "one"})
    args = {"writer": "manual", "incarnation": "one", "operation": "pending", "payload": "a" * 64}
    fixture_writer_operation(path, **args)
    result = drain_fixture_writers(path, {"manual": "one"}, timeout=0)
    assert result["status"] == "TIMED_OUT" and result["pending"] == ["pending"]
    fixture_writer_operation(path, **args, acknowledge=True)
    assert drain_fixture_writers(path, {"manual": "one"}, timeout=0)["status"] == "DRAINED_FIXTURE_ONLY"
