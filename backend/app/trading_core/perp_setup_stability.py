from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Iterable, Mapping

from app.trading_core.models import Side
from app.trading_core.perp_setup_state import classify_setup_state


def _parse_time(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def _key(row: Mapping[str, Any]) -> str:
    return f"{str(row.get('symbol') or '').upper()}:{str(row.get('side') or '').upper()}"


def _reclassify(row: dict[str, Any], mark: float) -> dict[str, Any]:
    levels = dict(row.get("levels") or {})
    side = Side[str(row.get("side") or "").upper()]
    state = classify_setup_state(
        side=side,
        mark=float(mark),
        l1=float(levels["l1"]),
        l2=float(levels["l2"]),
        l3=float(levels["l3"]),
        stop=float(levels["stop"]),
        tp1=float(levels["tp1"]),
        tp2=float(levels["tp2"]),
        entered=str(row.get("trade_status") or "").upper() == "ENTERED",
    )
    row["price"] = float(mark)
    row["mark"] = float(mark)
    row["state"] = state.state.value
    row["next_action"] = state.next_action
    row["distance_to_l1_pct"] = round(float(state.distance_to_l1_pct), 4)
    return row


def stabilize_setups(
    current: Iterable[dict[str, Any]],
    *,
    previous: Iterable[dict[str, Any]],
    price_map: Mapping[str, float],
    now: datetime | None = None,
    retention_minutes: int = 10,
) -> list[dict[str, Any]]:
    """Keep issued manual-perp setups stable across scanner refreshes.

    Once a setup has been published, its L1/L2/L3/stop/targets remain frozen for
    that setup key. A previously issued setup that temporarily falls out of the
    discovery shortlist is retained for a short grace window with alerts disabled.
    This prevents moving limit orders and dashboard flicker without creating orders.
    """
    now = now or datetime.now(timezone.utc)
    prior_by_key = {_key(row): dict(row) for row in previous if _key(row) != ":"}
    output: list[dict[str, Any]] = []
    seen: set[str] = set()

    for raw in current:
        row = dict(raw)
        key = _key(row)
        prior = prior_by_key.get(key)
        if prior and prior.get("levels"):
            # Published execution levels are a contract for this setup instance.
            row["levels"] = dict(prior["levels"])
            row["first_seen_at"] = prior.get("first_seen_at") or row.get("first_seen_at")
            row["last_alert_at"] = prior.get("last_alert_at")
            row["trade_status"] = prior.get("trade_status") or row.get("trade_status")
            row["entry_price"] = prior.get("entry_price")
            row["entered_at"] = prior.get("entered_at")
            mark = price_map.get(str(row.get("symbol") or "").upper())
            if mark is not None and float(mark) > 0:
                row = _reclassify(row, float(mark))
        row["levels_frozen"] = True
        row["discovery_stale"] = False
        output.append(row)
        seen.add(key)

    retain_for = timedelta(minutes=max(1, int(retention_minutes)))
    terminal = {"INVALIDATED", "TP2_HIT"}
    for key, prior in prior_by_key.items():
        if key in seen or not prior.get("levels"):
            continue
        first_seen = _parse_time(prior.get("first_seen_at") or prior.get("last_seen_at"))
        if first_seen is None or now - first_seen > retain_for:
            continue
        if str(prior.get("state") or "").upper() in terminal:
            continue
        symbol = str(prior.get("symbol") or "").upper()
        mark = price_map.get(symbol)
        if mark is None or float(mark) <= 0:
            continue
        row = dict(prior)
        try:
            row = _reclassify(row, float(mark))
        except Exception:
            continue
        row["levels_frozen"] = True
        row["discovery_stale"] = True
        row["alert_eligible"] = False
        row["alert_reason"] = "temporarily outside discovery shortlist; retained with frozen levels"
        row["next_action"] = (
            "Setup retained with frozen levels while scanner confirmation is temporarily absent. "
            + str(row.get("next_action") or "")
        ).strip()
        output.append(row)

    return output
