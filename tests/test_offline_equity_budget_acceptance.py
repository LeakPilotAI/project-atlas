import sqlite3
from concurrent.futures import ThreadPoolExecutor

import pytest

from scripts.observation_runtime.r7e47ck_equities_budget import (
    EquitiesBudgetRefused,
    EquitiesObservationBudget,
)


def ledger(tmp_path, maximum=2):
    return EquitiesObservationBudget(tmp_path / "budget.sqlite", access_approved=True, max_attempts=maximum)


@pytest.mark.parametrize("statement", ["DELETE FROM budget", "UPDATE budget SET attempted=-1", "UPDATE budget SET attempted=4", "UPDATE budget SET attempted='bad'", "UPDATE budget SET max_attempts=3", "INSERT INTO budget VALUES(2,2,0)"])
def test_malformed_state_refuses_read_and_consume(tmp_path, statement):
    b=ledger(tmp_path)
    with sqlite3.connect(b.path) as db:
        db.execute(statement)
    with pytest.raises(EquitiesBudgetRefused): b.remaining()
    with pytest.raises(EquitiesBudgetRefused): b.consume_before_attempt()
    with pytest.raises(EquitiesBudgetRefused): ledger(tmp_path)


def test_missing_file_never_recreated_by_read(tmp_path):
    b=ledger(tmp_path)
    b.path.rename(tmp_path / "preserved.sqlite")
    with pytest.raises(EquitiesBudgetRefused): b.remaining()
    assert not b.path.exists()


def test_partial_initialization_is_not_reset(tmp_path):
    (tmp_path / "budget.sqlite").write_bytes(b"")
    with pytest.raises(EquitiesBudgetRefused): ledger(tmp_path)
    assert (tmp_path / "budget.sqlite").stat().st_size == 0


def test_concurrent_consumers_cannot_overspend(tmp_path):
    b=ledger(tmp_path, maximum=3)
    def attempt(_):
        try: return b.consume_before_attempt()
        except EquitiesBudgetRefused: return "REFUSED"
    with ThreadPoolExecutor(max_workers=4) as workers:
        results=list(workers.map(attempt, range(8)))
    assert sorted(r for r in results if r != "REFUSED") == [0,1,2]
    assert results.count("REFUSED") == 5
    assert ledger(tmp_path,maximum=3).remaining() == 0


def test_commit_failure_never_acknowledges(tmp_path, monkeypatch):
    b=ledger(tmp_path)
    real_connect=sqlite3.connect
    class FailCommit(sqlite3.Connection):
        def __exit__(self, *args):
            self.rollback()
            raise sqlite3.OperationalError("synthetic disk full at commit")
    monkeypatch.setattr(sqlite3, "connect", lambda *args, **kwargs: real_connect(*args, **kwargs, factory=FailCommit))
    with pytest.raises(EquitiesBudgetRefused, match="storage"):
        b.consume_before_attempt()
    monkeypatch.setattr(sqlite3, "connect", real_connect)
    assert b.remaining() == 2


@pytest.mark.asyncio
async def test_failed_provider_consumes_logical_attempt_without_retry(tmp_path):
    from scripts.observation_runtime.r7e47cl_yahoo_observer import (
        YahooObservationController,
    )
    class Fixture:
        calls=0
        async def history(self,*args,**kwargs):
            self.calls += 1
            raise TimeoutError("synthetic provider failure")
    b=ledger(tmp_path,maximum=1); f=Fixture(); c=YahooObservationController(f,b)
    with pytest.raises(TimeoutError): await c.observe("AAPL")
    assert b.remaining() == 0 and f.calls == 1
    with pytest.raises(RuntimeError): await c.observe("AAPL")
    assert f.calls == 1
