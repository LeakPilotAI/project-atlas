"""Durable read-only registry for Robinhood equity discovery.

This module deliberately separates *coverage* from *selection*.  A symbol can be
known to Atlas without being a Quality Dip, actionable, or even currently
tradable.  Discovery/sync code can upsert evidence here incrementally without
causing dashboard requests to rescan the full universe or call external
providers.

No brokerage authentication or order execution is permitted here.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from app.investment.storage import (
    ROBINHOOD_UNIVERSE_EVENTS_PATH,
    ROBINHOOD_UNIVERSE_PATH,
    ensure_dirs,
)

SCHEMA_VERSION = "robinhood-universe-v1"
VALID_STATES = {"TRADABLE", "PRE_LISTING", "ANNOUNCED", "DELISTED", "UNKNOWN"}
VALID_LANES = {
    "QUALITY_DIPS",
    "ESTABLISHED_COMPOUNDER",
    "EMERGING_COMPOUNDER",
    "FRONTIER_RESEARCH",
    "EXCLUDED",
    "UNCLASSIFIED",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load(path: Path = ROBINHOOD_UNIVERSE_PATH) -> dict[str, Any]:
    if not path.exists():
        return {
            "schema_version": SCHEMA_VERSION,
            "updated_at": None,
            "symbols": {},
            "execution": "RESEARCH_ONLY_MANUAL",
            "live_capital_allowed": False,
            "automatic_real_money_execution": False,
        }
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        raw = {}
    symbols = raw.get("symbols") if isinstance(raw, dict) else {}
    return {
        "schema_version": SCHEMA_VERSION,
        "updated_at": raw.get("updated_at") if isinstance(raw, dict) else None,
        "symbols": symbols if isinstance(symbols, dict) else {},
        "execution": "RESEARCH_ONLY_MANUAL",
        "live_capital_allowed": False,
        "automatic_real_money_execution": False,
    }


def snapshot(path: Path = ROBINHOOD_UNIVERSE_PATH) -> dict[str, Any]:
    return _load(path)


def upsert_discovery(
    rows: Iterable[dict[str, Any]],
    *,
    source: str,
    observed_at: str | None = None,
    path: Path = ROBINHOOD_UNIVERSE_PATH,
    events_path: Path = ROBINHOOD_UNIVERSE_EVENTS_PATH,
) -> dict[str, Any]:
    """Merge a discovery batch and append only material state changes.

    Caller-supplied rows must be evidence from a read-only discovery source.
    Absence from a batch never implies delisting; explicit evidence is required.
    """
    ensure_dirs()
    state = _load(path)
    symbols = dict(state["symbols"])
    ts = observed_at or _now()
    added = changed = 0
    events: list[dict[str, Any]] = []

    for raw in rows:
        symbol = str(raw.get("symbol") or "").upper().strip()
        if not symbol:
            continue
        listing_state = str(raw.get("listing_state") or "UNKNOWN").upper()
        if listing_state not in VALID_STATES:
            listing_state = "UNKNOWN"
        lane = str(raw.get("research_lane") or "UNCLASSIFIED").upper()
        if lane not in VALID_LANES:
            lane = "UNCLASSIFIED"
        previous = dict(symbols.get(symbol) or {})
        current = {
            **previous,
            "symbol": symbol,
            "name": raw.get("name") or previous.get("name"),
            "listing_state": listing_state,
            "research_lane": lane,
            "instrument_type": raw.get("instrument_type") or previous.get("instrument_type"),
            "source": source,
            "source_reference": raw.get("source_reference"),
            "first_seen_at": previous.get("first_seen_at") or ts,
            "last_seen_at": ts,
            "tradable": bool(raw.get("tradable")) if raw.get("tradable") is not None else previous.get("tradable"),
        }
        material_before = {k: previous.get(k) for k in ("listing_state", "research_lane", "instrument_type", "tradable")}
        material_after = {k: current.get(k) for k in material_before}
        if not previous:
            added += 1
            event_type = "DISCOVERED"
        elif material_before != material_after:
            changed += 1
            event_type = "STATE_CHANGED"
        else:
            event_type = ""
        symbols[symbol] = current
        if event_type:
            events.append({
                "timestamp": ts,
                "event": event_type,
                "symbol": symbol,
                "before": material_before if previous else None,
                "after": material_after,
                "source": source,
                "execution": "RESEARCH_ONLY_MANUAL",
                "live_capital_allowed": False,
                "automatic_real_money_execution": False,
            })

    state.update({"updated_at": ts, "symbols": symbols})
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")
    if events:
        events_path.parent.mkdir(parents=True, exist_ok=True)
        with events_path.open("a", encoding="utf-8") as handle:
            for event in events:
                handle.write(json.dumps(event, sort_keys=True) + "\n")

    counts: dict[str, int] = {}
    lanes: dict[str, int] = {}
    for row in symbols.values():
        s = str(row.get("listing_state") or "UNKNOWN")
        l = str(row.get("research_lane") or "UNCLASSIFIED")
        counts[s] = counts.get(s, 0) + 1
        lanes[l] = lanes.get(l, 0) + 1
    return {
        "total_symbols": len(symbols),
        "added": added,
        "material_changes": changed,
        "listing_state_counts": counts,
        "research_lane_counts": lanes,
        "execution": "RESEARCH_ONLY_MANUAL",
        "live_capital_allowed": False,
        "automatic_real_money_execution": False,
    }


def research_candidates(
    *,
    limit: int = 40,
    path: Path = ROBINHOOD_UNIVERSE_PATH,
) -> list[dict[str, Any]]:
    """Return a bounded discovery queue; never the whole catalog at scan cadence.

    Priority is deterministic: explicitly classified research lanes first, then
    newly discovered tradable symbols. Existing Quality Dips remain in their
    normal investment scanner; this queue is for broad-universe discovery.
    """
    state = _load(path)
    symbols = state.get("symbols") or {}
    lane_rank = {
        "EMERGING_COMPOUNDER": 0,
        "ESTABLISHED_COMPOUNDER": 1,
        "QUALITY_DIPS": 2,
        "FRONTIER_RESEARCH": 3,
        "UNCLASSIFIED": 4,
        "EXCLUDED": 99,
    }
    eligible = [
        dict(row)
        for row in symbols.values()
        if isinstance(row, dict)
        and bool(row.get("tradable"))
        and str(row.get("listing_state") or "").upper() == "TRADABLE"
        and str(row.get("research_lane") or "UNCLASSIFIED").upper() != "EXCLUDED"
    ]
    eligible.sort(
        key=lambda row: (
            lane_rank.get(str(row.get("research_lane") or "UNCLASSIFIED").upper(), 50),
            str(row.get("last_researched_at") or ""),
            str(row.get("first_seen_at") or ""),
            str(row.get("symbol") or ""),
        )
    )
    return eligible[: max(1, min(int(limit), 200))]


def mark_researched(
    symbol: str,
    *,
    researched_at: str | None = None,
    path: Path = ROBINHOOD_UNIVERSE_PATH,
) -> None:
    """Record scheduling metadata only; this is not an investment conclusion."""
    state = _load(path)
    symbols = dict(state.get("symbols") or {})
    key = str(symbol or "").upper().strip()
    if not key or key not in symbols:
        return
    row = dict(symbols[key])
    row["last_researched_at"] = researched_at or _now()
    symbols[key] = row
    state["symbols"] = symbols
    state["updated_at"] = researched_at or _now()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")
