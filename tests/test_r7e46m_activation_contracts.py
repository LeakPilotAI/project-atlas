"""Activation/rollback readiness without any real Atlas lifecycle invocation."""

import asyncio
import json
import subprocess
import threading
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest
from app.investment import extended_hours_collector as collector_module
from app.services import extended_hours_research as service_module

ROOT = Path(__file__).resolve().parents[1]
FLAG = "ATLAS_EXTENDED_HOURS_RESEARCH_ENABLED"
NOW = datetime(2026, 10, 16, 8, tzinfo=ZoneInfo("America/New_York"))


@pytest.mark.parametrize("value,enabled", [
    (None, False), ("false", False), ("0", False), ("unknown", False),
    ("true", True), (" TRUE ", True), ("1", True), ("yes", True), ("on", True),
])
def test_explicit_feature_flag_only(monkeypatch, value, enabled):
    monkeypatch.setenv("ATLAS_GAMING_MODE", "true")
    monkeypatch.delenv(FLAG, raising=False)
    if value is not None:
        monkeypatch.setenv(FLAG, value)
    assert service_module.enabled_from_environment() is enabled


def make_service(collector):
    return service_module.ExtendedHoursResearchService(
        collector=collector,
        universe_loader=lambda: SimpleNamespace(symbols=lambda **kw: ["TEST"]),
    )


@pytest.mark.asyncio
async def test_disabled_service_has_no_provider_or_journal_side_effect(monkeypatch, tmp_path):
    monkeypatch.delenv(FLAG, raising=False)

    class Forbidden:
        output_path = tmp_path / "research.jsonl"

        async def collect_once(self, *args, **kwargs):
            raise AssertionError("disabled collector invoked")

    service = make_service(Forbidden())
    assert await service.start() is False
    state = service.status()
    assert state["state"] == "DISABLED" and state["running"] is False
    assert state["activation_enabled"] is False
    assert not list(tmp_path.iterdir())
    await service.stop()


@pytest.mark.asyncio
async def test_service_reports_failure_and_gracefully_stops(monkeypatch):
    monkeypatch.setenv(FLAG, "true")
    monkeypatch.setattr(service_module, "extended_session", lambda now: "PRE_MARKET")
    tried = asyncio.Event()

    class Failure:
        async def collect_once(self, *args, **kwargs):
            tried.set()
            raise OSError("fixture disk failure")

    service = make_service(Failure())
    assert await service.start()
    await asyncio.wait_for(tried.wait(), timeout=3)
    await asyncio.sleep(0)
    state = service.status()
    assert state["state"] == "DEGRADED" and state["failed_cycles"] == 1
    assert state["last_error"] == "OSError"
    assert state["committed_observations"] == 0
    assert state["execution_authority"] is False
    assert state["automatic_discord_delivery"] is False
    await service.stop()
    assert not service.status()["task_active"]


@pytest.mark.asyncio
async def test_actual_status_endpoint_is_observational(monkeypatch):
    from app.api.diagnostics import diagnostics_extended_hours

    expected = {"contract_version": "fixture", "running": False}
    monkeypatch.setattr(service_module, "extended_hours_research_service",
                        SimpleNamespace(status=lambda: expected))
    assert await diagnostics_extended_hours() == expected


class Quotes:
    def __init__(self, price=250):
        self.price = price

    async def get_many(self, symbols):
        return {s: {"price": self.price, "effective_timestamp": NOW.isoformat(),
                    "quality": "LIVE", "source": "isolated"} for s in symbols}


@pytest.mark.asyncio
async def test_validation_clock_is_after_provider_fetch(monkeypatch, tmp_path):
    clock = [NOW]
    monkeypatch.setattr(collector_module, "datetime", SimpleNamespace(
        now=lambda zone: clock[0].astimezone(zone),
        fromisoformat=datetime.fromisoformat,
    ))

    class LaterQuotes(Quotes):
        async def get_many(self, symbols):
            clock[0] += timedelta(seconds=2)
            return {s: {"price": 250, "effective_timestamp": clock[0].isoformat(),
                        "quality": "LIVE", "source": "isolated"} for s in symbols}

    collector = collector_module.ExtendedHoursCollector(LaterQuotes(), tmp_path / "history.jsonl")
    rows = await collector.collect_once(["TEST"])
    assert len(rows) == 1 and rows[0]["age_sec"] == 0


@pytest.mark.asyncio
async def test_cancellation_drains_commit_without_blocking_event_loop(tmp_path):
    entered, release, finished = threading.Event(), threading.Event(), threading.Event()
    collector = collector_module.ExtendedHoursCollector(Quotes(), tmp_path / "history.jsonl")
    original = collector._commit_with_lock

    def paused(*args):
        entered.set()
        if not release.wait(5):
            raise TimeoutError("test writer release missing")
        result = original(*args)
        finished.set()
        return result

    collector._commit_with_lock = paused
    task = asyncio.create_task(collector.collect_once(["TEST"], now=NOW))
    try:
        assert await asyncio.to_thread(entered.wait, 3)
        # The event loop stays responsive while the writer holds a thread.
        task.cancel()
        await asyncio.sleep(0)
        task.cancel()  # repeated cancellation must not orphan the writer
        await asyncio.sleep(0)
        assert not task.done()
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, 3)
        assert finished.is_set()
        assert len(collector.output_path.read_text().splitlines()) == 1
    finally:
        release.set()
        if not task.done():
            await asyncio.gather(task, return_exceptions=True)


@pytest.mark.parametrize("corruption", ["duplicate", "wrong_authority", "missing_price"])
def test_semantic_corruption_preserved_and_append_blocked(tmp_path, corruption):
    path = tmp_path / "history.jsonl"
    collector = collector_module.ExtendedHoursCollector(Quotes(), path)
    asyncio.run(collector.collect_once(["TEST"], now=NOW))
    row = json.loads(path.read_text())
    if corruption == "duplicate":
        path.write_text(path.read_text() + json.dumps(row) + "\n")
    else:
        if corruption == "wrong_authority":
            row["research_only"] = False
        else:
            row.pop("price")
        path.write_text(json.dumps(row) + "\n")
    before = path.read_bytes()
    with pytest.raises(ValueError):
        asyncio.run(collector.collect_once(["TEST"], now=NOW))
    assert path.read_bytes() == before


@pytest.mark.parametrize("opt_in,prior,fail", [
    (False, "true", False), (False, None, False),
    (True, "false", False), (False, "true", True), (True, None, True),
])
def test_actual_start_branch_sanitizes_and_restores_flag(tmp_path, opt_in, prior, fail):
    """Execute the actual Start AST with a fake Start-Process; no child is launched."""
    manager = str(ROOT / "scripts/windows/Atlas-Background.ps1").replace("'", "''")
    script = tmp_path / "start-contract.ps1"
    prior_literal = "$null" if prior is None else f"'{prior}'"
    script.write_text(rf"""
$ErrorActionPreference='Stop'
Import-Module '{str(ROOT / "scripts/windows/Atlas-CompleteShutdown.psm1").replace("'", "''")}' -Force
$Root='{str(tmp_path).replace("'", "''")}';$RuntimeDir=$Root
$LockPath='fixture';$ManagerPath='fixture-manager';$PowerShellPath='fixture-powershell'
$EnableExtendedHoursResearch=${str(opt_in).lower()}
[Environment]::SetEnvironmentVariable('{FLAG}',{prior_literal},'Process')
function Assert-CleanStart {{ }}
function Get-ProcessIdentity($ProcessId) {{return @{{executable='fixture';command_line='fixture';created_utc='fixture'}}}}
function New-ExclusiveJsonFile($Value,$Path) {{ }}
function Remove-OwnedFile($Path,$RunId) {{ }}
function Write-Status($Value) {{ }}
function Start-Process {{
 $script:observed=[Environment]::GetEnvironmentVariable('{FLAG}','Process')
 if (${str(fail).lower()}) {{throw 'fake launch failure'}}
 return [pscustomobject]@{{Id=12345}}
}}
$tokens=$null;$errors=$null
$ast=[Management.Automation.Language.Parser]::ParseFile('{manager}',[ref]$tokens,[ref]$errors)
if($errors.Count){{throw 'parse error'}}
$branch=@($ast.EndBlock.Statements|Where-Object {{$_ -is [Management.Automation.Language.IfStatementAst] -and $_.Clauses[0].Item1.Extent.Text -ceq '$Action -eq "Start"'}})
if($branch.Count -ne 1){{throw 'Start branch not unique'}}
$failed=$false
try {{ & ([scriptblock]::Create($branch[0].Clauses[0].Item2.Extent.Text.Trim('{{','}}'))) }}
catch {{$failed=$true}}
@{{observed=$script:observed;restored=[Environment]::GetEnvironmentVariable('{FLAG}','Process');failed=$failed}}|ConvertTo-Json -Compress
""", encoding="utf-8-sig")
    result = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy",
                             "Bypass", "-File", str(script)], capture_output=True, text=True,
                            timeout=15, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
    data = json.loads(result.stdout)
    assert data["observed"] == ("true" if opt_in else "false")
    assert data["restored"] == prior
    assert data["failed"] is fail


def test_gui_never_implicitly_enables_extended_hours():
    controls = (ROOT / "scripts/windows/Atlas-Background-Controls.ps1").read_text()
    assert "-EnableExtendedHoursResearch" not in controls
    gaming = (ROOT / "scripts/windows/Atlas-Background-Gaming.ps1").read_text()
    assert "$researchArgument = if ($EnableExtendedHoursResearch)" in gaming


@pytest.mark.parametrize("opt_in", [False, True])
def test_gaming_wrapper_forwards_only_explicit_opt_in_to_fake_manager(tmp_path, opt_in):
    launcher = tmp_path / "Atlas-Background-Gaming.ps1"
    launcher.write_bytes((ROOT / "scripts/windows/Atlas-Background-Gaming.ps1").read_bytes())
    manager = tmp_path / "Atlas-Background.ps1"
    manager.write_text(r"""
param([string]$Action,[switch]$EnableExtendedHoursResearch)
@{explicit_opt_in=[bool]$EnableExtendedHoursResearch;gaming=$env:ATLAS_GAMING_MODE;action=$Action}|
 ConvertTo-Json|Set-Content (Join-Path $PSScriptRoot 'fixture-result.json')
""", encoding="utf-8-sig")
    fixture = tmp_path / "invoke.ps1"
    fixture.write_text(rf"""
$ErrorActionPreference='Stop'
$env:ATLAS_GAMING_MODE='false';$env:ATLAS_EXTENDED_HOURS_RESEARCH_ENABLED='true'
& '{str(launcher).replace("'", "''")}' -Action Start -EnableExtendedHoursResearch:${str(opt_in).lower()}
if($env:ATLAS_GAMING_MODE -cne 'false'){{throw 'Parent gaming flag changed'}}
if($env:ATLAS_EXTENDED_HOURS_RESEARCH_ENABLED -cne 'true'){{throw 'Parent research flag changed'}}
""", encoding="utf-8-sig")
    result = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy",
                             "Bypass", "-File", str(fixture)], capture_output=True, text=True,
                            timeout=20, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
    data = json.loads((tmp_path / "fixture-result.json").read_text(encoding="utf-8-sig"))
    assert data == {"explicit_opt_in": opt_in, "gaming": "true", "action": "Start"}
