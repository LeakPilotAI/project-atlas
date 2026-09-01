"""Point-in-time major-move events. Outcomes live in a separate jsonl."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional
from uuid import uuid4

from app.investment.storage import DATA_DIR, OUTCOMES_PATH, ensure_dirs

MOVE_EVENTS_PATH = DATA_DIR / "move_events.jsonl"
MOVE_OUTCOMES_PATH = DATA_DIR / "move_outcomes.jsonl"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def append_move_event(event: Dict[str, Any], *, path: Optional[Path] = None) -> Dict[str, Any]:
    ensure_dirs()
    row = dict(event)
    row.setdefault("event_id", uuid4().hex[:16])
    row.setdefault("recorded_at", _now().isoformat())
    # Outcomes stay NULL on the original event.
    row.setdefault("outcomes", None)
    p = path or MOVE_EVENTS_PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, default=str) + "\n")
    return row


def append_move_outcome(event_id: str, outcomes: Dict[str, Any], *, path: Optional[Path] = None) -> None:
    """Write outcomes beside the event. Never rewrite the original event file."""
    ensure_dirs()
    p = path or MOVE_OUTCOMES_PATH
    if p.resolve() == MOVE_EVENTS_PATH.resolve():
        raise RuntimeError("move outcomes must not overwrite move events")
    row = {
        "event_id": event_id,
        "recorded_at": _now().isoformat(),
        "outcomes": outcomes,
    }
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, default=str) + "\n")
