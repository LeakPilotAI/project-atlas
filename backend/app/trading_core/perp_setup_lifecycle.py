from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Iterable

from app.trading_core.models import Side
from app.trading_core.perp_setup_state import classify_setup_state


class SetupTier(str, Enum):
    WATCH = "WATCH"
    QUALIFIED = "QUALIFIED"
    PRIME = "PRIME"


@dataclass(frozen=True)
class LifecycleDecision:
    tier: SetupTier
    alert_eligible: bool
    alert_reason: str
    setup_key: str


def setup_key(symbol: str, side: str) -> str:
    return f"{str(symbol).upper()}:{str(side).upper()}"


def classify_tier(score: float) -> SetupTier:
    score = float(score)
    if score >= 82.0:
        return SetupTier.PRIME
    if score >= 70.0:
        return SetupTier.QUALIFIED
    return SetupTier.WATCH


def _parse_time(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None


def _freeze_prior_levels(row: dict[str, Any], prior: dict[str, Any] | None) -> dict[str, Any]:
    """Keep published execution levels fixed for the life of a setup key."""
    if not prior or not isinstance(prior.get("levels"), dict):
        row["levels_frozen"] = True
        return row
    levels = dict(prior["levels"])
    required = {"l1", "l2", "l3", "stop", "tp1", "tp2"}
    if not required.issubset(levels):
        row["levels_frozen"] = True
        return row
    row["levels"] = levels
    try:
        side = Side[str(row.get("side") or "").upper()]
        mark = float(row.get("price") or row.get("mark") or 0.0)
        state = classify_setup_state(
            side=side,
            mark=mark,
            l1=float(levels["l1"]),
            l2=float(levels["l2"]),
            l3=float(levels["l3"]),
            stop=float(levels["stop"]),
            tp1=float(levels["tp1"]),
            tp2=float(levels["tp2"]),
            entered=str(prior.get("trade_status") or "").upper() == "ENTERED",
        )
        row["state"] = state.state.value
        row["next_action"] = state.next_action
        row["distance_to_l1_pct"] = round(float(state.distance_to_l1_pct), 4)
    except Exception:
        pass
    row["levels_frozen"] = True
    return row


def decide_lifecycle(
    setup: dict[str, Any],
    *,
    prior: dict[str, Any] | None = None,
    now: datetime | None = None,
    cooldown_minutes: int = 30,
) -> LifecycleDecision:
    now = now or datetime.now(timezone.utc)
    key = setup_key(str(setup.get("symbol") or ""), str(setup.get("side") or ""))
    tier = classify_tier(float(setup.get("score") or 0.0))
    state = str(setup.get("state") or "WAIT").upper()

    # Alerts are deliberately narrower than ranking. A setup must be at least
    # QUALIFIED and close enough to execution to be actionable.
    actionable_state = state in {"PREPARE", "L1_ACTIVE", "L2_ACTIVE", "L3_ACTIVE"}
    if tier is SetupTier.WATCH or not actionable_state:
        return LifecycleDecision(tier, False, "ranked for observation; not actionable yet", key)

    prior = prior or {}
    previous_tier = str(prior.get("tier") or "")
    previous_state = str(prior.get("state") or "")
    last_alert = _parse_time(prior.get("last_alert_at"))
    changed = previous_tier != tier.value or previous_state != state

    if changed:
        return LifecycleDecision(tier, True, "setup promoted or execution state changed", key)

    if last_alert is None:
        return LifecycleDecision(tier, True, "qualified actionable setup has not been alerted", key)

    if now - last_alert >= timedelta(minutes=max(1, int(cooldown_minutes))):
        return LifecycleDecision(tier, True, "alert cooldown elapsed while setup remains actionable", key)

    return LifecycleDecision(tier, False, "cooldown suppresses duplicate alert", key)


def reconcile_setups(
    setups: Iterable[dict[str, Any]],
    *,
    previous: Iterable[dict[str, Any]] = (),
    now: datetime | None = None,
    cooldown_minutes: int = 30,
    retention_minutes: int = 10,
) -> list[dict[str, Any]]:
    """Reconcile discovery rows into stable, executable setup instances.

    Published L1/L2/L3/stop/target levels do not drift on later refreshes. If a
    setup temporarily falls out of the small discovery shortlist, retain it for
    a short grace window as non-actionable/stale instead of making the card
    disappear and then reappear.

    ``paper_mirror_epoch_at`` versions a continuous manual-opportunity cycle. A
    setup that leaves the actionable states and later becomes actionable again
    receives a new epoch so the automatic paper mirror may arm the new manual
    instruction exactly once without replaying the prior fill forever.

    Prior mark/state metadata is carried forward for one refresh so the paper
    mirror can prove that a previously-resting L1 was crossed between polls.
    """
    now = now or datetime.now(timezone.utc)
    prior_by_key = {
        setup_key(str(row.get("symbol") or ""), str(row.get("side") or "")): dict(row)
        for row in previous
    }
    output: list[dict[str, Any]] = []
    seen: set[str] = set()
    actionable_states = {"PREPARE", "L1_ACTIVE", "L2_ACTIVE", "L3_ACTIVE"}

    for raw in setups:
        row = dict(raw)
        key = setup_key(str(row.get("symbol") or ""), str(row.get("side") or ""))
        prior = prior_by_key.get(key)
        row = _freeze_prior_levels(row, prior)
        decision = decide_lifecycle(
            row,
            prior=prior,
            now=now,
            cooldown_minutes=cooldown_minutes,
        )
        row["setup_key"] = key
        row["tier"] = decision.tier.value
        row["alert_eligible"] = decision.alert_eligible
        row["alert_reason"] = decision.alert_reason
        row["first_seen_at"] = (prior or {}).get("first_seen_at") or now.isoformat()
        row["last_seen_at"] = now.isoformat()
        row["last_alert_at"] = (prior or {}).get("last_alert_at")
        row["previous_tier"] = (prior or {}).get("tier")
        row["previous_state"] = (prior or {}).get("state")
        row["previous_price"] = (prior or {}).get("price") or (prior or {}).get("mark")
        row["previous_discovery_stale"] = bool((prior or {}).get("discovery_stale", False))
        row["discovery_stale"] = False

        current_state = str(row.get("state") or "WAIT").upper()
        prior_state = str((prior or {}).get("state") or "WAIT").upper()
        prior_epoch = str((prior or {}).get("paper_mirror_epoch_at") or "")
        if current_state in actionable_states:
            if not prior_epoch or prior_state not in actionable_states:
                row["paper_mirror_epoch_at"] = now.isoformat()
            else:
                row["paper_mirror_epoch_at"] = prior_epoch
        else:
            row["paper_mirror_epoch_at"] = prior_epoch or None

        output.append(row)
        seen.add(key)

    keep_for = timedelta(minutes=max(1, int(retention_minutes)))
    terminal = {"INVALIDATED", "TP2_HIT"}
    for key, prior in prior_by_key.items():
        if key in seen:
            continue
        if str(prior.get("state") or "").upper() in terminal:
            continue
        first_seen = _parse_time(prior.get("first_seen_at") or prior.get("last_seen_at"))
        if first_seen is None or now - first_seen > keep_for:
            continue
        retained = dict(prior)
        retained["setup_key"] = key
        retained["levels_frozen"] = True
        retained["discovery_stale"] = True
        retained["state"] = "WAIT"
        retained["alert_eligible"] = False
        retained["alert_reason"] = "temporarily outside discovery shortlist; retained with frozen levels"
        retained["previous_tier"] = prior.get("tier")
        retained["previous_state"] = prior.get("state")
        retained["previous_price"] = prior.get("price") or prior.get("mark")
        retained["previous_discovery_stale"] = bool(prior.get("discovery_stale", False))
        retained["next_action"] = "Scanner confirmation temporarily absent; keep existing limits frozen and do not add/chase until rediscovered."
        output.append(retained)

    return output
