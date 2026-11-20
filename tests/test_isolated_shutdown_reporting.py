"""Fixture-only shutdown cannot substitute priced exits for accounting/report proof."""
import sqlite3

import pytest
from app.services.daily_paper_fixture_adapter import isolated_shutdown
from app.services.daily_paper_liquidation import liquidate
from test_bound_daily_report import setup
from test_durable_partial_shutdown import fixture


def test_missing_daily_report_contract_never_stops_or_claims_complete(tmp_path):
    path, _ = fixture(tmp_path)
    stopped = []
    report = isolated_shutdown(path, "s", {"T": {"price": "104", "observed_at": 3,
                                                "verified": True, "source_id": "fixture"}},
                               now=3, max_age=1, quiesce=lambda: True, drain=lambda: True,
                               stop_owned=lambda: stopped.append(True) or True)
    assert report["outcome"] == "INCOMPLETE"
    assert stopped == []


def options():
    return {"day": "1970-01-01", "timezone": "UTC", "currency": "USD"}


def quotes():
    return {"T": {"price": "104", "observed_at": 3, "verified": True, "source_id": "fixture"}}


@pytest.mark.parametrize("stop_confirmed", [True, False])
def test_daily_accounting_precedes_owned_fixture_stop_and_retries(tmp_path, stop_confirmed):
    path, _ = fixture(tmp_path)
    setup(path)
    observed = []

    def stop():
        with sqlite3.connect(path) as db:
            assert db.execute("SELECT COUNT(*) FROM bound_daily").fetchone()[0] == 1
        observed.append(True)
        return stop_confirmed

    for _ in range(2):
        result = isolated_shutdown(path, "s", quotes(), now=3, max_age=1,
                                   quiesce=lambda: True, drain=lambda: True,
                                   stop_owned=stop, report_options=options())
        assert result["outcome"] == ("COMPLETE_FIXTURE_ONLY" if stop_confirmed else "INCOMPLETE")
        assert result["production_authorized"] is result["recovery_authorized"] is False
        assert result["audit"]["source_completeness_independently_proven"] is False
    assert observed == [True, True]
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT COUNT(*) FROM exits").fetchone()[0] == 1
        assert db.execute("SELECT COUNT(*) FROM bound_daily").fetchone()[0] == 1


@pytest.mark.parametrize("damage", ["cash", "report-write", "exit-accounting"])
def test_accounting_or_publication_failure_never_reaches_stop(tmp_path, damage):
    path, _ = fixture(tmp_path)
    setup(path)
    liquidate(path, "s", quotes(), now=3, max_age=1)
    with sqlite3.connect(path) as db:
        if damage == "cash":
            db.execute("DELETE FROM cash_evidence")
        elif damage == "report-write":
            db.execute("CREATE TABLE bound_daily(id INTEGER PRIMARY KEY,body TEXT,parent TEXT,digest TEXT)")
            db.execute("CREATE TRIGGER deny BEFORE INSERT ON bound_daily BEGIN SELECT RAISE(ABORT,'fixture denial'); END")
        else:
            db.execute("UPDATE exits SET body=json_set(body,'$.currency_accounting.net','999')")
    stopped = []
    with pytest.raises((ValueError, sqlite3.DatabaseError)):
        isolated_shutdown(path, "s", quotes(), now=3, max_age=1, quiesce=lambda: True,
                          drain=lambda: True, stop_owned=lambda: stopped.append(True),
                          report_options=options())
    assert stopped == []


def test_report_for_another_day_cannot_substitute_for_shutdown_accounting(tmp_path):
    path, _ = fixture(tmp_path)
    stopped = []
    result = isolated_shutdown(path, "s", quotes(), now=3, max_age=1,
                               quiesce=lambda: True, drain=lambda: True,
                               stop_owned=lambda: stopped.append(True),
                               report_options={**options(), "day": "1969-12-31"})
    assert result["outcome"] == "INCOMPLETE"
    assert result["reason"] == "REPORT_SESSION_DAY_MISMATCH" and stopped == []
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT COUNT(*) FROM exits").fetchone()[0] == 0
