from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8-sig")


def test_desktop_launch_contract_is_intact():
    batch = _read("ATLAS.bat")
    launch = _read("scripts/windows/Atlas-Launch.ps1")

    assert "Atlas-Launch.ps1" in batch
    assert "Atlas-Stop.ps1" in batch
    assert '$Backend = Join-Path $Root "backend"' in launch
    assert '$VenvPy = Join-Path $Backend ".venv\\Scripts\\python.exe"' in launch
    assert '"-m", "uvicorn", "app.main:app"' in launch
    assert '"--host", "127.0.0.1"' in launch
    assert '"--port", "8000"' in launch
    assert 'Wait-Http "http://127.0.0.1:8000/health"' in launch
    assert 'Start-Process "http://127.0.0.1:8000/dashboard?v=desk-v7"' in launch


def test_desktop_stop_contract_preserves_other_apps():
    batch = _read("ATLAS-STOP.bat")
    stop = _read("scripts/windows/Atlas-Stop.ps1")

    assert "Atlas-Stop.ps1" in batch
    assert "Never quits Docker Desktop or Genesis" in stop
    assert "Stop-ListenPort 8000" in stop
    assert "Stop-ListenPort 3000" in stop
    assert "docker compose down --remove-orphans" in stop
    assert "Docker Desktop / Genesis were not touched" in stop


def test_quality_dips_v2_closure_keeps_manual_only_boundary():
    files = [
        _read("backend/app/investment/quality_dips_v2_board.py"),
        _read("backend/app/investment/quality_dips_v2_alerts.py"),
        _read("backend/app/services/quality_dip_scanner.py"),
    ]
    joined = "\n".join(files)

    assert "MANUAL_ONLY" in joined
    assert "live_capital_allowed" in joined
    assert "automatic_real_money_execution" in joined
    assert "place_order" not in joined
    assert "submit_order" not in joined
    assert "execute_trade" not in joined


def test_closed_historical_perps_result_remains_preserved_in_roadmap():
    roadmap = _read("PROJECT_ATLAS_MASTER_ROADMAP.txt")
    assert "FAILED_NEGATIVE" in roadmap
    assert "closed and immutable" in roadmap
    assert "does not relabel, retune, or overwrite those results" in roadmap
