import sqlite3

import pytest
from app.services.paper_cash_evidence import (
    append_cash_fixture,
    derive_fixture_realizations,
)
from test_durable_partial_shutdown import fixture


def test_cash_retry_conflict_and_corruption(tmp_path):
    path, _ = fixture(tmp_path)
    event = {"id": "opening", "kind": "OPENING", "currency": "USD", "amount": "100",
             "timestamp": "2026-10-23T00:00:00-05:00", "source_digest": "fixture-source"}
    append_cash_fixture(path, event)
    append_cash_fixture(path, event)
    with pytest.raises(ValueError):
        append_cash_fixture(path, {**event, "amount": "200"})
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT COUNT(*) FROM cash_evidence").fetchone()[0] == 1
        db.execute("UPDATE cash_evidence SET body='{}'")
    with pytest.raises(ValueError):
        append_cash_fixture(path, {**event, "id": "next"})


def test_full_partial_finalization_not_counted_twice(tmp_path):
    from decimal import Decimal

    from app.services.daily_paper_liquidation import append_partial_fixture
    path, fill = fixture(tmp_path)
    fill.update(quantity="1", session_id="s")
    append_partial_fixture(path, "t", fill)
    events = derive_fixture_realizations(path)
    assert len(events) == 1
    assert Decimal(events[0]["amount"]) == Decimal("1.94")
