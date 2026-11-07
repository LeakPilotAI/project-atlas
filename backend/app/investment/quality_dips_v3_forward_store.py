"""Forward Quality Dips V3 point-in-time shadow evidence recorder."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.investment.storage import DATA_DIR, ensure_dirs

V3_FORWARD_PATH = DATA_DIR / "quality_dips_v3_forward_pit.jsonl"


def append_v3_forward_observation(
    *,
    symbol: str,
    price: Any,
    plan: dict[str, Any],
    source_timestamp: str | None = None,
    path: Path = V3_FORWARD_PATH,
) -> dict[str, Any]:
    ensure_dirs()
    row = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source_timestamp": source_timestamp,
        "symbol": str(symbol or "").upper().strip(),
        "price": price,
        "patient_state": plan.get("patient_state"),
        "fair_value_anchor": plan.get("fair_value_anchor"),
        "discount_to_fair_value_pct": plan.get("discount_to_fair_value_pct"),
        "blockers": list(plan.get("blockers") or []),
        "entry_ladder": dict(plan.get("entry_ladder") or {}),
        "policy": dict(plan.get("policy") or {}),
        "execution": "MANUAL_ONLY",
        "live_capital_allowed": False,
        "automatic_real_money_execution": False,
    }
    if not row["symbol"]:
        raise ValueError("symbol required")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, default=str) + "\n")
    return row
