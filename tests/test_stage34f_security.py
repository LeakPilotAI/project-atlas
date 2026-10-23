import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4

import pytest
from app.core.offline_startup_admission import (
    AdmissionRefused,
    consume_offline_admission,
    initialize_fixture_store,
)

ROOT = Path(__file__).resolve().parents[1]


def fixture(tmp_path):
    path = tmp_path / "state.sqlite"
    initialize_fixture_store(path)
    evidence = {"token": str(uuid4()), "run_id": str(uuid4()), "profile": "DAILY_PAPER_OFFLINE",
                "issued_at": 100, "expires_at": 130,
                "process": {"pid": 123, "created_at": "fixture", "executable": "fixture", "command": "fixture"}}
    return path, evidence


def consume(path, evidence, now=110):
    return consume_offline_admission(path, evidence, issued=evidence, run_id=evidence["run_id"],
                                     now=now, read_identity=lambda: evidence["process"])


def test_concurrent_token_consumption(tmp_path):
    path, evidence = fixture(tmp_path)
    def attempt(_):
        try:
            consume(path, evidence)
            return True
        except AdmissionRefused:
            return False
    with ThreadPoolExecutor(4) as pool:
        assert sum(pool.map(attempt, range(4))) == 1


@pytest.mark.parametrize("phase", ["before", "after"])
def test_process_crash_consumption_boundary(tmp_path, phase):
    path, evidence = fixture(tmp_path)
    payload = tmp_path / "fixture.json"
    payload.write_text(json.dumps(evidence))
    script = (
        "import json,os,sys;from pathlib import Path;"
        "from app.core.offline_startup_admission import consume_offline_admission;"
        "e=json.loads(Path(sys.argv[2]).read_text());"
        "consume_offline_admission(sys.argv[1],e,issued=e,run_id=e['run_id'],now=110,"
        "read_identity=lambda:os._exit(19))"
        if phase == "before" else
        "import json,os,sys;from pathlib import Path;"
        "from app.core.offline_startup_admission import consume_offline_admission;"
        "e=json.loads(Path(sys.argv[2]).read_text());"
        "consume_offline_admission(sys.argv[1],e,issued=e,run_id=e['run_id'],now=110,read_identity=lambda:e['process']);os._exit(19)"
    )
    result = subprocess.run([sys.executable, "-c", script, str(path), str(payload)], timeout=10, check=False)
    assert result.returncode == 19
    if phase == "after":
        with pytest.raises(AdmissionRefused):
            consume(path, evidence)
    else:
        assert consume(path, evidence)["production_authorized"] is False


@pytest.mark.parametrize("clock", [99, 130, True, float("nan")])
def test_clock_anomalies_refuse(tmp_path, clock):
    path, evidence = fixture(tmp_path)
    with pytest.raises(AdmissionRefused):
        consume(path, evidence, clock)


@pytest.mark.parametrize("action", ["Start", "Worker"])
def test_parallel_entries_ignore_forged_environment(tmp_path, action):
    forged = tmp_path / "authorization.json"
    forged.write_text('{"authorized":true}')
    env = {**os.environ, "ATLAS_STARTUP_AUTHORIZED": "true", "ATLAS_ADMISSION_FILE": str(forged)}
    def attempt(_):
        return subprocess.run(["powershell.exe", "-NoProfile", "-File",
                               str(ROOT / "scripts/windows/Atlas-Background.ps1"), "-Action", action],
                              env=env, capture_output=True, text=True, timeout=10, check=False)
    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(attempt, range(2)))
    assert all(r.returncode != 0 and "ATLAS_STARTUP_ADMISSION_REFUSED" in r.stderr for r in results)


def test_partial_store_refuses_without_reconstruction(tmp_path):
    path = tmp_path / "partial.sqlite"
    path.write_bytes(b"SQLite format 3\x00partial")
    _, evidence = fixture(tmp_path)
    original = path.read_bytes()
    with pytest.raises(AdmissionRefused):
        consume(path, evidence)
    assert path.read_bytes() == original
