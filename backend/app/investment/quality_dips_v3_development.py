"""Development evaluation/freeze report for Quality Dips V3.

Consumes already-recorded PIT rows only. Produces a DEVELOPMENT summary and a
parameter-freeze artifact suitable for later untouched HOLDOUT evaluation.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
from typing import Any, Iterable

from app.investment.quality_dips_v3 import LEVEL_MARGINS
from app.investment.quality_dips_v3_validation import DEVELOPMENT_END, DEVELOPMENT_START, validate_v3_pit_rows


def build_development_report(rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    rows = [r for r in rows if isinstance(r, dict)]
    validation = validate_v3_pit_rows(rows)
    dev = [r for r in rows if DEVELOPMENT_START <= str(r.get("timestamp") or "") <= DEVELOPMENT_END]
    states = Counter(str(r.get("patient_state") or "WATCH").upper() for r in dev)
    symbols = sorted({str(r.get("symbol") or "").upper() for r in dev if str(r.get("symbol") or "")})
    return {
        "cycle": "QUALITY_DIPS_V3_MARGIN_OF_SAFETY",
        "window": {"name": "DEVELOPMENT", "start": DEVELOPMENT_START, "end": DEVELOPMENT_END},
        "validation": validation,
        "observations": len(dev),
        "symbols": symbols,
        "state_counts": dict(states),
        "parameter_freeze": {
            "level_margins": deepcopy(LEVEL_MARGINS),
            "frozen_after_development": True,
            "holdout_retuning_allowed": False,
        },
        "decision": "DEVELOPMENT_VALIDATION_READY" if validation["valid"] and len(dev) > 0 else "BLOCKED",
        "execution": "MANUAL_ONLY",
        "live_capital_allowed": False,
        "automatic_real_money_execution": False,
    }
