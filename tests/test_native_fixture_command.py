"""Native read-only evidence from exact retained disposable children, never authority."""
import subprocess
from pathlib import Path

import pytest


@pytest.mark.parametrize("damage", [None, "command", "account", "parent", "creation", "unavailable"])
def test_retained_fixture_native_command_and_account(tmp_path, damage):
    module = Path(__file__).resolve().parents[1] / "scripts/windows/Atlas-NativeIdentity-Observation.psm1"
    child = tmp_path / "owned-fixture.ps1"
    child.write_text("@{command_line=[Environment]::CommandLine}|ConvertTo-Json -Compress;"
                     "[Console]::Out.Flush();[void][Console]::ReadLine()")
    script = (f"$ErrorActionPreference='Stop';Import-Module '{module}';"
              "$i=New-Object Diagnostics.ProcessStartInfo;$i.FileName=(Join-Path $PSHOME 'powershell.exe');"
              f"$i.Arguments='-NoProfile -File \"{child}\"';"
              "$i.UseShellExecute=$false;$i.CreateNoWindow=$true;$i.RedirectStandardInput=$true;$i.RedirectStandardOutput=$true;"
              "$p=New-Object Diagnostics.Process;$p.StartInfo=$i;[void]$p.Start();"
              "try{$ready=$p.StandardOutput.ReadLineAsync();if(-not $ready.Wait(5000)){throw 'Readiness unavailable'};"
              "$body=$ready.Result|ConvertFrom-Json;"
              "$expected=@{pid=$p.Id;created_utc=$p.StartTime.ToUniversalTime().ToString('o');"
              "executable=$p.MainModule.FileName;command_line=$body.command_line;parent_pid=$PID;"
              "account_sid=[Security.Principal.WindowsIdentity]::GetCurrent().User.Value};")
    if damage == "unavailable":
        script += "& (Get-Module Atlas-NativeIdentity-Observation) {function script:Get-CimInstance {throw 'Synthetic unavailable'}};"
    elif damage:
        key = {"command": "command_line", "account": "account_sid", "parent": "parent_pid",
               "creation": "created_utc"}[damage]
        value = "1" if damage == "parent" else "foreign"
        script += f"$expected['{key}']='{value}';"
    if damage:
        script += "$refused=$false;try{$null=Get-AtlasFixtureCommandObservation $p $expected}catch{$refused=$true};if(-not $refused){throw 'Unsafe acceptance'};"
    else:
        script += ("$r=Get-AtlasFixtureCommandObservation $p $expected;"
                   "if(-not $r.command_line_verified -or -not $r.windows_account_verified -or "
                   "$r.production_authorized -or $r.shutdown_authorized -or $r.startup_authorized -or "
                   "$r.ownership_independently_verified -or $r.quiescence -cne 'UNKNOWN'){throw 'False authority or missing observation'};")
    script += "}finally{if(-not $p.HasExited){$p.StandardInput.Close();if(-not $p.WaitForExit(5000)){throw 'Owned fixture still active; no forced termination'}};$p.Dispose()}"
    result = subprocess.run(["powershell.exe", "-NoProfile", "-Command", script],
                            capture_output=True, text=True, timeout=20, check=False)
    assert result.returncode == 0, result.stderr
