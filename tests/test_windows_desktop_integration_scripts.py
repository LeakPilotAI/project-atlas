from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8-sig")


def test_launcher_is_api_served_and_preserves_docker_desktop():
    text = _text("scripts/windows/Atlas-Launch.ps1")
    assert '"-m", "uvicorn", "app.main:app"' in text
    assert 'http://127.0.0.1:8000/health' in text
    assert 'http://127.0.0.1:8000/dashboard?v=desk-v7' in text
    assert 'Docker Desktop and other apps (Genesis, etc.) stay running.' in text
    assert 'Start-Process "http://127.0.0.1:3000' not in text


def test_stop_script_scopes_shutdown_to_atlas():
    text = _text("scripts/windows/Atlas-Stop.ps1")
    assert '$env:COMPOSE_PROJECT_NAME = "atlas"' in text
    assert 'docker stop atlas-postgres atlas-redis' in text
    assert 'Docker Desktop / Genesis were not touched.' in text
    assert 'Stop-Process -Name "Docker Desktop"' not in text


def test_shortcut_installer_targets_root_batch_files():
    text = _text("scripts/windows/Install-DesktopShortcut.ps1")
    assert '"Project Atlas.lnk"' in text
    assert '"Stop Atlas.lnk"' in text
    assert '$s.TargetPath = $LaunchBat' in text
    assert '$t.TargetPath = $StopBat' in text


def test_desktop_smoke_is_fail_closed_and_no_live():
    text = _text("scripts/windows/Atlas-Desktop-Smoke.ps1")
    for endpoint in ("/health", "/dashboard", "/api/research", "/api/command-center/summary"):
        assert endpoint in text
    assert 'paper_shadow_only = $true' in text
    assert 'live_capital_allowed = $false' in text
    assert 'automatic_real_money_execution = $false' in text
    assert 'ATLAS_DESKTOP_SMOKE_BLOCKED' in text
    assert 'exit 2' in text


def test_desktop_smoke_supports_longevity_and_reconciliation_probes():
    text = _text("scripts/windows/Atlas-Desktop-Smoke.ps1")
    assert "[int]$LongevitySeconds = 0" in text
    assert "[int]$ProbeIntervalSeconds = 15" in text
    assert "/diagnostics/paper-reconciliation" in text
    assert "longevity = $longevity" in text
    assert "$longevity.green" in text


def test_desktop_smoke_can_self_start_and_reports_probe_progress():
    text = _text("scripts/windows/Atlas-Desktop-Smoke.ps1")
    assert "[switch]$StartAtlasIfNeeded" in text
    assert "starting an isolated desktop launcher" in text
    assert "Longevity probe" in text
    assert "auto_started_atlas" in text


def test_desktop_smoke_self_start_isolated_from_validation_console_ctrl_c():
    text = _text("scripts/windows/Atlas-Desktop-Smoke.ps1")
    assert '$LauncherScript = Join-Path $PSScriptRoot "Atlas-Launch.ps1"' in text
    assert 'Start-Process -FilePath "powershell.exe"' in text
    assert '("-File", (' not in text  # guard against malformed tuple-style PowerShell
    assert '"-File", (\'"{0}"\' -f $LauncherScript)' in text
    assert "-WorkingDirectory $Root -WindowStyle Hidden -PassThru" in text
    assert "Start-Process -FilePath $LaunchBat -WindowStyle Hidden -PassThru" not in text


def test_desktop_smoke_captures_first_failure_diagnostics():
    text = _text("scripts/windows/Atlas-Desktop-Smoke.ps1")
    assert "first_failure_probe" in text
    assert "failure_snapshot" in text
    assert "api_processes" in text
    assert "api_err_tail" in text
    assert "api_out_tail" in text
    assert "captured failure snapshot" in text


def test_desktop_smoke_distinguishes_transient_probe_failure_and_persists_artifact():
    text = _text("scripts/windows/Atlas-Desktop-Smoke.ps1")
    assert "failed_probe_count" in text
    assert "max_consecutive_failed_probes" in text
    assert "recovered_after_failure" in text
    assert "$probeFailed" in text
    assert "GREEN (runtime recovered after earlier transient failure)" in text
    assert "desktop-smoke-latest.json" in text


def test_desktop_smoke_keeps_diagnostics_compact_and_tracks_launcher():
    text = _text("scripts/windows/Atlas-Desktop-Smoke.ps1")
    assert "[System.IO.File]::ReadLines($Path)" in text
    assert "launcher_process_id" in text
    assert "launcher_alive" in text
    assert "ConvertTo-Json -Depth 12" in text
    assert "Get-Content $Path -Tail" not in text


def test_desktop_smoke_captures_port_owner_and_process_tree():
    text = _text("scripts/windows/Atlas-Desktop-Smoke.ps1")
    assert "Get-ApiPortOwnershipSnapshot" in text
    assert "Get-NetTCPConnection -LocalPort 8000 -State Listen" in text
    assert "owning_pid" in text
    assert "parent_pid" in text
    assert "parent_command_line" in text
    assert "Get-ApiProcessTreeSnapshot" in text
    assert "owns_port_8000" in text
    assert "port_8000_listeners" in text
    assert "api_process_tree" in text


def test_desktop_smoke_does_not_assign_reserved_powershell_pid_variable():
    text = _text("scripts/windows/Atlas-Desktop-Smoke.ps1")
    assert "$ownerPid = [int]$_.OwningProcess" in text
    assert "$processId = [int]$p.ProcessId" in text
    assert "$pid = [int]$_.OwningProcess" not in text
    assert "$pid = [int]$p.ProcessId" not in text


def test_stop_never_kills_by_generic_server_name_or_port():
    text = _text("scripts/windows/Atlas-Stop.ps1")
    assert "Stop-ListenPort" not in text
    assert '$markers = @("uvicorn"' not in text
    assert "Test-AtlasProcess" in text
    assert '$exe -ieq $VenvPy' in text
    assert '$cl.IndexOf($Root + "\\"' in text


def test_startup_gate_precedes_measured_clock_and_is_fail_closed():
    text = _text("scripts/windows/Atlas-Desktop-Smoke.ps1")
    assert text.index("$stabilization =") < text.index("$longevity.started_at =")
    assert "if ($stabilization.green -and $longevity.requested_seconds -gt 0)" in text
    assert "green = $stabilization.green" in text
    assert "$stabilization.consecutive_green=0" in text
    assert "startup_stabilization = $stabilization" in text


def test_runtime_diagnostic_captures_json_body():
    text = _text("scripts/windows/Atlas-Desktop-Smoke.ps1")
    assert '$r.Content | ConvertFrom-Json' in text
    assert 'runtime_latency = Test-Http "http://127.0.0.1:8000/diagnostics/runtime-latency" -IncludeBody' in text


def test_longevity_verifies_runtime_ownership_and_reported_safety():
    text = _text("scripts/windows/Atlas-Desktop-Smoke.ps1")
    assert "$runtime = Test-RuntimeOwnership" in text
    assert "$longevity.runtime_failures++" in text
    assert "$listenerOk -and $containersOk" in text
    assert "$result.safety_verified -and" in text
    assert "$safetyBody.live_capital_allowed -eq $false" in text
    assert "$safetyBody.automatic_real_money_execution -eq $false" in text
