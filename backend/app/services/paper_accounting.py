"""Pure accounting readers. Never infer a fill or rewrite historical evidence."""
from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any


def recorded_net_r(row: Mapping[str, Any]) -> float | None:
    """Zero net R is authoritative; only missing/null net may use legacy gross R.

    Missing both fields, invalid strings, booleans and nonfinite values are
    unknown, not flat trades. An invalid net never falls through to gross.
    """
    raw = row.get("net_pnl_r")
    if raw is None:
        raw = row.get("R_multiple")
    if raw is None or isinstance(raw, bool):
        return None
    try:
        value = float(raw)
    except (TypeError, ValueError, OverflowError):
        return None
    return value if math.isfinite(value) else None


def is_administrative(row: Mapping[str, Any]) -> bool:
    return (
        bool(row.get("session_roll"))
        or bool(row.get("interrupted"))
        or str(row.get("result") or "").upper() in {"SESSION_ROLL", "INTERRUPTED"}
        or str(row.get("exit_reason") or "").lower() in {"atlas_shutdown", "session_reset"}
        or str(row.get("status") or "").lower() == "interrupted"
    )


def is_performance_row(row: Mapping[str, Any]) -> bool:
    """For closed-row consumers; event selection remains their responsibility."""
    return (
        str(row.get("trade_type") or "PAPER").upper() == "PAPER"
        and not is_administrative(row)
        and recorded_net_r(row) is not None
    )
