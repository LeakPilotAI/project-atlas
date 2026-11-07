import sqlite3
from concurrent.futures import ThreadPoolExecutor

import pytest

from scripts.observation_runtime.r7e47v_budget_ledger import (
    BudgetRefused,
    DurableBudget,
)


def test_persists_across_reopen(tmp_path):
    path = tmp_path / "budget.sqlite"
    first = DurableBudget(path, "fixture", 2, enroll=True)
    assert first.consume() == 1
    reopened = DurableBudget(path, "fixture", 2)
    assert reopened.remaining() == 1
    assert reopened.consume() == 2
    with pytest.raises(BudgetRefused):
        reopened.consume()


def test_concurrent_writers_cannot_exceed_budget(tmp_path):
    path = tmp_path / "budget.sqlite"
    ledger = DurableBudget(path, "fixture", 10, enroll=True)

    def attempt(_):
        try:
            ledger.consume()
            return True
        except BudgetRefused:
            return False

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(attempt, range(40)))

    assert sum(results) == 10
    assert ledger.remaining() == 0


def test_changed_limit_refused(tmp_path):
    path = tmp_path / "budget.sqlite"
    DurableBudget(path, "fixture", 3, enroll=True).consume()
    with pytest.raises(BudgetRefused):
        DurableBudget(path, "fixture", 5, enroll=True)


def test_corrupt_database_refused(tmp_path):
    path = tmp_path / "budget.sqlite"
    path.write_bytes(b"not a sqlite database")
    with pytest.raises(BudgetRefused):
        DurableBudget(path, "fixture", 2, enroll=True)


def test_invalid_counter_refused(tmp_path):
    path = tmp_path / "budget.sqlite"
    ledger = DurableBudget(path, "fixture", 2, enroll=True)
    with sqlite3.connect(path) as db:
        db.execute(
            "UPDATE budget SET attempted=-1 WHERE provider='fixture'"
        )
    with pytest.raises(BudgetRefused):
        ledger.consume()


def test_missing_parent_refused(tmp_path):
    with pytest.raises(BudgetRefused):
        DurableBudget(tmp_path / "missing" / "budget.sqlite", "fixture", 2)


@pytest.mark.parametrize("limit", [0, -1, True, 10001])
def test_invalid_limits(tmp_path, limit):
    with pytest.raises(BudgetRefused):
        DurableBudget(tmp_path / "budget.sqlite", "fixture", limit)