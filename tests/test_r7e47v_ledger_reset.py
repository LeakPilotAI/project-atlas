"""Synthetic-only ledger deletion and replacement regression tests."""
import sqlite3

import pytest

from scripts.observation_runtime.r7e47v_budget_ledger import (
    BudgetRefused,
    DurableBudget,
)


def test_deleted_database_must_not_restore_budget(tmp_path):
    path = tmp_path / "budget.sqlite"
    ledger = DurableBudget(path, "fixture", 3, enroll=True)
    assert ledger.consume() == 1

    path.unlink()

    with pytest.raises(BudgetRefused):
        DurableBudget(path, "fixture", 3)


def test_replaced_empty_database_must_not_restore_budget(tmp_path):
    path = tmp_path / "budget.sqlite"
    ledger = DurableBudget(path, "fixture", 3, enroll=True)
    assert ledger.consume() == 1

    path.unlink()

    with sqlite3.connect(path):
        pass

    with pytest.raises(BudgetRefused):
        DurableBudget(path, "fixture", 3)