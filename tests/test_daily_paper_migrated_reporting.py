"""Supplied legacy clocks reach fixture historical reporting without becoming authority."""
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from app.services.daily_paper_fixture_adapter import (
    adapt_legacy_rows,
    migrate_fixture_rows,
)
from app.services.daily_paper_liquidation import create_fixture_ledger, liquidate
from app.services.paper_bound_daily_report import publish_bound_daily
from app.services.paper_cash_evidence import append_cash_fixture
from app.services.paper_historical_inventory import historical_fixture_inventory
from test_daily_paper_fixture_adapter import row
from test_report_inventory import inventory


@pytest.mark.parametrize("stamp", ["2026-10-23T09:30:00.123456-04:00",
                                  "2026-11-01T01:30:00-04:00", "2026-11-01T01:30:00-05:00"])
def test_legacy_entry_clock_survives_migration(tmp_path, stamp):
    original = {**row(), "entry_timestamp": stamp}
    adapted = adapt_legacy_rows([original], currency="USD")[0]
    expected = int(datetime.fromisoformat(stamp).timestamp())
    assert adapted["opened_at"] == expected
    assert adapted["source_entry_timestamp"] == stamp
    path = tmp_path / "migrated.sqlite"
    create_fixture_ledger(path, [])
    migrate_fixture_rows(path, [original], currency="USD")
    before = historical_fixture_inventory(path, cutoff=expected)
    after = historical_fixture_inventory(path, cutoff=expected + 1)
    assert before["positions"] == []
    assert after["unresolved"] == ["a"]
    assert after["historical_availability_authenticated"] is False


@pytest.mark.parametrize("stamp", [None, "invalid", "2026-10-23T09:30:00"])
def test_supplied_unqualified_clock_is_not_replaced(stamp):
    with pytest.raises(ValueError):
        adapt_legacy_rows([{**row(), "entry_timestamp": stamp}], currency="USD")


def test_migrated_source_to_liquidation_cash_and_daily_report(tmp_path):
    stamp = "2026-10-23T13:30:00.123456+00:00"
    opened = int(datetime.fromisoformat(stamp).timestamp())
    path = tmp_path / "migrated.sqlite"
    create_fixture_ledger(path, [])
    source = [{**row(), "entry_timestamp": stamp}]
    migrate_fixture_rows(path, source, currency="USD")
    append_cash_fixture(path, {"id": "opening", "kind": "OPENING", "currency": "USD", "amount": "100",
                               "timestamp": "2026-10-23T00:00:00+00:00", "source_digest": "fixture-only"})
    liquidate(path, "fixture-day", {"TEST": {"price": "104", "observed_at": opened + 10,
                                            "verified": True, "source_id": "fixture"}},
              now=opened + 10, max_age=1)
    kwargs = {"day": "2026-10-23", "timezone": "UTC", "currency": "USD", "inventory": inventory(path)}
    report = publish_bound_daily(path, **kwargs)
    assert report["status"] == "CASH_RECONCILED_NOT_OPERATIONAL_ACCEPTANCE"
    assert report["unresolved"] == [] and Decimal(report["realized_net"]) == Decimal("0.4925")
    assert Decimal(report["closing_cash"]) == Decimal("100.4925")
    assert report["independently_authenticated"] is report["production_authorized"] is False
    assert publish_bound_daily(path, **kwargs) == report


def test_missing_legacy_clock_still_refuses_historical_report(tmp_path):
    path = tmp_path / "unknown.sqlite"
    create_fixture_ledger(path, adapt_legacy_rows([row()], currency="USD"))
    with pytest.raises(ValueError, match="timestamp"):
        historical_fixture_inventory(path, cutoff=int(datetime(2026, 10, 24, tzinfo=UTC).timestamp()))
