import asyncio
import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from app.services.desktop_control import DesktopControl


def test_desktop_stop_requires_current_run_and_cleans_manifest(tmp_path, monkeypatch):
    import app.services.desktop_control as module
    signals = []
    monkeypatch.setattr(module.signal, "raise_signal", signals.append)
    control = DesktopControl(tmp_path, "current-run")

    async def run():
        await control.start()
        (tmp_path / "stop.json").write_text(json.dumps({"run_id": "old-run"}))
        assert not control.requested()
        (tmp_path / "stop.json").write_text(json.dumps({"run_id": "current-run"}))
        await asyncio.wait_for(control.task, timeout=2)
        await control.stop()

    asyncio.run(run())
    assert signals == [module.signal.SIGTERM]
    assert not (tmp_path / "runtime.json").exists()


def test_desktop_control_is_opt_in():
    control = DesktopControl()
    asyncio.run(control.start())
    assert control.task is None


def test_log_rotation_retains_bounded_files(tmp_path):
    config = json.loads(Path("deploy/logging-desktop.json").read_text())
    assert all(h["maxBytes"] == 20 * 1024 * 1024 and h["backupCount"] == 3
               for h in config["handlers"].values())
    handler = RotatingFileHandler(tmp_path / "api.log", maxBytes=128, backupCount=3)
    try:
        for _ in range(100):
            handler.emit(logging.makeLogRecord({"msg": "x" * 40}))
    finally:
        handler.close()
    assert len(list(tmp_path.glob("api.log*"))) == 4
    assert all(p.stat().st_size <= 128 for p in tmp_path.glob("api.log*"))


def test_normal_launcher_stabilizes_and_preserves_global_configuration():
    text = Path("scripts/windows/Atlas-Launch.ps1").read_text(encoding="utf-8")
    assert '"Atlas-Ready.ps1"' in text
    assert '"--log-config"' in text
    assert "    Ensure-WslMemoryCap\n" not in text
    assert "-RedirectStandardOutput $apiOut" not in text
