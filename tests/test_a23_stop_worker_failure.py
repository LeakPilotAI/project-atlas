"""A23-G3E3: fail-closed stop-worker launch regression coverage."""

import pathlib
import subprocess

import pytest


ROOT = pathlib.Path(__file__).resolve().parents[1]
MANAGER = ROOT / "scripts/windows/Atlas-Background.ps1"


def _run_powershell(script: str) -> subprocess.CompletedProcess[str]:
    gate_module = str(ROOT / "scripts/windows/Atlas-CompleteShutdown.psm1").replace("'", "''")
    script = f"Import-Module '{gate_module}' -Force\n" + script
    return subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            script,
        ],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )


def _manager_ast():
    source = MANAGER.read_text(encoding="utf-8")
    assert "function Set-OwnerLastError" in source
    assert "STOP_WORKER_LAUNCH_UNCONFIRMED" in source
    return source


def test_stop_worker_failure_remains_fail_closed():
    source = _manager_ast()
    stop = source.split('if ($Action -eq "Stop") {', 1)[1].split(
        'if ($Action -eq "Worker") {', 1
    )[0]
    catch = stop.split("    } catch {")[-1]
    assert "STOP_WORKER_LAUNCH_UNCONFIRMED" in catch
    assert "Write-JsonAtomic" not in catch
    assert "Set-OwnerLastError" not in catch
    assert '$owner.state = "stop_timeout"' not in catch
    assert "Assert-CleanStart" in source


@pytest.mark.parametrize("kind", ["hashtable", "pscustomobject"])
def test_owner_last_error_helper_supports_owner_types(kind):
    source = _manager_ast()

    start = source.index("function Set-OwnerLastError(")
    end = source.index("function New-ExclusiveJsonFile(", start)
    helper = source[start:end]

    owner = (
        '@{ state = "running" }'
        if kind == "hashtable"
        else '[pscustomobject]@{ state = "running" }'
    )

    script = f"""
$ErrorActionPreference = "Stop"
{helper}
$owner = {owner}
Set-OwnerLastError $owner "A23_TEST_OWNER_ERROR: injected"
if ($owner.last_error -cne "A23_TEST_OWNER_ERROR: injected") {{
    throw "Owner error property was not persisted."
}}
Write-Output "PASS"
"""

    result = _run_powershell(script)

    assert result.returncode == 0, result.stderr
    assert "PASS" in result.stdout


def test_stop_worker_status_message_is_distinct():
    source = _manager_ast()
    assert "STOP_WORKER_LAUNCH_FAILED:" not in source
    assert "STOP_WORKER_LAUNCH_UNCONFIRMED" in source
    assert "Graceful shutdown timed out" in source
    assert "Operator intervention is required" in source

@pytest.mark.parametrize("failure_mode", ["throw", "no_process"])
def test_stop_worker_launch_failure_preserves_evidence(
    failure_mode, tmp_path
):
    """Execute the production Stop action with isolated mocked dependencies."""

    source = _manager_ast()

    extract = r"""
$ErrorActionPreference = "Stop"
$tokens = $null
$errors = $null

$ast = [System.Management.Automation.Language.Parser]::ParseFile(
    $args[0], [ref]$tokens, [ref]$errors
)

if (@($errors).Count -gt 0) {
    throw "Manager parse failed."
}

$stop = @(
    $ast.EndBlock.Statements | Where-Object {
        $_ -is [System.Management.Automation.Language.IfStatementAst] -and
        $_.Extent.Text -match '^\s*if\s*\(\s*\$Action\s+-eq\s+["'']Stop["'']\s*\)'
    }
)

if ($stop.Count -ne 1) {
    throw "Expected exactly one Stop action."
}

$helper = @(
    $ast.FindAll({
        param($node)
        $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and
        $node.Name -eq "Set-OwnerLastError"
    }, $true)
)

if ($helper.Count -ne 1) {
    throw "Expected exactly one owner-error helper."
}

[IO.File]::WriteAllText(
    $args[1], $stop[0].Extent.Text,
    [Text.UTF8Encoding]::new($false)
)

[IO.File]::WriteAllText(
    $args[2], $helper[0].Extent.Text,
    [Text.UTF8Encoding]::new($false)
)
"""

    extractor = tmp_path / "extract.ps1"
    action = tmp_path / "stop-action.ps1"
    helper = tmp_path / "owner-helper.ps1"

    extractor.write_text(extract, encoding="utf-8")

    extracted = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(extractor),
            str(MANAGER),
            str(action),
            str(helper),
        ],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert extracted.returncode == 0, extracted.stderr

    fixture = r"""
$ErrorActionPreference = "Stop"

$Action = "Stop"
$Root = "D:\Atlas-Isolated-Fixture"
$RuntimeDir = $PSScriptRoot
$OwnerPath = Join-Path $RuntimeDir "owner.json"
$StopLockPath = Join-Path $RuntimeDir "stop.lock"
$StopPath = Join-Path $RuntimeDir "stop.json"
$PowerShellPath = "powershell.exe"
$ManagerPath = "D:\Atlas-Isolated-Fixture\manager.ps1"

$runId = [guid]::NewGuid().ToString()

$owner = [pscustomobject]@{
    schema_version = 1
    root = $Root
    run_id = $runId
    pid = 43210
    state = "running"
}

function Get-VerifiedState {
    return @{
        state = "running"
        run_id = $runId
        pid = 43210
        owner = $owner
        message = "Verified isolated fixture"
    }
}

function Read-JsonFile([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path)) {
        return $null
    }
    return Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json
}

function Write-JsonAtomic($Value, [string]$Path) {
    $Value |
        ConvertTo-Json -Depth 8 |
        Set-Content -LiteralPath $Path -Encoding UTF8
}

function New-ExclusiveJsonFile($Value, [string]$Path) {
    if (Test-Path -LiteralPath $Path) {
        throw "Lock already exists."
    }
    Write-JsonAtomic $Value $Path
}

function Get-ProcessIdentity([int]$ProcessId) {
    return @{
        executable = "powershell.exe"
        command_line = "isolated-test"
        created_utc = "2026-10-16T00:00:00Z"
    }
}

function Start-Process {
    if ($env:A23_FAILURE_MODE -eq "throw") {
        throw "A23_INJECTED_LAUNCH_FAILURE"
    }
    return $null
}

function Write-Status($Value) {
    return $Value
}

. (Join-Path $PSScriptRoot "owner-helper.ps1")

$failureObserved = $false

try {
    . (Join-Path $PSScriptRoot "stop-action.ps1")
} catch {
    if ($_.Exception.Message -match "STOP_WORKER_LAUNCH_UNCONFIRMED") {
        $failureObserved = $true
    } else {
        throw
    }
}

if (-not $failureObserved) {
    throw "Expected stop-worker failure was not observed."
}

$persisted = Read-JsonFile $OwnerPath
$lock = Read-JsonFile $StopLockPath

if (-not $persisted -or -not $lock) {
    throw "Owner or stop-lock evidence missing."
}

if ($persisted.state -ne "stopping") {
    throw "Owner was not preserved in stopping state."
}

if ($persisted.PSObject.Properties["last_error"]) {
    throw "Parent unexpectedly persisted a launch-failure error."
}

if ($persisted.run_id -cne $runId -or
    $lock.run_id -cne $runId) {
    throw "Run ID changed."
}

if ($lock.phase -ne "requesting") {
    throw "Stop-lock phase changed unexpectedly."
}

if (Test-Path -LiteralPath $StopPath) {
    throw "Unexpected stop request created."
}

Write-Output "PASS: Failure remained fail-closed."
Write-Output "PASS: Owner and stop-lock evidence preserved."
"""

    fixture_path = tmp_path / "fixture.ps1"
    gate_module = str(ROOT / "scripts/windows/Atlas-CompleteShutdown.psm1").replace("'", "''")
    fixture_path.write_text(f"Import-Module '{gate_module}' -Force\n" + fixture, encoding="utf-8")

    import os

    environment = os.environ.copy()
    environment["A23_FAILURE_MODE"] = failure_mode

    result = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(fixture_path),
        ],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
        env=environment,
    )

    assert result.returncode == 0, result.stderr
    assert "PASS: Failure remained fail-closed." in result.stdout
    assert "PASS: Owner and stop-lock evidence preserved." in result.stdout

@pytest.mark.parametrize("scenario", ["requesting", "waiting", "completed"])
def test_parent_never_overwrites_worker_race_evidence(scenario, tmp_path):
    """Execute the production Stop action with simulated worker progress."""
    import os

    source = _manager_ast()
    assert "STOP_WORKER_LAUNCH_UNCONFIRMED" in source

    extract = r"""
$ErrorActionPreference = "Stop"
$tokens = $null
$errors = $null
$ast = [System.Management.Automation.Language.Parser]::ParseFile(
    $args[0], [ref]$tokens, [ref]$errors
)
if (@($errors).Count -gt 0) {
    throw "Manager parse failed."
}
$stop = @(
    $ast.EndBlock.Statements | Where-Object {
        $_ -is [System.Management.Automation.Language.IfStatementAst] -and
        $_.Extent.Text -match '^\s*if\s*\(\s*\$Action\s+-eq\s+["'']Stop["'']\s*\)'
    }
)
if ($stop.Count -ne 1) {
    throw "Expected exactly one Stop action."
}
[IO.File]::WriteAllText(
    $args[1], $stop[0].Extent.Text,
    [Text.UTF8Encoding]::new($false)
)
"""

    extractor = tmp_path / "extract.ps1"
    action = tmp_path / "stop-action.ps1"
    extractor.write_text(extract, encoding="utf-8")

    extracted = subprocess.run(
        [
            "powershell.exe", "-NoProfile", "-NonInteractive",
            "-ExecutionPolicy", "Bypass", "-File",
            str(extractor), str(MANAGER), str(action),
        ],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert extracted.returncode == 0, extracted.stderr

    fixture = r"""
$ErrorActionPreference = "Stop"
$Action = "Stop"
$Root = "D:\Atlas-Isolated-Fixture"
$RuntimeDir = $PSScriptRoot
$OwnerPath = Join-Path $RuntimeDir "owner.json"
$StopLockPath = Join-Path $RuntimeDir "stop.lock"
$StopPath = Join-Path $RuntimeDir "stop.json"
$PowerShellPath = "powershell.exe"
$ManagerPath = "D:\Atlas-Isolated-Fixture\manager.ps1"

$runId = [guid]::NewGuid().ToString()
$owner = [pscustomobject]@{
    schema_version = 1
    root = $Root
    run_id = $runId
    pid = 43210
    state = "running"
}

function Get-VerifiedState {
    return @{
        state = "running"
        run_id = $runId
        pid = 43210
        owner = $owner
        message = "Verified isolated fixture"
    }
}

function Read-JsonFile([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        return $null
    }
    Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json
}

function Write-JsonAtomic($Value, [string]$Path) {
    [IO.File]::WriteAllText(
        $Path,
        ($Value | ConvertTo-Json -Depth 8),
        [Text.UTF8Encoding]::new($false)
    )
}

function New-ExclusiveJsonFile($Value, [string]$Path) {
    if (Test-Path -LiteralPath $Path) {
        throw "Duplicate fixture stop lock."
    }
    Write-JsonAtomic $Value $Path
}

function Get-ProcessIdentity([int]$ProcessId) {
    return @{
        executable = "powershell.exe"
        command_line = "isolated-test"
        created_utc = "2026-10-16T00:00:00Z"
    }
}

function Start-Process {
    $lock = Read-JsonFile $StopLockPath

    if ($env:A23_RACE_SCENARIO -eq "waiting") {
        $lock.phase = "waiting"
        Write-JsonAtomic $lock $StopLockPath
    }

    if ($env:A23_RACE_SCENARIO -eq "completed") {
        Remove-Item -LiteralPath $OwnerPath -Force
        Remove-Item -LiteralPath $StopLockPath -Force
    }

    throw "A23_INJECTED_UNCONFIRMED_LAUNCH"
}

function Write-Status($Value) {
    return $Value
}

$observed = $false

try {
    . (Join-Path $PSScriptRoot "stop-action.ps1")
}
catch {
    if ($_.Exception.Message -match "STOP_WORKER_LAUNCH_UNCONFIRMED") {
        $observed = $true
    }
    else {
        throw
    }
}

if (-not $observed) {
    throw "Expected unconfirmed-launch diagnostic."
}

$persisted = Read-JsonFile $OwnerPath
$lock = Read-JsonFile $StopLockPath

if ($env:A23_RACE_SCENARIO -eq "completed") {
    if ($persisted -or $lock) {
        throw "Parent resurrected completed worker ownership."
    }
}
else {
    if (-not $persisted -or -not $lock) {
        throw "Parent removed unresolved ownership evidence."
    }

    if ($persisted.state -cne "stopping") {
        throw "Parent overwrote stopping state."
    }

    if ($persisted.run_id -cne $runId -or
        $lock.run_id -cne $runId) {
        throw "Run ID changed."
    }

    if ($lock.phase -cne $env:A23_RACE_SCENARIO) {
        throw "Parent overwrote worker lock phase."
    }

    if ($persisted.PSObject.Properties["last_error"]) {
        throw "Parent injected unexpected owner error."
    }
}

if (Test-Path -LiteralPath $StopPath) {
    throw "Unexpected stop request."
}

Write-Output "PASS: $env:A23_RACE_SCENARIO"
"""

    fixture_path = tmp_path / "fixture.ps1"
    gate_module = str(ROOT / "scripts/windows/Atlas-CompleteShutdown.psm1").replace("'", "''")
    fixture_path.write_text(f"Import-Module '{gate_module}' -Force\n" + fixture, encoding="utf-8")

    environment = os.environ.copy()
    environment["A23_RACE_SCENARIO"] = scenario

    result = subprocess.run(
        [
            "powershell.exe", "-NoProfile", "-NonInteractive",
            "-ExecutionPolicy", "Bypass", "-File", str(fixture_path),
        ],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
        env=environment,
    )

    assert result.returncode == 0, result.stderr
    assert f"PASS: {scenario}" in result.stdout
