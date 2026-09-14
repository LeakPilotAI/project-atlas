"""Durable research-only accumulation ladder for Quality Dips.

The ladder is frozen when an ACCUMULATE cycle arms so levels never chase a rising
market. Crossing a level creates a one-shot manual-buy research alert. Atlas never
places a brokerage order.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from app.investment.storage import DATA_DIR, ensure_dirs

STATE_PATH = DATA_DIR / "accumulation_ladder_state.json"
LADDER_PCTS = (0.03, 0.07, 0.12, 0.18)
LEVEL_NAMES = ("L1", "L2", "L3", "L4")


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
        self.state: dict[str, Any] = {"symbols": {}}
        self.load()

    def load(self) -> None:
        if not self.path.exists():
            self.state = {"symbols": {}}
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            self.state = raw if isinstance(raw, dict) else {"symbols": {}}
        except Exception:
            self.state = {"symbols": {}}
        if not isinstance(self.state.get("symbols"), dict):
            self.state["symbols"] = {}

    def save(self) -> None:
        ensure_dirs()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.state, indent=2), encoding="utf-8")

    def get(self, symbol: str) -> dict[str, Any] | None:
        row = self.state["symbols"].get(symbol.upper())
        return dict(row) if isinstance(row, dict) else None

    def put(self, symbol: str, row: dict[str, Any]) -> None:
        self.state["symbols"][symbol.upper()] = row

    def sync(self, rows: Iterable[dict[str, Any]], *, now: datetime | None = None) -> list[LadderHit]:
        now = now or _now()
        seen: set[str] = set()
        hits: list[LadderHit] = []
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
            quote_price = _float(board_row.get("quote_price"))
            quote_ts = board_row.get("quote_effective_timestamp")
            quote_session = str(board_row.get("quote_session") or "UNKNOWN")
            state = self.get(symbol)

            if stance != "ACCUMULATE":
                if state and state.get("active"):
                    state["active"] = False
                    state["ended_at"] = now.isoformat()
                    state["end_reason"] = f"stance_{stance}"
                    self.put(symbol, state)
                    changed = True
                continue

            # Never arm or trigger from a stale/missing quote. REFERENCE is useful for
            # display but not good enough to claim a level was just hit.
            if quote_price is None or quote_quality != "FRESH":
                continue

            if not state or not state.get("active"):
                cycle_id = f"{symbol}:{now.isoformat()}"
                levels = []
                for name, pct in zip(LEVEL_NAMES, LADDER_PCTS):
                    levels.append({
                        "level": name,
                        "pct_below_anchor": round(pct * 100.0, 1),
                        "price": round(quote_price * (1.0 - pct), 4),
                        "hit": False,
                        "hit_at": None,
                        "hit_market_price": None,
                    })
                state = {
                    "symbol": symbol,
                    "active": True,
                    "cycle_id": cycle_id,
                    "armed_at": now.isoformat(),
                    "anchor_price": quote_price,
                    "anchor_quote_timestamp": quote_ts,
                    "last_price": quote_price,
                    "last_quote_timestamp": quote_ts,
                    "levels": levels,
                    "note": "Frozen below the accumulation-cycle anchor; levels do not chase rising prices.",
                }
                self.put(symbol, state)
                changed = True
                continue

            previous = _float(state.get("last_price"))
            state["last_price"] = quote_price
            state["last_quote_timestamp"] = quote_ts
            state["last_seen_at"] = now.isoformat()
            levels = list(state.get("levels") or [])
            for level in levels:
                if bool(level.get("hit")):
                    continue
                level_price = _float(level.get("price"))
                if level_price is None:
                    continue
                # First observed print at/below the frozen level counts as a hit.
                # previous > level is preferred, but restart gaps are intentionally
                # recovered so a real dip is not silently lost.
                crossed = quote_price <= level_price and (previous is None or previous > level_price)
                if not crossed:
                    continue
                level["hit"] = True
                level["hit_at"] = now.isoformat()
                level["hit_market_price"] = quote_price
                hits.append(LadderHit(
                    symbol=symbol,
                    level=str(level.get("level") or "L?"),
                    level_price=level_price,
                    market_price=quote_price,
                    anchor_price=float(state.get("anchor_price") or quote_price),
                    pct_below_anchor=float(level.get("pct_below_anchor") or 0.0),
                    cycle_id=str(state.get("cycle_id") or ""),
                    quote_session=quote_session,
                    quote_timestamp=str(quote_ts) if quote_ts else None,
                ))
                changed = True
            state["levels"] = levels
            self.put(symbol, state)
            changed = True

        # Symbols that disappeared from the board close their cycle. This prevents
        # an ancient ACCUMULATE state from remaining armed forever.
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
        return hits

    def overlay(self, rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for original in rows:
            row = dict(original)
            symbol = str(row.get("symbol") or "").upper()
            state = self.get(symbol)
            row["accumulation_ladder"] = state if state and state.get("active") else None
            out.append(row)
        return out


accumulation_ladder_store = AccumulationLadderStore()
