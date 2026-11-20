import sqlite3
import subprocess
import sys

import pytest
from app.services.paper_writer_fixture import (
    close_fixture_writers,
    fixture_writer_operation,
    provision_fixture_writers,
)
from test_durable_partial_shutdown import fixture


@pytest.mark.parametrize("phase", ["before_admission", "after_admission", "after_mutation", "after_ack"])
def test_abrupt_writer_boundary(tmp_path, phase):
    path, _ = fixture(tmp_path)
    provision_fixture_writers(path, {"manual": "one"})
    marker = tmp_path / "external.txt"
    script = ("import os,sys;from pathlib import Path;from app.services.paper_writer_fixture import run_fixture_writer;"
              "run_fixture_writer(sys.argv[1],writer='manual',incarnation='one',operation='op',payload='a'*64,"
              "mutation=lambda:Path(sys.argv[2]).write_text('committed-fixture'),"
              "fault=lambda at:os._exit(43) if at==sys.argv[3] else None)")
    result = subprocess.run([sys.executable, "-c", script, str(path), str(marker), phase], timeout=10, check=False)
    assert result.returncode == 43
    drain = close_fixture_writers(path, {"manual": "one"})
    assert (drain["status"] == "INCOMPLETE") == (phase in ("after_admission", "after_mutation"))
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT COUNT(*) FROM writer_operations").fetchone()[0] == int(phase != "before_admission")
    assert marker.exists() == (phase in ("after_mutation", "after_ack"))


def test_payload_conflict_never_replays(tmp_path):
    path, _ = fixture(tmp_path)
    provision_fixture_writers(path, {"manual": "one"})
    args = {"writer": "manual", "incarnation": "one", "operation": "op", "payload": "a" * 64}
    fixture_writer_operation(path, **args)
    with pytest.raises(ValueError):
        fixture_writer_operation(path, **{**args, "payload": "b" * 64})


@pytest.mark.parametrize("phase", ["before_close_commit", "after_close_commit"])
def test_close_admission_abrupt_retry(tmp_path, phase):
    path, _ = fixture(tmp_path)
    provision_fixture_writers(path, {"manual": "one"})
    script = ("import os,sys;from app.services.paper_writer_fixture import close_fixture_writers;"
              "close_fixture_writers(sys.argv[1],{'manual':'one'},fault=lambda at:os._exit(47) if at==sys.argv[2] else None)")
    result = subprocess.run([sys.executable, "-c", script, str(path), phase], timeout=10, check=False)
    assert result.returncode == 47
    assert close_fixture_writers(path, {"manual": "one"})["status"] == "DRAINED_FIXTURE_ONLY"
