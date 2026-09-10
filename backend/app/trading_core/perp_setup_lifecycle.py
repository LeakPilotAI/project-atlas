from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Iterable


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
) -> list[dict[str, Any]]:
    now = now or datetime.now(timezone.utc)
    prior_by_key = {
        setup_key(str(row.get("symbol") or ""), str(row.get("side") or "")): dict(row)
        for row in previous
    }
    output: list[dict[str, Any]] = []
    for raw in setups:
        row = dict(raw)
        key = setup_key(str(row.get("symbol") or ""), str(row.get("side") or ""))
        prior = prior_by_key.get(key)
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
        output.append(row)
    return output
