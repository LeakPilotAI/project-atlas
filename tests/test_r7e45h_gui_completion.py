"""Offline regression tests for Atlas GUI manager completion file handling."""

import json
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / "scripts/windows/Atlas-Background-Ui.psm1"


def run_ps(tmp_path, script):
    fixture = tmp_path / "fixture.ps1"
    fixture.write_text(script, encoding="utf-8-sig")
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive",
         "-ExecutionPolicy", "Bypass", "-File", str(fixture)],
        capture_output=True, text=True, timeout=20, check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return json.loads(result.stdout)


def base_script():
    ui = str(UI).replace("'", "''")
    return f"""
$ErrorActionPreference = 'Stop'
Import-Module '{ui}' -Force
$root = Join-Path $env:TEMP ('atlas-r7e45h-' + [guid]::NewGuid().ToString('N'))
[IO.Directory]::CreateDirectory($root) | Out-Null
$out = Join-Path $root 'stdout'
$err = Join-Path $root 'stderr'
$exit = Join-Path $root 'exit'
[IO.File]::WriteAllText($out, '{{"state":"starting","message":"fixture"}}')
[IO.File]::WriteAllText($err, '')
[IO.File]::WriteAllText($exit, '0')
$handle = $null
try {{
"""


def finish_script():
    return """
} finally {
    if ($handle) { $handle.Dispose() }
    [IO.Directory]::Delete($root, $true)
}
"""


def test_stdout_with_compatible_open_writer(tmp_path):
    result = run_ps(tmp_path, base_script() + """
$handle = [IO.File]::Open(
    $out, [IO.FileMode]::Open, [IO.FileAccess]::ReadWrite,
    [IO.FileShare]::ReadWrite)
$r = Read-AtlasManagerCompletionFiles $out $err $exit
$c = ConvertFrom-AtlasManagerCompletion 'Start' $r.output $r.error_output $r.exit_code
@{reader=$r.state; accepted=$c.success} | ConvertTo-Json -Compress
""" + finish_script())
    assert result == {"reader": "ready", "accepted": True}


def test_exit_marker_remains_exclusive(tmp_path):
    result = run_ps(tmp_path, base_script() + """
$handle = [IO.File]::Open(
    $exit, [IO.FileMode]::Open, [IO.FileAccess]::ReadWrite,
    [IO.FileShare]::ReadWrite)
$r = Read-AtlasManagerCompletionFiles $out $err $exit
@{reader=$r.state} | ConvertTo-Json -Compress
""" + finish_script())
    assert result == {"reader": "pending"}


@pytest.mark.parametrize("payload,exit_code,accepted", [
    ('{"state":', '0', False),
    ('{"state":"starting","message":"fixture"}', '1', False),
    ('{"state":"invalid","message":"fixture"}', '0', False),
    ('{"state":"starting","message":"fixture"}', '0', True),
])
def test_completion_validation(tmp_path, payload, exit_code, accepted):
    script = base_script() + f"""
[IO.File]::WriteAllText($out, '{payload}')
[IO.File]::WriteAllText($exit, '{exit_code}')
$r = Read-AtlasManagerCompletionFiles $out $err $exit
$c = ConvertFrom-AtlasManagerCompletion 'Start' $r.output $r.error_output $r.exit_code
@{{reader=$r.state; accepted=$c.success}} | ConvertTo-Json -Compress
""" + finish_script()
    result = run_ps(tmp_path, script)
    assert result == {"reader": "ready", "accepted": accepted}


def test_missing_exit_marker_is_pending(tmp_path):
    result = run_ps(tmp_path, base_script() + """
[IO.File]::Delete($exit)
$r = Read-AtlasManagerCompletionFiles $out $err $exit
@{reader=$r.state} | ConvertTo-Json -Compress
""" + finish_script())
    assert result == {"reader": "pending"}