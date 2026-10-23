import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest
from app.services.daily_paper_liquidation import append_partial_fixture, liquidate
from app.services.paper_exit_audit import audit_fixture_exits
from test_durable_partial_shutdown import fixture


@pytest.mark.parametrize("damage", ["missing", "duplicate", "invalid"])
def test_ambiguous_admission_never_rewritten_as_quiescent(tmp_path, damage):
    path, _ = fixture(tmp_path)
    with sqlite3.connect(path) as db:
        if damage == "missing":
            db.execute("DELETE FROM control")
        elif damage == "duplicate":
            db.execute("INSERT INTO control VALUES(0)")
        else:
            db.execute("UPDATE control SET stopped=99")
    with pytest.raises(ValueError, match="admission"):
        liquidate(path, "s", {}, now=3, max_age=1)


def test_shutdown_waits_for_owned_transaction_then_refuses_new_fill(tmp_path):
    path, fill = fixture(tmp_path)
    entered, release = threading.Event(), threading.Event()
    def fault(phase):
        if phase == "before_commit":
            entered.set()
            if not release.wait(1):
                raise TimeoutError("Fixture release missing")
    with ThreadPoolExecutor(2) as pool:
        writer = pool.submit(append_partial_fixture, path, "t", fill, fault=fault)
        assert entered.wait(1)
        shutdown = pool.submit(liquidate, path, "s", {"T": {"price": "104", "observed_at": 3,
                               "verified": True, "source_id": "fixture"}}, now=3, max_age=1)
        release.set()
        writer.result()
        assert shutdown.result()["complete"]
    assert audit_fixture_exits(path)["reconciled"]
    with pytest.raises(ValueError, match="quiesced"):
        append_partial_fixture(path, "t", {**fill, "fill_id": "new"})
