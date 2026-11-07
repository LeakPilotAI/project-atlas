"""Additional isolated tests for the synthetic SQLite budget prototype."""
import sqlite3
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

import pytest

from scripts.observation_runtime.r7e47v_budget_ledger import (
    BudgetRefused,
    DurableBudget,
)


def test_separate_processes_share_atomic_budget(tmp_path):
    path = tmp_path / "budget.sqlite"
    DurableBudget(path, "fixture", 5, enroll=True)

    worker = """
import sys
from scripts.observation_runtime.r7e47v_budget_ledger import (
    BudgetRefused, DurableBudget,
)
try:
    DurableBudget(sys.argv[1], "fixture", 5).consume()
except BudgetRefused:
    sys.exit(2)
"""

    def run_worker(_):
        return subprocess.run(
            [sys.executable, "-c", worker, str(path)],
            capture_output=True,
            text=True,
            timeout=15,
        )

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(run_worker, range(16)))

    assert all(result.returncode in (0, 2) for result in results), [
        (result.returncode, result.stderr) for result in results
    ]
    assert sum(result.returncode == 0 for result in results) == 5
    assert DurableBudget(path, "fixture", 5).remaining() == 0


def test_missing_provider_row_must_fail_closed(tmp_path):
    path = tmp_path / "budget.sqlite"
    ledger = DurableBudget(path, "fixture", 3, enroll=True)
    assert ledger.consume() == 1

    with sqlite3.connect(path) as db:
        db.execute("DELETE FROM budget WHERE provider='fixture'")

    with pytest.raises(BudgetRefused):
        DurableBudget(path, "fixture", 3)


def test_missing_table_must_fail_closed(tmp_path):
    path = tmp_path / "budget.sqlite"
    DurableBudget(path, "fixture", 3, enroll=True).consume()

    with sqlite3.connect(path) as db:
        db.execute("DROP TABLE budget")

    with pytest.raises(BudgetRefused):
        DurableBudget(path, "fixture", 3)


def test_ledger_rejects_database_corruption_on_reopen(tmp_path):
    path = tmp_path / "budget.sqlite"
    DurableBudget(path, "fixture", 3, enroll=True).consume()

    path.write_bytes(b"corrupted database content")

    with pytest.raises(BudgetRefused):
        DurableBudget(path, "fixture", 3)