"""Prospective policy freezes. Classification never changes original observations."""

from datetime import datetime, timezone
import hashlib
import json

from app.investment.prospective_evidence import append_record, read_records, _lock
from app.investment.storage import DATA_DIR

FREEZES = DATA_DIR / "prospective_policy_freezes.jsonl"


def freeze_policy(
    *,
    version,
    policy,
    development_end,
    holdout_start,
    holdout_end,
    rationale,
    path=FREEZES
):
    now = datetime.now(timezone.utc)
    dates = [
        datetime.fromisoformat(value.replace("Z", "+00:00"))
        for value in (development_end, holdout_start, holdout_end)
    ]
    if any(value.tzinfo is None for value in dates):
        raise ValueError("Timezone-aware boundaries required")
    if not now <= dates[0] < dates[1] < dates[2]:
        raise ValueError(
            "Freeze and all split boundaries must precede untouched future holdout"
        )
    if not version or not policy or not rationale:
        raise ValueError("Version, complete policy and rationale required")
    with _lock:
        if any(row["version"] == version for row in read_records(path)):
            raise ValueError("Frozen policy version is immutable; create a new version")
        row = {
            "version": version,
            "policy": policy,
            "frozen_at": now.isoformat(),
            "policy_hash": hashlib.sha256(
                json.dumps(policy, sort_keys=True).encode()
            ).hexdigest(),
            "development_end": dates[0].isoformat(),
            "holdout_start": dates[1].isoformat(),
            "holdout_end": dates[2].isoformat(),
            "rationale": rationale,
            "role": "CHALLENGER",
            "promotion": "NOT_PROMOTED",
            "live_capital_allowed": False,
            "automatic_real_money_execution": False,
        }
        append_record(path, row)
        return row


def classify_observation(observation, freeze):
    original = observation.get("evidence_class")
    if original != "FORWARD_COLLECTION":
        return original  # Historical, PAPER, TEST and DIAGNOSTIC never upgraded.
    if observation.get("policy_version") != freeze["version"]:
        return original
    if observation.get("policy_hash") != freeze.get("policy_hash"):
        return original  # A version label alone cannot prove the frozen rules match.
    observed = datetime.fromisoformat(observation["timestamp"])
    parsed = {
        key: datetime.fromisoformat(freeze[key])
        for key in ("frozen_at", "development_end", "holdout_start", "holdout_end")
    }
    if observed < parsed["frozen_at"]:
        return original
    if observed <= parsed["development_end"]:
        return "DEVELOPMENT"
    if parsed["holdout_start"] <= observed < parsed["holdout_end"]:
        return "HOLDOUT"
    return original
