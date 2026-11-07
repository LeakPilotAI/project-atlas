import sqlite3
import subprocess
import sys
from decimal import Decimal

import pytest
from app.services.daily_paper_fixture_adapter import (
    adapt_legacy_rows,
    isolated_shutdown,
)
from app.services.daily_paper_liquidation import create_fixture_ledger, liquidate


def row(ident="a", side="LONG", size="0.125"):
    return {"event": "open", "trade_id": ident, "trade_type": "PAPER", "status": "open",
            "symbol": "TEST", "side": side, "actual_entry_price": "100", "risk_price": "2",
            "fees_bps": "2", "slippage_bps": "1", "position_size": size}


def test_multi_position_long_short_fractional_currency_parity(tmp_path):
    path = tmp_path / "fixture.sqlite"
    positions = adapt_legacy_rows([row(), row("b", "SHORT", "0.25")], currency="USD")
    create_fixture_ledger(path, positions)
    quotes = {"TEST": {"price": "104", "observed_at": 100, "verified": True, "source_id": "fixture"}}
    report = liquidate(path, "s", quotes, now=100, max_age=10)
    assert Decimal(report["currency_totals_exact"]["USD"]) == Decimal("-0.5225")
    assert report["currency_display_2dp_half_even"]["USD"] == "-0.52"
    assert report["closed_n"] == 2
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT COUNT(*) FROM exits").fetchone()[0] == 2


@pytest.mark.parametrize("change", ["partial", "conflict", "orphan"])
def test_ambiguous_legacy_rows_refuse(change):
    first = row()
    second = dict(first)
    if change == "partial":
        first["partial_close"] = True
    elif change == "conflict":
        second["position_size"] = "2"
    else:
        first["event"] = "close"
    with pytest.raises(ValueError):
        adapt_legacy_rows([first, second], currency="USD")


def test_shutdown_no_false_complete_and_no_stop_without_prices(tmp_path):
    path = tmp_path / "fixture.sqlite"
    create_fixture_ledger(path, adapt_legacy_rows([row()], currency="USD"))
    calls = []
    result = isolated_shutdown(path, "s", {}, now=100, max_age=10, quiesce=lambda: True,
                               drain=lambda: True, stop_owned=lambda: calls.append("stop"))
    assert result["outcome"] == "INCOMPLETE" and calls == []


def test_duplicate_legacy_rows_idempotent_and_closed_not_reimported():
    first = row()
    assert len(adapt_legacy_rows([first, first], currency="USD")) == 1
    with pytest.raises(ValueError):
        adapt_legacy_rows([first, {"event": "close", "trade_id": "a"}], currency="USD")


@pytest.mark.parametrize("phase", ["before_import", "before_commit", "after_commit"])
def test_migration_retry_after_interruption(tmp_path, phase):
    from app.services.daily_paper_fixture_adapter import migrate_fixture_rows
    path = tmp_path / "migration.sqlite"
    create_fixture_ledger(path, [])
    def fault(at):
        if at == phase:
            raise OSError("fixture interruption")
    with pytest.raises(OSError):
        migrate_fixture_rows(path, [row()], currency="USD", fault=fault)
    digest = migrate_fixture_rows(path, [row()], currency="USD")
    assert digest == migrate_fixture_rows(path, [row()], currency="USD")
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT COUNT(*) FROM positions").fetchone()[0] == 1
    with pytest.raises(ValueError):
        migrate_fixture_rows(path, [row(size="2")], currency="USD")


@pytest.mark.parametrize("phase", ["before_import", "before_commit", "after_commit"])
def test_abrupt_migration_restart(tmp_path, phase):
    from app.services.daily_paper_fixture_adapter import migrate_fixture_rows
    path = tmp_path / "abrupt.sqlite"
    create_fixture_ledger(path, [])
    script = ("import os,sys;from test_daily_paper_fixture_adapter import row;"
              "from app.services.daily_paper_fixture_adapter import migrate_fixture_rows;"
              "migrate_fixture_rows(sys.argv[1],[row()],currency='USD',"
              "fault=lambda at:os._exit(29) if at==sys.argv[2] else None)")
    result = subprocess.run([sys.executable, "-c", script, str(path), phase], timeout=10, check=False)
    assert result.returncode == 29
    migrate_fixture_rows(path, [row()], currency="USD")
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT COUNT(*) FROM positions").fetchone()[0] == 1
        assert db.execute("SELECT COUNT(*) FROM migration").fetchone()[0] == 1
