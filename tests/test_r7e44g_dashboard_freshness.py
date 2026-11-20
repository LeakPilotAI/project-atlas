"""Run the real dashboard/poll classifier with fake clocks and fetch responses."""

import subprocess
from pathlib import Path


def test_market_freshness_browser_contract():
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        ["node", str(root / "tests/r7e44g_freshness_contract.cjs")],
        cwd=root, capture_output=True, text=True, timeout=15, check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "dashboard contracts passed" in result.stdout
