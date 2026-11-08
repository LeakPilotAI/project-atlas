"""Guard the desktop shortcut against silent PAPER activation or startup regressions."""
from pathlib import Path


LAUNCHER = (Path(__file__).resolve().parents[1] / "scripts" / "windows"
            / "Atlas-Observation-Shortcut.ps1")


def test_launcher_preflights_before_starting_observation():
    source = LAUNCHER.read_text(encoding="utf-8-sig")
    assert source.index("personal_installation_preflight") < source.index("Open-AtlasObservationDashboard $root")
    assert 'ConvertFrom-Json' in source
    assert 'forward_financial_write_authorized -ne $false' in source
    assert 'live_order_authorized -ne $false' in source
    assert 'PAPER prerequisites: UNVERIFIED' in source


def test_launcher_is_observation_only_and_owned():
    source = LAUNCHER.read_text(encoding="utf-8-sig")
    assert 'Open-AtlasObservationDashboard $root -BoundedDataOnly' in source
    assert 'PAPER trading: DISABLED' in source
    assert 'Production trading: DISABLED' in source
    assert 'Local\\AtlasObservationOwner_$sid' in source
    assert 'Local\\AtlasObservationStop_$sid' in source
    assert 'Close-AtlasObservationDashboard' in source
    for forbidden in ('publish_personal_activation', 'execute_broker_order',
                      'initialize_paper_account', 'Start-Atlas.ps1',
                      'Atlas-Start.ps1', 'docker compose', 'Project-Genesis'):
        assert forbidden not in source


def test_launcher_preflight_uses_repo_python_and_restores_environment():
    source = LAUNCHER.read_text(encoding="utf-8-sig")
    assert 'backend\\.venv\\Scripts\\python.exe' in source
    assert '$env:PYTHONPATH = "$root\\backend;$root"' in source
    assert '$env:PYTHONPATH = $priorPythonPath' in source
