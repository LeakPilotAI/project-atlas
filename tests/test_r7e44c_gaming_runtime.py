"""Read-only API-process gaming diagnostic: fake settings/tasks, no live runtime."""

import asyncio
from types import SimpleNamespace

import pytest
from app.api.diagnostics import diagnostics_gaming_runtime, router


@pytest.mark.parametrize("gaming,scan,active,expected", [
    (True, 60, True, 180), (True, 300, True, 300), (False, 60, False, 60),
])
def test_allowlisted_runtime_settings_and_task_state(monkeypatch, gaming, scan, active, expected):
    from app.core import config
    from app.services import perp_micro_coach as module

    settings = config.Settings(_env_file=None, atlas_gaming_mode=gaming,
                               perp_micro_scan_seconds=scan, perp_micro_manage_seconds=8)
    monkeypatch.setattr(config, "get_settings", lambda: settings)
    task = SimpleNamespace(done=lambda: not active)
    coach = SimpleNamespace(running=active, _task=task, _manage_task=task)
    monkeypatch.setattr(module, "perp_micro_coach", coach)
    monkeypatch.setenv("ATLAS_GAMING_MODE", str(gaming).lower())
    monkeypatch.setenv("ATLAS_DESKTOP_RUN_ID", "fixture-run")
    monkeypatch.setenv("DISCORD_TOKEN", "must-never-appear")
    result = asyncio.run(diagnostics_gaming_runtime())
    assert result["gaming_mode"] is gaming
    assert result["gaming_environment"] == str(gaming).lower()
    assert result["effective_discovery_seconds"] == expected
    assert result["management_seconds"] == 8
    assert result["paper_management_enabled"] is True
    assert result["management_task_active"] is active
    assert result["discovery_task_active"] is active
    assert result["run_id"] == "fixture-run"
    assert result["read_only"] is True and result["execution_authority"] is False
    assert "must-never-appear" not in str(result)
    assert set(result) == {
        "pid", "run_id", "gaming_environment", "gaming_mode", "configured_discovery_seconds",
        "effective_discovery_seconds", "management_seconds", "paper_management_enabled",
        "coach_running", "discovery_task_active", "management_task_active", "read_only",
        "execution_authority",
    }


def test_runtime_observation_has_only_get_route():
    matches = [r for r in router.routes if r.path == "/diagnostics/gaming-runtime"]
    assert len(matches) == 1
    assert matches[0].methods == {"GET"}
