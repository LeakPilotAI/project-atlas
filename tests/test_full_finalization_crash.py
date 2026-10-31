import json
import sqlite3
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

import pytest
from app.services.daily_paper_liquidation import append_partial_fixture, liquidate
from app.services.paper_cash_evidence import derive_fixture_realizations
from test_durable_partial_shutdown import fixture


@pytest.mark.parametrize("phase", ["before_partial", "after_partial", "after_finalization", "before_commit", "after_commit"])
def test_full_finalization_abrupt_restart(tmp_path, phase):
    path, fill = fixture(tmp_path)
    fill.update(quantity="1", session_id="s")
    script = ("import os,sys,json;from app.services.daily_paper_liquidation import append_partial_fixture;"
              "append_partial_fixture(sys.argv[1],'t',json.loads(sys.argv[2]),"
              "fault=lambda at:os._exit(37) if at==sys.argv[3] else None)")
    result = subprocess.run([sys.executable, "-c", script, str(path), json.dumps(fill), phase], timeout=10, check=False)
    assert result.returncode == 37
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT COUNT(*) FROM exits").fetchone()[0] == int(phase == "after_commit")
    with ThreadPoolExecutor(2) as pool:
        list(pool.map(lambda _: append_partial_fixture(path, "t", fill), range(2)))
    assert len(derive_fixture_realizations(path)) == 1
    report = liquidate(path, "s", {}, now=3, max_age=1)
    assert report["closed_n"] == 1


def test_missing_final_fill_cannot_claim_closed(tmp_path):
    path, fill = fixture(tmp_path)
    fill.update(quantity="1", session_id="s")
    append_partial_fixture(path, "t", fill)
    with sqlite3.connect(path) as db:
        db.execute("DELETE FROM partial_fills")
    with pytest.raises(ValueError, match="Finalization"):
        derive_fixture_realizations(path)
