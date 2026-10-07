"""Durable runtime controls for PAPER risk only."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

CONTROL_PATH = Path(__file__).resolve().parents[2] / "data" / "paper_risk_controls.json"


class PaperRiskControlStore:
    def __init__(self, path: Path = CONTROL_PATH) -> None:
        self.path = path
        self.kill_switch = False
        self.session_net_r = 0.0
        self.load()

    def load(self) -> None:
        if not self.path.exists():
            return
        try:
            data=json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return
        if isinstance(data,dict):
            self.kill_switch=bool(data.get("kill_switch"))
            try:self.session_net_r=float(data.get("session_net_r") or 0.0)
            except Exception:self.session_net_r=0.0

    def save(self) -> None:
        self.path.parent.mkdir(parents=True,exist_ok=True)
        tmp=self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"kill_switch":self.kill_switch,"session_net_r":self.session_net_r},indent=2),encoding="utf-8")
        tmp.replace(self.path)

    def snapshot(self) -> dict[str,Any]:
        return {"kill_switch":self.kill_switch,"session_net_r":self.session_net_r}


paper_risk_controls=PaperRiskControlStore()
