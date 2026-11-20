import json
import sqlite3
import subprocess
import sys

import pytest
from app.services.daily_paper_liquidation import liquidate
from test_daily_paper_liquidation import fixture


@pytest.mark.parametrize("phase", ["before_exit", "after_exit", "before_commit", "after_commit"])
def test_abrupt_process_exit_and_restart(tmp_path, phase):
    path, quotes = fixture(tmp_path)
    script = ("import os,sys,json;from app.services.daily_paper_liquidation import liquidate;"
              "liquidate(sys.argv[1],'s',json.loads(sys.argv[2]),now=100,max_age=10,"
              "fault=lambda at:os._exit(23) if at==sys.argv[3] else None)")
    result = subprocess.run([sys.executable, "-c", script, str(path), json.dumps(quotes), phase],
                            timeout=10, check=False)
    assert result.returncode == 23
    report = liquidate(path, "s", quotes, now=100, max_age=10)
    assert report["closed_n"] == 1
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT COUNT(*) FROM exits").fetchone()[0] == 1
        assert db.execute("SELECT COUNT(*) FROM report_history").fetchone()[0] == 1


def test_report_revisions_preserved_and_corruption_refused(tmp_path):
    path, quotes = fixture(tmp_path)
    first = liquidate(path, "s", {}, now=100, max_age=10)
    liquidate(path, "s", quotes, now=100, max_age=10)
    with sqlite3.connect(path) as db:
        rows = db.execute("SELECT body FROM report_history ORDER BY revision").fetchall()
        assert len(rows) == 2 and json.loads(rows[0][0]) == first
        db.execute("UPDATE report_history SET body='{}' WHERE revision=1")
    with pytest.raises(ValueError, match="lineage"):
        liquidate(path, "s", quotes, now=100, max_age=10)


def test_explicit_currency_sizing_costs_and_rounding(tmp_path):
    path, quotes = fixture(tmp_path)
    with sqlite3.connect(path) as db:
        p = json.loads(db.execute("SELECT body FROM positions").fetchone()[0])
        p.update(quantity="0.125", currency="USD")
        db.execute("UPDATE positions SET body=?", (json.dumps(p),))
    report = liquidate(path, "s", quotes, now=100, max_age=10)
    assert report["currency_totals_exact"] == {"USD": "0.4925000"}
    assert report["currency_display_2dp_half_even"] == {"USD": "0.49"}
    assert report["currency_unavailable_n"] == 0
