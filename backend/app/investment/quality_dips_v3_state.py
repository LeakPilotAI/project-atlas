"""Durable state for Quality Dips V3 research transitions and entry-level hits.

Append-safe JSON snapshot store. Research notifications only; no broker orders.
"""
from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.investment.storage import DATA_DIR, ensure_dirs

STATE_PATH = DATA_DIR / "quality_dips_v3_state.json"


class QualityDipsV3StateStore:
    def __init__(self, path: Path = STATE_PATH) -> None:
        self.path = path
        self.snapshots: dict[str, dict[str, Any]] = {}
        self.events: dict[str, dict[str, Any]] = {}
        self.load()

    def load(self) -> None:
        self.snapshots, self.events = {}, {}
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8")) if self.path.exists() else {}
            if isinstance(raw.get("snapshots"), dict):
                self.snapshots = raw["snapshots"]
            if isinstance(raw.get("events"), dict):
                self.events = raw["events"]
        except Exception:
            self.snapshots, self.events = {}, {}

    def save(self) -> None:
        ensure_dirs()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps({"snapshots": self.snapshots, "events": self.events}, indent=2, sort_keys=True), encoding="utf-8")
        tmp.replace(self.path)

    def previous(self, symbol: str) -> dict[str, Any] | None:
        row = self.snapshots.get(str(symbol or "").upper())
        return deepcopy(row) if isinstance(row, dict) else None

    def remember(self, symbol: str, plan: dict[str, Any]) -> None:
        sym = str(symbol or "").upper().strip()
        if sym:
            self.snapshots[sym] = deepcopy(plan)

    def event_seen(self, key: str) -> bool:
        return str(key or "") in self.events

    def mark_event(self, key: str, *, symbol: str, event_type: str, payload: dict[str, Any] | None = None) -> None:
        if not key:
            return
        self.events[key] = {
            "key": key,
            "symbol": str(symbol or "").upper(),
            "event_type": event_type,
            "at": datetime.now(timezone.utc).isoformat(),
            "payload": deepcopy(payload or {}),
        }

    def get_event(self, key: str) -> dict[str, Any] | None:
        row = self.events.get(str(key or ""))
        return deepcopy(row) if isinstance(row, dict) else None


def detect_v3_events(previous: dict[str, Any] | None, current: dict[str, Any]) -> list[dict[str, Any]]:
    sym = str(current.get("symbol") or "").upper()
    prev_state = str((previous or {}).get("patient_state") or "WATCH").upper()
    cur_state = str(current.get("patient_state") or "WATCH").upper()
    out: list[dict[str, Any]] = []
    rank = {"WATCH": 0, "ACCUMULATION": 1, "DEEP_VALUE": 2, "GENERATIONAL": 3}
    if rank.get(cur_state, 0) > rank.get(prev_state, 0):
        out.append({"event_type": "STATE_IMPROVED", "symbol": sym, "state": cur_state, "key": f"V3:{sym}:STATE:{cur_state}"})

    prev_levels = {
        str(x.get("level") or "").upper(): bool(x.get("reached"))
        for x in ((previous or {}).get("entry_ladder") or {}).get("levels", [])
    }
    for level in (current.get("entry_ladder") or {}).get("levels", []):
        name = str(level.get("level") or "").upper()
        if bool(level.get("reached")) and not prev_levels.get(name, False):
            out.append({
                "event_type": "ENTRY_LEVEL_REACHED",
                "symbol": sym,
                "level": name,
                "limit_price": level.get("limit_price"),
                "key": f"V3:{sym}:LEVEL:{name}",
            })
    return out


quality_dips_v3_state_store = QualityDipsV3StateStore()
