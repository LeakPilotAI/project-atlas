"""Durable JSON store for Quality Dips V2 alert state.

Persists only research notification state: the last V2 projection by symbol and the
last emitted event per dedupe key. It does not store credentials or brokerage data.
"""
from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from app.investment.storage import DATA_DIR, ensure_dirs

V2_ALERT_STATE_PATH = DATA_DIR / "quality_dips_v2_alert_state.json"


class QualityDipsV2AlertStore:
    def __init__(self, path: Path = V2_ALERT_STATE_PATH) -> None:
        self.path = path
        self.snapshots: Dict[str, Dict[str, Any]] = {}
        self.events: Dict[str, Dict[str, Any]] = {}
        self.load()

    def load(self) -> None:
        self.snapshots = {}
        self.events = {}
        if not self.path.exists():
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return
        if not isinstance(raw, dict):
            return
        if isinstance(raw.get("snapshots"), dict):
            self.snapshots = raw["snapshots"]
        if isinstance(raw.get("events"), dict):
            self.events = raw["events"]

    def save(self) -> None:
        ensure_dirs()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps({"snapshots": self.snapshots, "events": self.events}, indent=2, sort_keys=True),
            encoding="utf-8",
        )

    def previous(self, symbol: str) -> Optional[Dict[str, Any]]:
        row = self.snapshots.get(str(symbol or "").upper())
        return deepcopy(row) if isinstance(row, dict) else None

    def prior_event(self, dedupe_key: str) -> Optional[Dict[str, Any]]:
        row = self.events.get(str(dedupe_key or ""))
        return deepcopy(row) if isinstance(row, dict) else None

    def remember_snapshot(self, symbol: str, projection: Dict[str, Any]) -> None:
        sym = str(symbol or "").upper().strip()
        if not sym:
            return
        self.snapshots[sym] = deepcopy(projection or {})

    def mark_event(self, *, dedupe_key: str, delivered: bool, event_type: str, symbol: str, at: Optional[str] = None) -> None:
        key = str(dedupe_key or "").strip()
        if not key:
            return
        self.events[key] = {
            "dedupe_key": key,
            "event_type": event_type,
            "symbol": str(symbol or "").upper(),
            "last_at": at or datetime.now(timezone.utc).isoformat(),
            "delivered": bool(delivered),
        }


quality_dips_v2_alert_store = QualityDipsV2AlertStore()
