import sqlite3
import subprocess
import sys
from decimal import Decimal

import pytest
from app.services.daily_paper_liquidation import append_partial_fixture, liquidate
from app.services.paper_bound_daily_report import publish_bound_daily
from app.services.paper_cash_evidence import append_cash_fixture
from test_durable_partial_shutdown import fixture


def setup(path):
    append_cash_fixture(path, {"id": "opening", "kind": "OPENING", "currency": "USD", "amount": "100",
                               "timestamp": "1970-01-01T00:00:00+00:00", "source_digest": "fixture"})


def test_cross_midnight_partial_and_final_are_separate(tmp_path):
    path, fill = fixture(tmp_path)
    setup(path)
    fill["timestamp"] = 86399
    append_partial_fixture(path, "t", fill)
    liquidate(path, "s", {"T": {"price": "104", "observed_at": 86401, "verified": True, "source_id": "fixture"}},
              now=86401, max_age=1)
    report = publish_bound_daily(path, day="1970-01-01", timezone="UTC", currency="USD")
    assert Decimal(report["realized_net"]) == Decimal("0.485")
    assert Decimal(report["closing_cash"]) == Decimal("100.485")
    assert report == publish_bound_daily(path, day="1970-01-01", timezone="UTC", currency="USD")
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT COUNT(*) FROM bound_daily").fetchone()[0] == 1


@pytest.mark.parametrize("phase", ["before_report", "before_commit", "after_commit"])
def test_report_abrupt_crash_retry(tmp_path, phase):
    path, _ = fixture(tmp_path)
    setup(path)
    script = ("import os,sys;from app.services.paper_bound_daily_report import publish_bound_daily;"
              "publish_bound_daily(sys.argv[1],day='1970-01-01',timezone='UTC',currency='USD',"
              "fault=lambda at:os._exit(31) if at==sys.argv[2] else None)")
    result = subprocess.run([sys.executable, "-c", script, str(path), phase], timeout=10, check=False)
    assert result.returncode == 31
    report = publish_bound_daily(path, day="1970-01-01", timezone="UTC", currency="USD")
    assert report["status"] == "INCOMPLETE"
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT COUNT(*) FROM bound_daily").fetchone()[0] == 1
