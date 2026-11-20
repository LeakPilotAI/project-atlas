import subprocess
from pathlib import Path

import pytest


@pytest.mark.parametrize("mismatch", [False, True])
def test_exact_native_self_identity_no_authority(mismatch):
    module = Path(__file__).resolve().parents[1] / "scripts/windows/Atlas-NativeIdentity-Observation.psm1"
    script = (f"Import-Module '{module}';"
              "$p=[Diagnostics.Process]::GetCurrentProcess();"
              "$expected=@{pid=$PID;created_utc=$p.StartTime.ToUniversalTime().ToString('o');executable=$p.MainModule.FileName;command_line=[Environment]::CommandLine};")
    if mismatch:
        script += "$expected.created_utc='reused';try{Get-AtlasNativeIdentityObservation $PID $expected;exit 9}catch{exit 0}"
    else:
        script += "$r=Get-AtlasNativeIdentityObservation $PID $expected;if($r.production_authorized -or $r.quiescence -ne 'UNKNOWN'){exit 9}"
    result = subprocess.run(["powershell.exe", "-NoProfile", "-Command", script],
                            capture_output=True, text=True, timeout=15, check=False)
    if result.returncode == 77:
        pytest.skip("Native CIM self-observation unavailable; acceptance BLOCKED")
    assert result.returncode == 0, result.stderr
