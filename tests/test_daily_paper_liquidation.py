import sqlite3
from concurrent.futures import ThreadPoolExecutor

import pytest
from app.services.daily_paper_liquidation import create_fixture_ledger, liquidate


def fixture(tmp_path):
    path = tmp_path / "isolated.sqlite"
    create_fixture_ledger(path, [{"trade_id": "t", "symbol": "TEST", "side": "LONG",
                                 "actual_entry_price": "100", "risk_price": "2",
                                 "fees_bps": "2", "slippage_bps": "1"}])
    return path, {"TEST": {"price": "104", "observed_at": 100, "verified": True, "source_id": "fixture"}}


@pytest.mark.parametrize("phase", ["before_exit", "after_exit", "before_commit", "after_commit"])
def test_interrupted_transaction_retry_exactly_once(tmp_path, phase):
    path, quotes = fixture(tmp_path)
    def fault(at):
        if at == phase:
            raise OSError("fixture interruption")
    with pytest.raises(OSError):
        liquidate(path, "s", quotes, now=100, max_age=10, fault=fault)
    report = liquidate(path, "s", quotes, now=100, max_age=10)
    assert report["closed_n"] == 1 and report["realized_pnl_r"] == "1.9700"
    assert report == liquidate(path, "s", {}, now=200, max_age=10)
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT COUNT(*) FROM exits").fetchone()[0] == 1
        assert db.execute("SELECT stopped FROM control").fetchone()[0] == 1


def test_concurrent_shutdown_and_cross_session_no_duplicate(tmp_path):
    path, quotes = fixture(tmp_path)
    with ThreadPoolExecutor(3) as pool:
        reports = list(pool.map(lambda _: liquidate(path, "s", quotes, now=100, max_age=10), range(3)))
    assert reports[0] == reports[1] == reports[2]
    assert liquidate(path, "next", quotes, now=100, max_age=10)["closed_n"] == 0


def test_missing_evidence_retains_open_then_resolves(tmp_path):
    path, quotes = fixture(tmp_path)
    report = liquidate(path, "s", {}, now=100, max_age=10)
    assert not report["complete"] and report["closed_n"] == 0
    assert liquidate(path, "s", quotes, now=100, max_age=10)["complete"]
