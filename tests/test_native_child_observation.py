import subprocess
from pathlib import Path

import pytest


@pytest.mark.parametrize("damage", [None, "creation", "pid", "executable", "exited"])
def test_retained_native_child_identity(tmp_path, damage):
    module = Path(__file__).resolve().parents[1] / "scripts/windows/Atlas-NativeIdentity-Observation.psm1"
    child = tmp_path / "child.ps1"
    child.write_text("[Console]::WriteLine('READY');[Console]::Out.Flush();[void][Console]::ReadLine()")
    script = (f"$ErrorActionPreference='Stop';Import-Module '{module}';"
              "$i=New-Object Diagnostics.ProcessStartInfo;$i.FileName=(Join-Path $PSHOME 'powershell.exe');"
              f"$i.Arguments='-NoProfile -File \"{child}\"';"
              "$i.UseShellExecute=$false;$i.CreateNoWindow=$true;$i.RedirectStandardInput=$true;$i.RedirectStandardOutput=$true;"
              "$p=New-Object Diagnostics.Process;$p.StartInfo=$i;[void]$p.Start();"
              "try{$ready=$p.StandardOutput.ReadLineAsync();if(-not $ready.Wait(5000) -or $ready.Result -ne 'READY'){throw 'Child readiness unavailable'};"
              "$expected=@{pid=$p.Id;created_utc=$p.StartTime.ToUniversalTime().ToString('o');executable=$p.MainModule.FileName};")
    if damage == "exited":
        script += "$p.StandardInput.Close();if(-not $p.WaitForExit(5000)){throw 'Child exit unverified'};"
    elif damage:
        key = {"creation": "created_utc", "pid": "pid", "executable": "executable"}[damage]
        script += f"$expected['{key}']='foreign';"
    if damage:
        script += "try{Get-AtlasFixtureChildObservation $p $expected;exit 9}catch{};"
    else:
        script += "$r=Get-AtlasFixtureChildObservation $p $expected;if($r.production_authorized -or $r.command_line_verified -or $r.ownership_independently_verified){throw 'Unproven authority'};"
        script += "$wait=Wait-AtlasFixtureChildExit $p $expected 0;if($wait.process_exited -or $wait.production_authorized){throw 'False exit proof'};"
    script += "}finally{if(-not $p.HasExited){$p.StandardInput.Close();if(-not $p.WaitForExit(5000)){throw 'Fixture still active; no forced termination'}};$p.Dispose()}"
    result = subprocess.run(["powershell.exe", "-NoProfile", "-Command", script],
                            capture_output=True, text=True, timeout=20, check=False)
    assert result.returncode == 0, result.stderr
