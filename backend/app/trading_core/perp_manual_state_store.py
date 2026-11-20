from __future__ import annotations

import json
import os
import uuid
from pathlib import Path
from typing import Any, Iterable

from app.core.durable_io import sync_parent, write_flushed


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
    """Validated snapshot publication for the manual Hyperliquid workflow.

    This store is intentionally separate from the V4 paper event journal. It keeps
    user-confirmed manual plans/trades plus setup alert lifecycle metadata across
    application restarts. Live market rows, marks, scores, and entry candidates are
    deliberately not persisted as live truth. File flush/publication acknowledgement
    is not a guarantee against hardware failure or Windows namespace loss.
    """

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.pending_path = self.path.with_name(self.path.name + ".pending")
        self.persistence_error: BaseException | None = None

    def load(self) -> dict[str, Any]:
        if self.pending_path.exists() or self.path.with_name(self.path.name + ".tmp").exists() or next(
            self.path.parent.glob(self.path.name + ".*.tmp"), None
        ) is not None:
            raise ManualPerpStateError("Unresolved manual state publication evidence")
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
        if self.persistence_error is not None:
            raise self.persistence_error
        # A failed/interrupted publication is evidence, never an implicit retry grant.
        if self.pending_path.exists() or self.path.with_name(self.path.name + ".tmp").exists() or next(
            self.path.parent.glob(self.path.name + ".*.tmp"), None
        ) is not None:
            raise ManualPerpStateError("Unresolved manual state publication evidence")
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
        tmp = self.path.with_name(self.path.name + f".{uuid.uuid4().hex}.tmp")
        try:
            # Exclusive intent serializes publication and survives an interrupted replace.
            # It is a refusal marker, never a recovery grant or an auto-replay request.
            with self.pending_path.open("x", encoding="utf-8") as intent:
                write_flushed(intent, json.dumps({"version": STATE_VERSION, "temporary": tmp.name}) + "\n")
            sync_parent(self.pending_path)
            with tmp.open("x", encoding="utf-8") as handle:
                write_flushed(handle, encoded)
            os.replace(tmp, self.path)
            sync_parent(self.path)
            self.pending_path.unlink()
            sync_parent(self.pending_path)
        except BaseException as error:
            # Retain temporary evidence and refuse blind retries after unknown commit.
            self.persistence_error = error
            raise
