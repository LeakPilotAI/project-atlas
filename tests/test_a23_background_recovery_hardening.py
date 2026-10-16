"""A23: isolated Windows background recovery hardening regressions."""

from pathlib import Path
import subprocess
import textwrap

import pytest


ROOT = Path(__file__).resolve().parents[1]
MANAGER = ROOT / "scripts/windows/Atlas-Background.ps1"
OWNERSHIP = ROOT / "scripts/windows/Atlas-ProcessOwnership.psm1"


def run_powershell(script: str, tmp_path: Path):
    fixture = tmp_path / "fixture.ps1"
    fixture.write_text(script, encoding="utf-8")

    result = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(fixture),
        ],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert result.returncode == 0, (
        f"PowerShell fixture failed:\n{result.stdout}\n{result.stderr}"
    )
    return result.stdout


def extract_function(path: Path, name: str, tmp_path: Path) -> str:
    output = tmp_path / "function.txt"
    script = textwrap.dedent(
        r"""
        $ErrorActionPreference = "Stop"
        $tokens = $null
        $errors = $null
        $ast = [Management.Automation.Language.Parser]::ParseFile(
            '__SOURCE__', [ref]$tokens, [ref]$errors
        )
        if (@($errors).Count -gt 0) { throw "Parse errors" }
        $functions = @($ast.FindAll({
            param($node)
            $node -is [Management.Automation.Language.FunctionDefinitionAst] -and
            $node.Name -eq '__NAME__'
        }, $true))
        if ($functions.Count -ne 1) { throw "Unexpected function count" }
        [IO.File]::WriteAllText(
            '__OUTPUT__',
            $functions[0].Extent.Text,
            [Text.UTF8Encoding]::new($false)
        )
        """
    )

    for key, value in {
        "__SOURCE__": str(path),
        "__NAME__": name,
        "__OUTPUT__": str(output),
    }.items():
        script = script.replace(key, value.replace("'", "''"))

    run_powershell(script, tmp_path)
    return output.read_text(encoding="utf-8")


def test_archive_rollback_restores_original_metadata(tmp_path):
    source = OWNERSHIP.read_text(encoding="utf-8")
    needle = (
        "Move-Item -LiteralPath $RuntimePath "
        "-Destination $archivedRuntimePath -ErrorAction Stop"
    )

    assert source.count(needle) == 1

    injected = source.replace(
        needle,
        'throw "A23_INJECTED_SECOND_MOVE_FAILURE"\n        ' + needle,
    )

    module = tmp_path / "ownership-fixture.psm1"
    module.write_text(injected, encoding="utf-8")

    script = textwrap.dedent(
        r"""
        $ErrorActionPreference = "Stop"
        Import-Module '__MODULE__' -Force

        $root = '__ROOT__'
        $ownerPath = Join-Path $root 'atlas-background-owner.json'
        $runtimePath = Join-Path $root 'runtime.json'
        $archiveRoot = Join-Path $root 'stale-sessions'

        New-Item -ItemType Directory -Path $archiveRoot | Out-Null

        $run = [guid]::NewGuid().ToString()

        $owner = [pscustomobject]@{
            root = 'D:\Atlas'
            run_id = $run
            pid = 31204
        }

        $runtime = [pscustomobject]@{
            run_id = $run
            pid = 19444
        }

        $owner | ConvertTo-Json |
            Set-Content -LiteralPath $ownerPath -Encoding UTF8

        $runtime | ConvertTo-Json |
            Set-Content -LiteralPath $runtimePath -Encoding UTF8

        $ownerHash = (Get-FileHash $ownerPath -Algorithm SHA256).Hash
        $runtimeHash = (Get-FileHash $runtimePath -Algorithm SHA256).Hash

        $caught = $false

        try {
            Move-AtlasDeadSessionMetadata `
                $ownerPath $runtimePath $archiveRoot `
                $owner $runtime 'D:\Atlas' `
                @() @() @() $false | Out-Null
        } catch {
            if ($_.Exception.Message -match 'STALE_SESSION_ARCHIVE_FAILED' -and
                $_.Exception.Message -match 'A23_INJECTED_SECOND_MOVE_FAILURE') {
                $caught = $true
            } else {
                throw
            }
        }

        if (-not $caught) { throw 'Expected failure missing' }

        if ((Get-FileHash $ownerPath -Algorithm SHA256).Hash -ne $ownerHash) {
            throw 'Owner rollback failed'
        }

        if ((Get-FileHash $runtimePath -Algorithm SHA256).Hash -ne $runtimeHash) {
            throw 'Runtime metadata changed'
        }

        if (@(Get-ChildItem $archiveRoot -Recurse -File).Count -ne 0) {
            throw 'Archived metadata remains'
        }

        Write-Output 'PASS: archive rollback'
        """
    )

    script = script.replace("__MODULE__", str(module).replace("'", "''"))
    script = script.replace("__ROOT__", str(tmp_path).replace("'", "''"))

    assert "PASS: archive rollback" in run_powershell(script, tmp_path)


@pytest.mark.parametrize(
    ("failure_mode", "expected_lock"),
    [("rollback", True), ("ordinary", False)],
)
def test_manager_recovery_failure_lock_policy(
    tmp_path, failure_mode, expected_lock
):
    function = extract_function(
        MANAGER, "Get-VerifiedState", tmp_path
    )

    script = textwrap.dedent(
        r"""
        $ErrorActionPreference = "Stop"

        $RuntimeDir = '__ROOT__'
        $Root = 'D:\Atlas'
        $OwnerPath = Join-Path $RuntimeDir 'atlas-background-owner.json'
        $RuntimePath = Join-Path $RuntimeDir 'runtime.json'
        $RecoveryLockPath = Join-Path $RuntimeDir 'atlas-background-recovery.lock'
        $LockPath = Join-Path $RuntimeDir 'atlas-background-start.lock'
        $StopLockPath = Join-Path $RuntimeDir 'atlas-background-stop.lock'

        $PowerShellPath = 'powershell.exe'
        $ManagerPath = 'D:\Atlas\scripts\windows\Atlas-Background.ps1'
        $VenvPy = 'D:\Atlas\backend\.venv\Scripts\python.exe'
        $VenvBasePy = ''

        function Read-JsonFile([string]$Path) {
            if (-not (Test-Path -LiteralPath $Path)) { return $null }
            Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json
        }

        function New-ExclusiveJsonFile($Value, [string]$Path) {
            $bytes = [Text.Encoding]::UTF8.GetBytes(($Value | ConvertTo-Json))
            $stream = [IO.File]::Open(
                $Path, [IO.FileMode]::CreateNew,
                [IO.FileAccess]::Write, [IO.FileShare]::None
            )
            try { $stream.Write($bytes, 0, $bytes.Length) }
            finally { $stream.Dispose() }
        }

        function Get-ProcessIdentity([int]$ProcessId) {
            return @{
                executable = $PowerShellPath
                command_line = 'fixture'
                created_utc = '2026-10-16T00:00:00Z'
            }
        }

        function Get-AtlasApiProcesses { return @() }
        function Get-ApiListeners { return @() }
        function Get-CimProcess([int]$ProcessId) { return $null }
        function Test-AtlasDeadSession { return $true }

        function Move-AtlasDeadSessionMetadata {
            if ('__MODE__' -eq 'rollback') {
                throw 'STALE_SESSION_ROLLBACK_FAILED: injected'
            }
            throw 'STALE_SESSION_ARCHIVE_FAILED: injected'
        }

        __FUNCTION__

        $run = [guid]::NewGuid().ToString()

        @{
            schema_version = 1
            root = $Root
            run_id = $run
            pid = 31204
            created_utc = '2026-10-16T00:00:00Z'
            state = 'running'
            command_line = 'fixture'
        } | ConvertTo-Json |
            Set-Content -LiteralPath $OwnerPath -Encoding UTF8

        @{
            run_id = $run
            pid = 19444
        } | ConvertTo-Json |
            Set-Content -LiteralPath $RuntimePath -Encoding UTF8

        $result = Get-VerifiedState

        if ($result.state -ne 'AMBIGUOUS') {
            throw "Unexpected state: $($result.state)"
        }

        if ($result.message -notmatch 'metadata integrity must be verified') {
            throw "Missing integrity warning: $($result.message)"
        }

        $lockExists = Test-Path -LiteralPath $RecoveryLockPath

        if ($lockExists -ne [bool]::Parse('__EXPECTED__')) {
            throw "Unexpected recovery lock: $lockExists"
        }

        Write-Output 'PASS: manager lock policy'
        """
    )

    replacements = {
        "__ROOT__": str(tmp_path).replace("'", "''"),
        "__MODE__": failure_mode,
        "__EXPECTED__": str(expected_lock),
        "__FUNCTION__": function,
    }

    for key, value in replacements.items():
        script = script.replace(key, value)

    assert "PASS: manager lock policy" in run_powershell(script, tmp_path)


def test_crash_window_is_fail_closed(tmp_path):
    function = extract_function(
        MANAGER, "Get-VerifiedState", tmp_path
    )

    script = textwrap.dedent(
        r"""
        $ErrorActionPreference = "Stop"

        $RuntimeDir = '__ROOT__'
        $Root = 'D:\Atlas'
        $OwnerPath = Join-Path $RuntimeDir 'atlas-background-owner.json'
        $RuntimePath = Join-Path $RuntimeDir 'runtime.json'
        $RecoveryLockPath = Join-Path $RuntimeDir 'atlas-background-recovery.lock'
        $LockPath = Join-Path $RuntimeDir 'atlas-background-start.lock'
        $StopLockPath = Join-Path $RuntimeDir 'atlas-background-stop.lock'

        function Read-JsonFile([string]$Path) {
            if (-not (Test-Path -LiteralPath $Path)) { return $null }
            Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json
        }

        function Get-AtlasApiProcesses { return @() }
        function Get-ApiListeners { return @() }

        __FUNCTION__

        $run = [guid]::NewGuid().ToString()
        $archive = Join-Path $RuntimeDir 'archive'
        New-Item -ItemType Directory -Path $archive | Out-Null

        @{
            root = $Root
            run_id = $run
            pid = 31204
        } | ConvertTo-Json |
            Set-Content -LiteralPath $OwnerPath -Encoding UTF8

        @{
            run_id = $run
            pid = 19444
        } | ConvertTo-Json |
            Set-Content -LiteralPath $RuntimePath -Encoding UTF8

        Move-Item -LiteralPath $OwnerPath `
            -Destination (Join-Path $archive 'atlas-background-owner.json')

        $result = Get-VerifiedState

        if ($result.state -ne 'AMBIGUOUS') {
            throw 'Incomplete archive was not rejected'
        }

        if ($result.message -notmatch 'runtime manifest exists without a background owner') {
            throw 'Unexpected crash-window diagnostic'
        }

        Write-Output 'PASS: crash-window fail-closed'
        """
    )

    script = script.replace("__ROOT__", str(tmp_path).replace("'", "''"))
    script = script.replace("__FUNCTION__", function)

    assert "PASS: crash-window fail-closed" in run_powershell(
        script, tmp_path
    )