from datetime import datetime

import pytest
from app.services.daily_paper_liquidation import append_partial_fixture, liquidate
from app.services.paper_daily_calendar import publish_daily_fixture
from test_durable_partial_shutdown import fixture


@pytest.mark.parametrize("day,hours", [("2026-03-08", 23), ("2026-11-01", 25)])
def test_dst_cash_report_preserves_equity_unknown(tmp_path, day, hours):
    path, _ = fixture(tmp_path)
    result = publish_daily_fixture(path, local_date=day, timezone="America/Chicago",
                                   evidence={"opening_cash": "100", "currency": "USD", "events": [], "unresolved": ["t"]})
    assert (datetime.fromisoformat(result["end_utc"]) - datetime.fromisoformat(result["start_utc"])).total_seconds() == hours * 3600
    assert result["ending_cash"] == "100" and result["total_equity"] is None
    assert result["shutdown"] == "INCOMPLETE"


def test_full_fill_atomic_finalization_and_retry(tmp_path):
    path, fill = fixture(tmp_path)
    fill.update(quantity="1", session_id="s")
    append_partial_fixture(path, "t", fill)
    append_partial_fixture(path, "t", fill)
    report = liquidate(path, "s", {}, now=3, max_age=1)
    assert report["complete"] and report["closed_n"] == 1
