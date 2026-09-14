"""Durable research-only accumulation ladder for Quality Dips.

The ladder is frozen when an ACCUMULATE cycle arms so levels never chase a rising
market. Crossing a level records the hit and queues a manual-buy research DM until
Discord confirms delivery. Atlas never places a brokerage order.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from app.investment.storage import DATA_DIR, ensure_dirs

STATE_PATH = DATA_DIR / "accumulation_ladder_state.json"
SCHEMA_VERSION = 2
# Tighter accumulation ladder: L1 is a modest real dip rather than waiting 3%.
# At a $252.20 anchor this places L1 at about $248.42.
LADDER_PCTS = (0.015, 0.03, 0.05, 0.08)
LEVEL_NAMES = ("L1", "L2", "L3", "L4")
ACTIONABLE_QUOTE_QUALITY = {"LIVE", "FRESH"}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _float(v: Any) -> float | None:
    try:
        x = float(v)
        return x if x == x and x > 0 else None
    except (TypeError, ValueError):
        return None


@dataclass
class LadderHit:
    symbol: str
    level: str
    level_price: float
    market_price: float
    anchor_price: float
    pct_below_anchor: float
    cycle_id: str
    quote_session: str
    quote_timestamp: str | None


class AccumulationLadderStore:
    def __init__(self, path: Path = STATE_PATH) -> None:
        self.path = path
        self.state: dict[str, Any] = {"schema_version": SCHEMA_VERSION, "symbols": {}}
        self.load()

    def load(self) -> None:
        if not self.path.exists():
            self.state = {"schema_version": SCHEMA_VERSION, "symbols": {}}
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            self.state = raw if isinstance(raw, dict) else {"schema_version": SCHEMA_VERSION, "symbols": {}}
        except Exception:
            self.state = {"schema_version": SCHEMA_VERSION, "symbols": {}}
        if not isinstance(self.state.get("symbols"), dict):
            self.state["symbols"] = {}
        self.state["schema_version"] = SCHEMA_VERSION

    def save(self) -> None:
        ensure_dirs()
        self.state["schema_version"] = SCHEMA_VERSION
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.state, indent=2), encoding="utf-8")

    def get(self, symbol: str) -> dict[str, Any] | None:
        row = self.state["symbols"].get(symbol.upper())
        return dict(row) if isinstance(row, dict) else None

    def put(self, symbol: str, row: dict[str, Any]) -> None:
        self.state["symbols"][symbol.upper()] = row

    @staticmethod
    def _valid_schema(state: dict[str, Any] | None) -> bool:
        return bool(state) and int(state.get("schema_version") or 0) == SCHEMA_VERSION

    def mark_delivered(self, symbol: str, cycle_id: str, level_name: str, *, now: datetime | None = None) -> bool:
        state = self.get(symbol)
        if not self._valid_schema(state) or str(state.get("cycle_id") or "") != str(cycle_id):
            return False
        changed = False
        for level in list(state.get("levels") or []):
            if str(level.get("level") or "") != str(level_name):
                continue
            level["dm_delivered"] = True
            level["dm_delivered_at"] = (now or _now()).isoformat()
            changed = True
            break
        if changed:
            self.put(symbol, state)
            self.save()
        return changed

    @staticmethod
    def _event_from_level(symbol: str, state: dict[str, Any], level: dict[str, Any], *, fallback_price: float, quote_session: str, quote_ts: Any) -> LadderHit | None:
        level_price = _float(level.get("price"))
        market_price = _float(level.get("hit_market_price")) or fallback_price
        if level_price is None:
            return None
        return LadderHit(
            symbol=symbol,
            level=str(level.get("level") or "L?"),
            level_price=level_price,
            market_price=market_price,
            anchor_price=float(state.get("anchor_price") or fallback_price),
            pct_below_anchor=float(level.get("pct_below_anchor") or 0.0),
            cycle_id=str(state.get("cycle_id") or ""),
            quote_session=quote_session,
            quote_timestamp=str(level.get("hit_quote_timestamp") or quote_ts) if (level.get("hit_quote_timestamp") or quote_ts) else None,
        )

    def sync(self, rows: Iterable[dict[str, Any]], *, now: datetime | None = None) -> list[LadderHit]:
        now = now or _now()
        seen: set[str] = set()
        notifications: list[LadderHit] = []
        changed = False

        for board_row in rows:
            if not isinstance(board_row, dict):
                continue
            symbol = str(board_row.get("symbol") or "").upper().strip()
            if not symbol:
                continue
            seen.add(symbol)
            stance = str(board_row.get("stance") or "WATCH").upper()
            quote_quality = str(board_row.get("quote_quality") or "UNKNOWN").upper()
            display_price = _float(board_row.get("quote_display_price")) or _float(board_row.get("quote_price"))
            trigger_price = _float(board_row.get("quote_trigger_price")) or _float(board_row.get("quote_price"))
            quote_ts = board_row.get("quote_effective_timestamp")
            quote_session = str(board_row.get("quote_session") or "UNKNOWN")
            quote_source = str(board_row.get("quote_source") or "UNKNOWN")
            state = self.get(symbol)

            if stance != "ACCUMULATE":
                if state and state.get("active"):
                    state["active"] = False
                    state["ended_at"] = now.isoformat()
                    state["end_reason"] = f"stance_{stance}"
                    self.put(symbol, state)
                    changed = True
                continue

            if display_price is None or trigger_price is None or quote_quality not in ACTIONABLE_QUOTE_QUALITY:
                continue

            # Any pre-v2 ladder is invalid. Earlier tests could persist synthetic $300
            # anchors into the shared development data file; v2 deliberately re-arms
            # from the first real fresh quote and uses the new tighter percentages.
            if state and state.get("active") and not self._valid_schema(state):
                state["active"] = False
                state["ended_at"] = now.isoformat()
                state["end_reason"] = "ladder_schema_upgrade"
                self.put(symbol, state)
                state = None
                changed = True

            if not state or not state.get("active"):
                cycle_id = f"{symbol}:{now.isoformat()}"
                levels = []
                for name, pct in zip(LEVEL_NAMES, LADDER_PCTS):
                    levels.append({
                        "level": name,
                        "pct_below_anchor": round(pct * 100.0, 2),
                        "price": round(display_price * (1.0 - pct), 4),
                        "hit": False,
                        "hit_at": None,
                        "hit_market_price": None,
                        "hit_quote_timestamp": None,
                        "dm_delivered": False,
                        "dm_delivered_at": None,
                    })
                state = {
                    "schema_version": SCHEMA_VERSION,
                    "symbol": symbol,
                    "active": True,
                    "cycle_id": cycle_id,
                    "armed_at": now.isoformat(),
                    "anchor_price": display_price,
                    "anchor_quote_timestamp": quote_ts,
                    "anchor_quote_source": quote_source,
                    "last_price": display_price,
                    "last_trigger_price": trigger_price,
                    "last_quote_timestamp": quote_ts,
                    "levels": levels,
                    "note": "Frozen below the accumulation-cycle anchor; levels do not chase rising prices.",
                }
                self.put(symbol, state)
                changed = True
                continue

            previous_trigger = _float(state.get("last_trigger_price")) or _float(state.get("last_price"))
            state["last_price"] = display_price
            state["last_trigger_price"] = trigger_price
            state["last_quote_timestamp"] = quote_ts
            state["last_seen_at"] = now.isoformat()
            levels = list(state.get("levels") or [])
            for level in levels:
                level_price = _float(level.get("price"))
                if level_price is None:
                    continue
                if not bool(level.get("hit")):
                    # For Robinhood bid/ask quotes, trigger_price is the ask. A manual
                    # buy limit at Lx is marketable once the ask reaches that limit.
                    crossed = trigger_price <= level_price and (previous_trigger is None or previous_trigger > level_price)
                    if crossed:
                        level["hit"] = True
                        level["hit_at"] = now.isoformat()
                        level["hit_market_price"] = trigger_price
                        level["hit_quote_timestamp"] = quote_ts
                        level.setdefault("dm_delivered", False)
                        changed = True
                if bool(level.get("hit")) and not bool(level.get("dm_delivered")):
                    event = self._event_from_level(
                        symbol,
                        state,
                        level,
                        fallback_price=trigger_price,
                        quote_session=quote_session,
                        quote_ts=quote_ts,
                    )
                    if event is not None:
                        notifications.append(event)
            state["levels"] = levels
            self.put(symbol, state)
            changed = True

        for symbol, state in list(self.state["symbols"].items()):
            if symbol in seen or not isinstance(state, dict) or not state.get("active"):
                continue
            state["active"] = False
            state["ended_at"] = now.isoformat()
            state["end_reason"] = "not_in_current_board"
            self.put(symbol, state)
            changed = True

        if changed:
            self.save()
        return notifications

    def overlay(self, rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for original in rows:
            row = dict(original)
            symbol = str(row.get("symbol") or "").upper()
            state = self.get(symbol)
            active = state if state and state.get("active") and self._valid_schema(state) else None
            row["accumulation_ladder"] = active
            row["accumulation_status"] = self._status(row, active)
            out.append(row)
        return out

    @staticmethod
    def _status(row: dict[str, Any], state: dict[str, Any] | None) -> dict[str, Any]:
        quote = _float(row.get("quote_display_price")) or _float(row.get("quote_price"))
        quality = str(row.get("quote_quality") or "UNKNOWN").upper()
        if str(row.get("stance") or "").upper() != "ACCUMULATE":
            return {"state": "NOT_ACCUMULATING", "next_level": None, "pending_dm": 0}
        if not state:
            return {
                "state": "WAITING_FOR_FRESH_QUOTE",
                "next_level": None,
                "pending_dm": 0,
                "quote_quality": quality,
            }
        levels = list(state.get("levels") or [])
        pending_dm = sum(1 for x in levels if x.get("hit") and not x.get("dm_delivered"))
        latest_hit = next((x for x in reversed(levels) if x.get("hit")), None)
        next_level = next((x for x in levels if not x.get("hit")), None)
        if pending_dm:
            status_state = "LEVEL_HIT_DM_PENDING"
        elif latest_hit is not None:
            status_state = "LEVEL_HIT"
        else:
            status_state = "ARMED"
        payload: dict[str, Any] = {
            "state": status_state,
            "pending_dm": pending_dm,
            "quote_quality": quality,
            "latest_hit": latest_hit,
            "next_level": next_level,
        }
        if quote is not None and next_level is not None:
            level_price = _float(next_level.get("price"))
            if level_price is not None:
                payload["distance_to_next_level_usd"] = round(max(0.0, quote - level_price), 4)
                payload["distance_to_next_level_pct"] = round(max(0.0, (quote - level_price) / quote * 100.0), 2)
        return payload


accumulation_ladder_store = AccumulationLadderStore()
