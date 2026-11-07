"""Append-only observations of subsequent prices; unknown fills stay unknown."""
from datetime import datetime, timezone
import hashlib
import json

from app.investment.history import load_bars
from app.investment.outcomes import measure_outcomes
from app.investment.prospective_evidence import OBSERVATIONS, append_record, read_records, _lock
from app.investment.storage import DATA_DIR

OUTCOMES = DATA_DIR / "prospective_v3_outcomes.jsonl"


def outcome_for(observation, bars, now):
    observed = datetime.fromisoformat(observation["timestamp"])
    # Exclude the observation session and today's incomplete daily session.
    # Retain provider timestamps to reproduce what the evaluator could see.
    eligible = sorted((bar for bar in bars if observed.date().isoformat() < bar.session_date < now.date().isoformat()
                       and (bar.effective_timestamp is None or bar.effective_timestamp <= now)
                       and (bar.retrieved_at is None or bar.retrieved_at <= now)), key=lambda b: b.session_date)
    measures = measure_outcomes(price_at_t=observation["price"], as_of=observed, bars=eligible, now=now)
    interactions = []
    for level in (observation.get("prediction", {}).get("entry_ladder", {}).get("levels") or []):
        target = level.get("limit_price")
        if not isinstance(target, (float, int)) or target <= 0:
            continue
        first = next((bar for bar in eligible if bar.low is not None and bar.low <= target), None)
        interactions.append({"level": level.get("level"), "target": target,
                             "touch_session": first.session_date if first else None,
                             "sessions_to_touch": eligible.index(first) + 1 if first else None,
                             "status": "TOUCHED_NOT_ASSUMED_FILLED" if first else "NOT_YET_OBSERVED"})
    return {"observation_id": observation["observation_id"], "policy_version": observation["policy_version"],
            "execution_model_version": observation["execution_model_version"],
            "evidence_class": observation["evidence_class"], "symbol": observation["symbol"],
            "status": "TRACKING" if eligible else "UNKNOWN", "measures": measures,
            "price_path": [bar.as_dict() for bar in eligible], "target_interactions": interactions,
            "paper_fill": "UNKNOWN", "stop_interaction": "UNKNOWN_NO_FROZEN_STOP",
            "result_r": None, "note": "Price observation is not an executed trade; no stop or favorable fill invented.",
            "live_capital_allowed": False, "automatic_real_money_execution": False}


def refresh_outcomes(observations_path=OBSERVATIONS, outcomes_path=OUTCOMES, bars_loader=load_bars):
    now = datetime.now(timezone.utc)
    with _lock:
        previous = {row["observation_id"]: row.get("content_hash") for row in read_records(outcomes_path)}
        cache = {}
        created = []
        for observation in read_records(observations_path):
            if observation.get("evidence_class") not in {"FORWARD_COLLECTION", "DEVELOPMENT", "HOLDOUT", "PAPER"}:
                continue
            symbol = observation["symbol"]
            if symbol not in cache:
                cache[symbol] = bars_loader(symbol)
            result = outcome_for(observation, cache[symbol], now)
            digest = hashlib.sha256(json.dumps(result, sort_keys=True, default=str).encode()).hexdigest()
            if previous.get(observation["observation_id"]) == digest:
                continue
            result.update({"content_hash": digest, "evaluated_at": now.isoformat()})
            append_record(outcomes_path, result)
            previous[observation["observation_id"]] = digest
            created.append(result)
        return created
