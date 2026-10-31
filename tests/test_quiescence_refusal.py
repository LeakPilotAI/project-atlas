import subprocess
from pathlib import Path

import pytest


@pytest.mark.parametrize("field", ["pid", "created_utc", "executable", "command_line", "run_id", "root"])
def test_changed_observation_never_authorizes_shutdown(field):
    module = Path(__file__).resolve().parents[1] / "scripts/windows/Atlas-Quiescence-Refusal.psm1"
    script = (f"Import-Module '{module}';"
              "$x=@{pid=123;created_utc='fixture';executable='fixture';command_line='fixture';run_id='fixture';root='fixture'};"
              f"$y=$x.Clone();$y['{field}']='foreign';"
              "$r=Get-AtlasQuiescenceRefusal $x $x $y;"
              "if($r.shutdown_authorized -or $r.identity_observations_match -or $r.quiescence -ne 'UNKNOWN'){exit 9}")
    result = subprocess.run(["powershell.exe", "-NoProfile", "-Command", script], timeout=10, check=False)
    assert result.returncode == 0
