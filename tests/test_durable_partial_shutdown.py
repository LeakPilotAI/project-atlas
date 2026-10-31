import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal

import pytest
from app.services.daily_paper_liquidation import (
    append_partial_fixture,
    create_fixture_ledger,
    liquidate,
)


def fixture(tmp_path):
    path = tmp_path / "partial.sqlite"
    create_fixture_ledger(path, [{"trade_id": "t", "symbol": "T", "side": "LONG", "quantity": "1",
                                 "currency": "USD", "actual_entry_price": "100", "risk_price": "2",
                                 "fees_bps": "2", "slippage_bps": "1", "opened_at": 1}])
    fill = {"schema": "PAPER_PARTIAL_FILL_V1", "trade_id": "t", "fill_id": "f",
            "quantity": "0.25", "price": "102", "timestamp": 2}
    return path, fill


@pytest.mark.parametrize("phase", ["before_partial", "before_commit", "after_commit"])
def test_partial_retry_then_remaining_shutdown(tmp_path, phase):
    path, fill = fixture(tmp_path)
    def fault(at):
        if at == phase:
            raise OSError("fixture interruption")
    with pytest.raises(OSError):
        append_partial_fixture(path, "t", fill, fault=fault)
    append_partial_fixture(path, "t", fill)
    quotes = {"T": {"price": "104", "observed_at": 3, "verified": True, "source_id": "fixture"}}
    with ThreadPoolExecutor(2) as pool:
        reports = list(pool.map(lambda _: liquidate(path, "s", quotes, now=3, max_age=1), range(2)))
    assert reports[0] == reports[1]
    assert Decimal(reports[0]["currency_totals_exact"]["USD"]) == Decimal("3.44")
    assert Decimal(reports[0]["realized_pnl_r"]) == Decimal("1.72")
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT COUNT(*) FROM partial_fills").fetchone()[0] == 1
        row = json.loads(db.execute("SELECT body FROM exits").fetchone()[0])
        assert row["currency_accounting"]["shutdown_quantity"] == "0.75"
    append_partial_fixture(path, "t", fill)  # acknowledgement retry after quiescence
    with pytest.raises(ValueError):
        append_partial_fixture(path, "t", {**fill, "fill_id": "new"})
