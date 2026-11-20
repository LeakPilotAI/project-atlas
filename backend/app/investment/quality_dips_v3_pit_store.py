"""Build V3 PIT rows from existing investment observation storage.

This adapter is deliberately fail-closed: it only emits rows that already contain
timestamped symbol + V3-compatible patient state fields. It does not synthesize
historical V3 states from current data or future information.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.investment.storage import OBSERVATIONS_PATH


def load_v3_pit_rows(path: Path = OBSERVATIONS_PATH) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    out: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            raw = line.strip()
            if not raw:
                continue
            try:
                row = json.loads(raw)
            except Exception:
                continue
            if not isinstance(row, dict):
                continue
            symbol = str(row.get("symbol") or "").upper().strip()
            timestamp = str(row.get("timestamp") or row.get("as_of") or "")
            state = str(
                row.get("quality_dips_v3_state")
                or row.get("v3_patient_state")
                or row.get("patient_state")
                or ""
            ).upper()
            if not symbol or not timestamp or state not in {"WATCH","ACCUMULATION","DEEP_VALUE","GENERATIONAL"}:
                continue
            out.append({"symbol": symbol, "timestamp": timestamp, "patient_state": state})
    return out
