import json
import sqlite3
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pytest
from app.services.daily_paper_liquidation import liquidate
from test_bound_daily_report import setup
from test_durable_partial_shutdown import fixture
from test_report_inventory import inventory


@pytest.mark.parametrize("damage", [None, "identity", "version", "commitment", "persistence"])
def test_windows_v2_authority_pin(tmp_path, damage):
    path, _ = fixture(tmp_path)
    setup(path)
    liquidate(path, "s", {"T": {"price": "104", "observed_at": 3, "verified": True, "source_id": "fixture"}}, now=3, max_age=1)
    receipt = inventory(path)
    expected = deepcopy(receipt)
    if damage == "persistence":
        with sqlite3.connect(path) as db:
            db.execute("CREATE TABLE bound_daily(id INTEGER PRIMARY KEY,body TEXT,parent TEXT,digest TEXT)")
            db.execute("CREATE TRIGGER deny_report BEFORE INSERT ON bound_daily BEGIN SELECT RAISE(ABORT,'fixture persistence denial'); END")
    if damage == "identity":
        receipt["identity"] = "substitute"
    elif damage == "version":
        receipt["version"] = 2
    elif damage == "commitment":
        receipt["sources"]["positions"] = "bad"
    source = tmp_path / "receipt.json"
    source.write_text(json.dumps(receipt))
    bridge = tmp_path / "v2.py"
    bridge.write_text("import sys,json;from pathlib import Path;from app.services.paper_fixture_authority import pinned_fixture_reporter;"
                      f"publish=pinned_fixture_reporter({expected!r});"
                      "publish(sys.argv[1],day='1970-01-01',timezone='UTC',currency='USD',inventory=json.loads(Path(sys.argv[2]).read_text()))")
    module = Path(__file__).resolve().parents[1] / "scripts/windows/Atlas-PaperShutdown-Fixture.psm1"
    command = (f"Import-Module '{module}';$r=Invoke-AtlasPaperShutdownFixture {{$true}} {{$true}} {{$true}} "
               f"{{& '{sys.executable}' '{bridge}' '{path}' '{source}';$LASTEXITCODE -eq 0}} {{$true}};$r.outcome")
    result = subprocess.run(["powershell.exe", "-NoProfile", "-Command", command],
                            timeout=15, capture_output=True, text=True, check=False)
    assert result.returncode == 0
    assert ("INCOMPLETE" if damage else "COMPLETE_FIXTURE_ONLY") in result.stdout
    if damage == "persistence":
        with sqlite3.connect(path) as db:
            assert db.execute("SELECT COUNT(*) FROM bound_daily").fetchone()[0] == 0
            db.execute("DROP TRIGGER deny_report")
        retry = subprocess.run(["powershell.exe", "-NoProfile", "-Command", command],
                               timeout=15, capture_output=True, text=True, check=False)
        assert retry.returncode == 0 and "COMPLETE_FIXTURE_ONLY" in retry.stdout
