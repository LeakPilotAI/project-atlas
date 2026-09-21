"""Local desktop shutdown handshake; no HTTP or trading control surface."""
import asyncio
import json
import os
from pathlib import Path
import signal


class DesktopControl:
    def __init__(self, directory=None, run_id=None):
        self.directory = Path(directory) if directory else None
        self.run_id = run_id
        self.task = None

    async def start(self):
        if self.directory is None or not self.run_id:
            return
        self.directory.mkdir(parents=True, exist_ok=True)
        manifest = {"pid": os.getpid(), "run_id": self.run_id}
        (self.directory / "runtime.json").write_text(json.dumps(manifest), encoding="utf-8")
        self.task = asyncio.create_task(self._watch(), name="atlas-desktop-stop")

    def requested(self):
        try:
            request = json.loads((self.directory / "stop.json").read_text(encoding="utf-8-sig"))
            return request.get("run_id") == self.run_id
        except (OSError, ValueError, TypeError):
            return False

    async def _watch(self):
        while True:
            if self.requested():
                # Uvicorn handles SIGTERM on the main thread and runs lifespan cleanup.
                signal.raise_signal(signal.SIGTERM)
                return
            await asyncio.sleep(0.5)

    async def stop(self):
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        if self.directory:
            manifest = self.directory / "runtime.json"
            try:
                if json.loads(manifest.read_text(encoding="utf-8")).get("run_id") == self.run_id:
                    manifest.unlink()
            except (OSError, ValueError):
                pass
