"""Durable runtime controls for PAPER risk only."""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.core.durable_io import sync_parent, write_flushed

CONTROL_PATH = Path(__file__).resolve().parents[2] / "data" / "paper_risk_controls.json"


class PaperRiskControlStore:
    def __init__(self, path: Path = CONTROL_PATH) -> None:
        self.path = path
        self.kill_switch = False
        self.session_net_r = 0.0
        self.reliable = True
        self._write_failed = False
        self.load()

    def load(self) -> None:
        if self._write_failed:
            raise RuntimeError("PAPER control persistence requires independent reconciliation")
        if not self.path.exists():
            return
        try:
            data=json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError, RecursionError):
            self.reliable = False
            return
        try:
            if not isinstance(data, dict) or type(data.get("kill_switch")) is not bool:
                raise ValueError("Invalid kill-switch evidence")
            value = data["session_net_r"]
            if isinstance(value, bool):
                raise TypeError("Invalid session loss evidence")
            session_net_r = float(value)
            if not math.isfinite(session_net_r):
                raise ValueError("Nonfinite session loss evidence")
        except (KeyError, TypeError, ValueError, OverflowError):
            self.reliable = False
            return
        self.kill_switch = data["kill_switch"]
        self.session_net_r = session_net_r
        self.reliable = True

    def save(self) -> None:
        if self._write_failed or not self.reliable:
            raise RuntimeError("PAPER control persistence requires independent reconciliation")
        try:
            if type(self.kill_switch) is not bool or isinstance(self.session_net_r, bool):
                raise ValueError("Invalid PAPER controls")
            value = float(self.session_net_r)
            if not math.isfinite(value):
                raise ValueError("Invalid session loss evidence")
            text = json.dumps({"kill_switch": self.kill_switch, "session_net_r": value},
                              indent=2, allow_nan=False)
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_name(self.path.name + "." + uuid4().hex + ".tmp")
            with tmp.open("x", encoding="utf-8") as stream:
                write_flushed(stream, text)
            tmp.replace(self.path)
            sync_parent(self.path)
        except BaseException:
            self.reliable = False
            self._write_failed = True
            raise
        self.session_net_r = value
        self.reliable = True

    def snapshot(self) -> dict[str,Any]:
        return {"kill_switch":self.kill_switch,"session_net_r":self.session_net_r,"reliable":self.reliable}


paper_risk_controls=PaperRiskControlStore()
