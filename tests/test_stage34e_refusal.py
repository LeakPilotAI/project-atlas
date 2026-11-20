import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("kind", ["missing", "corrupt", "replayed", "expired", "identity-mismatch"])
def test_unaccepted_evidence_never_grants_production(kind):
    module = ROOT / "scripts/windows/Atlas-StartupAdmission.psm1"
    result = subprocess.run(["powershell.exe", "-NoProfile", "-Command",
                             f"Import-Module '{module}'; Assert-AtlasStartupAdmission -Boundary fixture -Evidence '{kind}'"],
                            capture_output=True, text=True, timeout=10, check=False)
    assert result.returncode != 0
    assert "ATLAS_STARTUP_ADMISSION_REFUSED" in result.stderr


@pytest.mark.parametrize("action", ["Start", "Worker"])
def test_real_entry_refuses_before_operational_code(action):
    path = ROOT / "scripts/windows/Atlas-Background.ps1"
    result = subprocess.run(["powershell.exe", "-NoProfile", "-File", str(path), "-Action", action],
                            capture_output=True, text=True, timeout=10, check=False)
    assert result.returncode != 0
    assert "ATLAS_STARTUP_ADMISSION_REFUSED" in result.stderr
    source = path.read_text()
    assert source.index("-Boundary 'parent'") < source.index('$Root =')
    body = source.split("function Invoke-BackgroundWorker {", 1)[1]
    assert body.index("-Boundary 'worker-function'") < body.index("Start-AtlasDependencies")
