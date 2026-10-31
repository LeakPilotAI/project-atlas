import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from app.services.paper_writer_fixture import provision_fixture_writers
from test_bound_daily_report import setup
from test_durable_partial_shutdown import fixture


@pytest.mark.parametrize("prices", [True, False, "stale"])
def test_windows_fixture_drives_isolated_ledger(tmp_path, prices):
    path, _ = fixture(tmp_path)
    setup(path)
    provision_fixture_writers(path, {"manual": "fixture", "prediction": "fixture", "investment": "fixture", "journal": "fixture", "lifecycle": "fixture"})
    bridge = tmp_path / "bridge.py"
    bridge.write_text(
        "import sys;from app.services.daily_paper_liquidation import liquidate;"
        "from app.services.paper_bound_daily_report import publish_bound_daily;"
        "from app.services.paper_exit_audit import audit_fixture_exits\n"
        "from app.services.paper_writer_fixture import close_fixture_writers\n"
        "if sys.argv[1]=='drain':\n"
        " r=close_fixture_writers(sys.argv[2],dict.fromkeys(['manual','prediction','investment','journal','lifecycle'],'fixture'));sys.exit(0 if r['status']=='DRAINED_FIXTURE_ONLY' else 2)\n"
        "elif sys.argv[1]=='liquidate':\n"
        f" r=liquidate(sys.argv[2],'s',{{'T':{{'price':'104','observed_at':{0 if prices == 'stale' else 3},'verified':True,'source_id':'fixture'}}}} if {prices!r} else {{}},now=3,max_age=1);sys.exit(0 if r['complete'] else 2)\n"
        "else:\n"
        " r=audit_fixture_exits(sys.argv[2]);publish_bound_daily(sys.argv[2],day='1970-01-01',timezone='UTC',currency='USD');sys.exit(0 if r['reconciled'] else 2)\n"
    )
    module = Path(__file__).resolve().parents[1] / "scripts/windows/Atlas-PaperShutdown-Fixture.psm1"
    command = (f"Import-Module '{module}';"
               f"$r=Invoke-AtlasPaperShutdownFixture {{$true}} {{& '{sys.executable}' '{bridge}' drain '{path}';$LASTEXITCODE -eq 0}} {{& '{sys.executable}' '{bridge}' liquidate '{path}';$LASTEXITCODE -eq 0}} "
               f"{{& '{sys.executable}' '{bridge}' report '{path}';$LASTEXITCODE -eq 0}} {{$true}};"
               "$r.outcome")
    result = subprocess.run(["powershell.exe", "-NoProfile", "-Command", command],
                            capture_output=True, text=True, timeout=15, check=False)
    assert result.returncode == 0, result.stderr
    assert ("COMPLETE_FIXTURE_ONLY" if prices is True else "INCOMPLETE") in result.stdout


@pytest.mark.parametrize("failed", ["drain", "liquidate", "report", "stop"])
def test_windows_failure_never_claims_complete(failed):
    module = Path(__file__).resolve().parents[1] / "scripts/windows/Atlas-PaperShutdown-Fixture.psm1"
    actions = ["{$true}", "{$true}", "{$true}", "{$true}", "{$true}"]
    index = {"drain": 1, "liquidate": 2, "report": 3, "stop": 4}[failed]
    actions[index] = "{throw 'fixture failure'}"
    for following in range(index + 1, 5):
        actions[following] = "{throw 'UNSAFE_FOLLOWING_STEP'}"
    command = f"Import-Module '{module}';$r=Invoke-AtlasPaperShutdownFixture " + " ".join(actions) + ";$r|ConvertTo-Json -Compress"
    result = subprocess.run(["powershell.exe", "-NoProfile", "-Command", command],
                            capture_output=True, text=True, timeout=10, check=False)
    assert result.returncode == 0
    assert '"outcome":"INCOMPLETE"' in result.stdout
    assert "UNSAFE_FOLLOWING_STEP" not in result.stdout


def test_concurrent_windows_subprocess_liquidation_once(tmp_path):
    import sqlite3

    path, _ = fixture(tmp_path)
    setup(path)
    bridge = tmp_path / "concurrent.py"
    bridge.write_text("import sys;from app.services.daily_paper_liquidation import liquidate;"
                      "liquidate(sys.argv[1],'s',{'T':{'price':'104','observed_at':3,'verified':True,'source_id':'fixture'}},now=3,max_age=1)")
    command = f"& '{sys.executable}' '{bridge}' '{path}';exit $LASTEXITCODE"
    def attempt(_):
        return subprocess.run(["powershell.exe", "-NoProfile", "-Command", command],
                              timeout=15, capture_output=True, text=True, check=False)
    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(attempt, range(2)))
    assert all(result.returncode == 0 for result in results)
    assert attempt(0).returncode == 0
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT COUNT(*) FROM exits").fetchone()[0] == 1
        assert db.execute("SELECT COUNT(*) FROM report_history").fetchone()[0] == 1


@pytest.mark.parametrize("phase", ["before_exit", "after_exit", "before_commit", "after_commit"])
def test_windows_bridge_abrupt_restart(tmp_path, phase):
    import sqlite3

    path, _ = fixture(tmp_path)
    bridge = tmp_path / "crash.py"
    bridge.write_text("import os,sys;from app.services.daily_paper_liquidation import liquidate;"
                      "liquidate(sys.argv[1],'s',{'T':{'price':'104','observed_at':3,'verified':True,'source_id':'fixture'}},now=3,max_age=1,"
                      "fault=lambda at:os._exit(41) if at==sys.argv[2] else None)")
    def attempt(at):
        command = f"& '{sys.executable}' '{bridge}' '{path}' '{at}';exit $LASTEXITCODE"
        return subprocess.run(["powershell.exe", "-NoProfile", "-Command", command],
                              timeout=15, capture_output=True, text=True, check=False)
    assert attempt(phase).returncode == 41
    assert attempt("none").returncode == 0
    assert attempt("none").returncode == 0
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT COUNT(*) FROM exits").fetchone()[0] == 1
        assert db.execute("SELECT COUNT(*) FROM report_history").fetchone()[0] == 1
