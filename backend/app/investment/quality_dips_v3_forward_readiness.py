"""Forward V3 shadow-readiness report."""
from __future__ import annotations

import json
import threading
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from app.investment.quality_dips_v3_forward_store import V3_FORWARD_PATH

MIN_UNIQUE_DAYS = 20
MIN_SYMBOLS = 10
MIN_EVALUATIONS = 200
_cache_lock = threading.Lock()
_aggregate_cache: dict[str, Any] = {
    "path": None,
    "offset": 0,
    "evaluations": 0,
    "symbols": set(),
    "days": set(),
    "states": Counter(),
    "by_day": Counter(),
    "by_symbol": Counter(),
}


def _parse_day(ts: Any) -> str | None:
    try:
        return datetime.fromisoformat(str(ts).replace("Z", "+00:00")).date().isoformat()
    except Exception:
        return None


def load_forward_rows(path: Path = V3_FORWARD_PATH) -> list[dict[str, Any]]:
    """Compatibility loader for focused callers/tests.

    Production readiness/diagnostics deliberately do not use this function:
    the PIT journal is large and must never be materialized as a giant decoded
    list on the dashboard hot path.
    """
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8") as handle:
            for raw in handle:
                if not raw.strip():
                    continue
                try:
                    row = json.loads(raw)
                except Exception:
                    continue
                if isinstance(row, dict):
                    rows.append(row)
    except OSError:
        return []
    return rows


def _reset_aggregate(path_key: str) -> None:
    _aggregate_cache.update({
        "path": path_key,
        "offset": 0,
        "evaluations": 0,
        "symbols": set(),
        "days": set(),
        "states": Counter(),
        "by_day": Counter(),
        "by_symbol": Counter(),
    })


def _aggregate_forward(path: Path = V3_FORWARD_PATH) -> dict[str, Any]:
    """Return compact PIT aggregates, incrementally consuming only appended bytes.

    The journal is append-only evidence. After the initial scan, dashboard
    refreshes process only newly appended observations instead of repeatedly
    decoding the entire 100MB+ history or retaining decoded rows in memory.
    """
    if not path.exists():
        return {
            "evaluations": 0, "symbols": set(), "days": set(),
            "states": Counter(), "by_day": Counter(), "by_symbol": Counter(),
        }
    try:
        stat = path.stat()
        path_key = str(path.resolve())
        size = int(stat.st_size)
    except OSError:
        return {
            "evaluations": 0, "symbols": set(), "days": set(),
            "states": Counter(), "by_day": Counter(), "by_symbol": Counter(),
        }

    with _cache_lock:
        # Rebuild only on first use, path change, or evidence truncation/replacement.
        if _aggregate_cache["path"] != path_key or size < int(_aggregate_cache["offset"]):
            _reset_aggregate(path_key)

        offset = int(_aggregate_cache["offset"])
        if size > offset:
            try:
                with path.open("rb") as handle:
                    handle.seek(offset)
                    for raw in handle:
                        try:
                            row = json.loads(raw.decode("utf-8"))
                        except Exception:
                            continue
                        if not isinstance(row, dict):
                            continue
                        _aggregate_cache["evaluations"] += 1
                        symbol = str(row.get("symbol") or "").upper()
                        if symbol:
                            _aggregate_cache["symbols"].add(symbol)
                            _aggregate_cache["by_symbol"][symbol] += 1
                        day = _parse_day(row.get("timestamp"))
                        if day:
                            _aggregate_cache["days"].add(day)
                            _aggregate_cache["by_day"][day] += 1
                        state = str(row.get("patient_state") or "UNKNOWN").upper()
                        _aggregate_cache["states"][state] += 1
                    _aggregate_cache["offset"] = handle.tell()
            except OSError:
                pass

        return {
            "evaluations": int(_aggregate_cache["evaluations"]),
            "symbols": set(_aggregate_cache["symbols"]),
            "days": set(_aggregate_cache["days"]),
            "states": Counter(_aggregate_cache["states"]),
            "by_day": Counter(_aggregate_cache["by_day"]),
            "by_symbol": Counter(_aggregate_cache["by_symbol"]),
        }


def forward_readiness(path: Path = V3_FORWARD_PATH) -> dict[str, Any]:
    agg = _aggregate_forward(path)
    evaluations = int(agg["evaluations"])
    symbols = agg["symbols"]
    days = agg["days"]
    states = agg["states"]
    blockers = []
    if evaluations < MIN_EVALUATIONS:
        blockers.append("minimum evaluations not reached")
    if len(symbols) < MIN_SYMBOLS:
        blockers.append("minimum symbol coverage not reached")
    if len(days) < MIN_UNIQUE_DAYS:
        blockers.append("minimum calendar-day coverage not reached")
    return {
        "ready": not blockers,
        "blockers": blockers,
        "evaluations": evaluations,
        "symbols": len(symbols),
        "unique_days": len(days),
        "state_counts": dict(states),
        "thresholds": {
            "min_evaluations": MIN_EVALUATIONS,
            "min_symbols": MIN_SYMBOLS,
            "min_unique_days": MIN_UNIQUE_DAYS,
        },
        "execution": "MANUAL_ONLY",
        "live_capital_allowed": False,
        "automatic_real_money_execution": False,
    }


def forward_diagnostics(path: Path = V3_FORWARD_PATH) -> dict[str, Any]:
    agg = _aggregate_forward(path)
    evaluations = int(agg["evaluations"])
    states = agg["states"]
    non_watch = sum(v for k, v in states.items() if k not in {"WATCH", "UNKNOWN"})
    return {
        "evaluations_per_day": dict(sorted(agg["by_day"].items())),
        "top_symbols": dict(agg["by_symbol"].most_common(20)),
        "state_counts": dict(states),
        "non_watch_evaluations": non_watch,
        "non_watch_rate": round(non_watch / evaluations, 4) if evaluations else 0.0,
        "execution": "MANUAL_ONLY",
        "live_capital_allowed": False,
    }
