"""Quality Dips V2 durable alert policy.

Pure/read-only policy for deciding when a V2 state transition, exceptional entry-zone
hit, or thesis change deserves a user notification. The caller owns persistence and
actual delivery. This module never places brokerage orders.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional


STATE_RANK = {
    "WATCH": 0,
    "ACCUMULATION": 1,
    "DEEP_VALUE": 2,
    "GENERATIONAL": 3,
    "THESIS_BROKEN": -1,
}
EXCEPTIONAL_LEVELS = {"L3", "L4"}
DEFAULT_COOLDOWN_HOURS = 12.0


@dataclass(frozen=True)
class AlertDecision:
    notify: bool
    event_type: Optional[str]
    dedupe_key: Optional[str]
    priority: str
    reasons: tuple[str, ...]

    def as_dict(self) -> Dict[str, Any]:
        return {
            "notify": self.notify,
            "event_type": self.event_type,
            "dedupe_key": self.dedupe_key,
            "priority": self.priority,
            "reasons": list(self.reasons),
            "execution": "MANUAL_ONLY",
            "read_only": True,
            "live_capital_allowed": False,
            "automatic_real_money_execution": False,
        }


def _upper(value: Any) -> str:
    return str(value or "UNKNOWN").upper()


def _parse_dt(value: Any) -> Optional[datetime]:
    if value in {None, ""}:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _cooldown_active(prior: Optional[Dict[str, Any]], *, now: datetime, hours: float) -> bool:
    if not prior:
        return False
    last = _parse_dt(prior.get("last_at"))
    if last is None:
        return False
    return now - last < timedelta(hours=max(1.0, float(hours)))


def decide_v2_alert(
    *,
    symbol: str,
    previous: Optional[Dict[str, Any]],
    current: Dict[str, Any],
    prior_event: Optional[Dict[str, Any]] = None,
    now: Optional[datetime] = None,
    cooldown_hours: float = DEFAULT_COOLDOWN_HOURS,
) -> Dict[str, Any]:
    """Return a fail-safe notification decision for one V2 board observation."""
    ref = now or datetime.now(timezone.utc)
    sym = str(symbol or current.get("symbol") or "").upper().strip()
    if not sym:
        return AlertDecision(False, None, None, "NORMAL", ("missing symbol",)).as_dict()

    cur_state = _upper(current.get("patient_state"))
    prev_state = _upper((previous or {}).get("patient_state")) if previous else "UNKNOWN"
    thesis = _upper(current.get("thesis"))
    prior_thesis = _upper((previous or {}).get("thesis")) if previous else "UNKNOWN"
    ladder = dict(current.get("entry_ladder") or {})
    levels = list(ladder.get("levels") or [])
    reached = [str(x.get("level") or "").upper() for x in levels if bool(x.get("reached"))]
    deepest = next((lvl for lvl in ("L4", "L3", "L2", "L1") if lvl in reached), None)

    event_type: Optional[str] = None
    priority = "NORMAL"
    reasons: list[str] = []

    if cur_state == "THESIS_BROKEN" or thesis in {"BROKEN", "FAILED"}:
        if prev_state != "THESIS_BROKEN" and prior_thesis not in {"BROKEN", "FAILED"}:
            event_type = "THESIS_CHANGE"
            priority = "HIGH"
            reasons.append("thesis changed to broken/failed")
    elif deepest in EXCEPTIONAL_LEVELS:
        event_type = "EXCEPTIONAL_ZONE"
        priority = "HIGH" if deepest == "L4" else "NORMAL"
        reasons.append(f"patient-capital {deepest} zone reached")
    elif prev_state != "UNKNOWN" and cur_state != prev_state:
        prev_rank = STATE_RANK.get(prev_state, 0)
        cur_rank = STATE_RANK.get(cur_state, 0)
        if cur_rank > prev_rank:
            event_type = "STATE_TRANSITION"
            priority = "HIGH" if cur_state == "GENERATIONAL" else "NORMAL"
            reasons.append(f"patient state improved {prev_state} -> {cur_state}")
        elif cur_state == "WATCH" and prev_state in {"ACCUMULATION", "DEEP_VALUE", "GENERATIONAL"}:
            event_type = "STATE_TRANSITION"
            reasons.append(f"patient state cooled {prev_state} -> WATCH")

    if not event_type:
        return AlertDecision(False, None, None, priority, tuple(reasons or ["no alert-worthy V2 change"])).as_dict()

    detail = deepest or cur_state or thesis
    dedupe_key = f"V2:{sym}:{event_type}:{detail}"
    if prior_event and str(prior_event.get("dedupe_key") or "") == dedupe_key:
        if _cooldown_active(prior_event, now=ref, hours=cooldown_hours):
            reasons.append("matching event suppressed by cooldown/dedupe")
            return AlertDecision(False, event_type, dedupe_key, priority, tuple(reasons)).as_dict()

    reasons.append("research notification only; no brokerage action")
    return AlertDecision(True, event_type, dedupe_key, priority, tuple(reasons)).as_dict()


def format_v2_alert(symbol: str, decision: Dict[str, Any], current: Dict[str, Any]) -> str:
    state = _upper(current.get("patient_state"))
    nv = dict(current.get("normalization_value") or {})
    gate = dict(current.get("evidence_gate") or {})
    ladder = dict(current.get("entry_ladder") or {})
    reached = [str(x.get("level")) for x in list(ladder.get("levels") or []) if x.get("reached")]
    return "\n".join([
        f"QUALITY DIPS V2 · {decision.get('event_type')}",
        str(symbol).upper(),
        "",
        f"Patient state: {state}",
        f"Conservative value: {nv.get('conservative', 'UNKNOWN')}",
        f"Conservative upside: {current.get('conservative_upside_pct', 'UNKNOWN')}",
        f"Reached patient zones: {', '.join(reached) if reached else 'none'}",
        f"Evidence gate: {gate.get('status', 'UNKNOWN')}",
        "",
        "MANUAL RESEARCH ONLY:",
        "Atlas detected a research-state change. Review the evidence before any decision.",
        "No brokerage order was placed. Screening hurdles are not promised returns.",
    ])
