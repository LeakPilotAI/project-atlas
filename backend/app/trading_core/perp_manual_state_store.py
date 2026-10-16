from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Iterable


STATE_VERSION = 1


class ManualPerpStateError(RuntimeError):
    pass


def _setup_history_row(raw: dict[str, Any]) -> dict[str, Any]:
    """Persist lifecycle identity/cooldown only, never stale market/level data."""
    keys = (
        "setup_key",
        "symbol",
        "side",
        "tier",
        "state",
        "first_seen_at",
        "last_seen_at",
        "last_alert_at",
        "previous_tier",
        "previous_state",
    )
    return {key: raw.get(key) for key in keys if key in raw}


class ManualPerpStateStore:
    """Small crash-safe snapshot store for the manual Hyperliquid workflow.

    This store is intentionally separate from the V4 paper event journal. It keeps
    user-confirmed manual plans/trades plus setup alert lifecycle metadata across
    application restarts. Live market rows, marks, scores, and entry candidates are
    deliberately not persisted as live truth.
    """

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"version": STATE_VERSION, "plans": [], "setup_history": []}
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ManualPerpStateError("manual perp state is unreadable") from exc
        if not isinstance(raw, dict):
            raise ManualPerpStateError("manual perp state must be a JSON object")
        if int(raw.get("version") or 0) != STATE_VERSION:
            raise ManualPerpStateError("unsupported manual perp state version")
        plans = raw.get("plans") or []
        history = raw.get("setup_history") or []
        if not isinstance(plans, list) or not all(isinstance(row, dict) for row in plans):
            raise ManualPerpStateError("manual perp plans must be a list of objects")
        if not isinstance(history, list) or not all(isinstance(row, dict) for row in history):
            raise ManualPerpStateError("manual perp setup history must be a list of objects")
        return {
            "version": STATE_VERSION,
            "plans": [dict(row) for row in plans[:100]],
            "setup_history": [dict(row) for row in history[:100]],
        }

    def save(
        self,
        *,
        plans: Iterable[dict[str, Any]],
        setup_history: Iterable[dict[str, Any]],
    ) -> None:
        payload = {
            "version": STATE_VERSION,
            "plans": [dict(row) for row in list(plans)[:100]],
            "setup_history": [_setup_history_row(dict(row)) for row in list(setup_history)[:100]],
        }
        encoded = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ) + "\n"
        tmp = self.path.with_name(self.path.name + ".tmp")
        try:
            with tmp.open("w", encoding="utf-8") as handle:
                handle.write(encoded)
                handle.flush()
                try:
                    os.fsync(handle.fileno())
                except OSError:
                    pass
            os.replace(tmp, self.path)
        except Exception:
            try:
                if tmp.exists():
                    tmp.unlink()
            except OSError:
                pass
            raise
