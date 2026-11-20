"""Version valuation evidence independently of price and allocation decisions."""

from datetime import datetime, timezone
import hashlib
import json
from app.investment.prospective_evidence import (
    append_record,
    read_records,
    _lock,
    POLICY_VERSION,
)
from app.investment.storage import DATA_DIR

REVISIONS = DATA_DIR / "valuation_revisions.jsonl"


def version_valuation(observation, path=REVISIONS, *, previous_records=None):
    features = observation.get("features") or {}
    decision = features.get("decision_inputs") or {}
    basis = {
        "normalization": observation.get("valuation"),
        "provenance": features.get("valuation_provenance"),
        "fundamentals_score": decision.get("fundamentals_score"),
        "thesis_intact": decision.get("thesis_intact"),
        "value_trap": decision.get("value_trap"),
    }
    digest = hashlib.sha256(
        json.dumps(basis, sort_keys=True, default=str).encode()
    ).hexdigest()
    prediction = observation.get("prediction") or {}
    values = {
        "fair_value_anchor": prediction.get("fair_value_anchor"),
        "normalization": observation.get("valuation"),
        "levels": prediction.get("entry_ladder", {}).get("levels", []),
    }
    # 'Reached' changes with price and is not a valuation revision.
    values["levels"] = [
        {k: v for k, v in row.items() if k != "reached"} for row in values["levels"]
    ]
    with _lock:
        records = read_records(path) if previous_records is None else previous_records
        prior = next(
            (
                row
                for row in reversed(records)
                if row["symbol"] == observation["symbol"]
            ),
            None,
        )
        price = observation["price"]
        price_change = (
            price / prior["reference_price"] - 1
            if prior and prior.get("reference_price")
            else None
        )
        if prior and prior["evidence_hash"] == digest:
            return {
                **prior,
                "price_change": price_change,
                "revision_status": (
                    "PRICE_ANCHOR_DRIFT"
                    if prior["new_values"] != values
                    else "UNCHANGED"
                ),
                "current_price": price,
            }
        old = prior["new_values"] if prior else None
        if (
            old
            and old.get("normalization") == values.get("normalization")
            and old != values
        ):
            # Scores and refreshed source timestamps can move with price; neither
            # permits different targets from the same valuation distribution.
            return {
                **prior,
                "price_change": price_change,
                "revision_status": "PRICE_ANCHOR_DRIFT",
                "current_price": price,
            }
        old_fair = old.get("fair_value_anchor") if old else None
        new_fair = values.get("fair_value_anchor")
        row = {
            "symbol": observation["symbol"],
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "observation_id": observation["observation_id"],
            "policy_version": observation["policy_version"],
            "source_timestamp": observation.get("source_timestamp"),
            "valuation_model_version": "evidence-versioned-valuation-v1",
            "evidence_hash": digest,
            "old_values": old,
            "new_values": values,
            "evidence_used": basis,
            "reference_price": price,
            "price_change": price_change,
            "fair_value_change": (
                new_fair / old_fair - 1 if old_fair and new_fair else None
            ),
            "fundamental_change": (
                None
                if not prior
                else any(
                    prior["evidence_used"].get(k) != basis[k]
                    for k in ("fundamentals_score", "thesis_intact", "value_trap")
                )
            ),
            "valuation_assumption_change": bool(
                prior
                and prior["evidence_used"].get("normalization")
                != basis["normalization"]
            ),
            "confidence": observation.get("confidence", "UNKNOWN"),
            "revision_status": (
                "INITIAL_EVIDENCE" if not prior else "FUNDAMENTAL_FAIR_VALUE_REVISION"
            ),
            "reason": (
                "First preserved valuation evidence"
                if not prior
                else "Recorded valuation sources or thesis/fundamental inputs changed; price excluded from evidence hash"
            ),
            "live_capital_allowed": False,
        }
        append_record(path, row)
        return row


def review_current_valuations(board, research, path=REVISIONS):
    """Version changed current evidence without creating extra performance samples."""
    from app.investment.prospective_evidence import _eligible_source

    now = datetime.now(timezone.utc)
    latest = {}
    for source in research:
        symbol = str(source.get("symbol") or "").upper().strip()
        if symbol and (
            symbol not in latest
            or str(source.get("timestamp") or "")
            > str(latest[symbol].get("timestamp") or "")
        ):
            latest[symbol] = source
    results = []
    previous_records = read_records(path)
    for item in board:
        symbol = str(item.get("symbol") or "").upper().strip()
        source = latest.get(symbol)
        features = item.get("quality_dips_v2") or {}
        prediction = features.get("quality_dips_v3") or {}
        if not source or not prediction or not _eligible_source(source, now):
            continue
        results.append(
            version_valuation(
                {
                    "symbol": symbol,
                    "price": source["price"],
                    "timestamp": now.isoformat(),
                    "source_timestamp": source["timestamp"],
                    "observation_id": None,
                    "policy_version": POLICY_VERSION,
                    "features": features,
                    "prediction": prediction,
                    "valuation": features.get("normalization_value"),
                    "confidence": features.get("evidence_quality", "UNKNOWN"),
                },
                path,
                previous_records=previous_records,
            )
        )
    return results


def actionability(observation, policy):
    """A challenger planning layer. Explicit required-return assumptions only."""
    inputs = (observation.get("features") or {}).get("decision_inputs") or {}
    prediction = observation.get("prediction") or {}
    normalization = observation.get("valuation") or {}
    blockers = list(prediction.get("blockers") or [])
    gate = (observation.get("features") or {}).get("evidence_gate") or {}
    if not gate.get("gate_passed"):
        blockers.extend(
            gate.get("blockers") or ["EVIDENCE_FRESHNESS_AND_QUALITY_UNVERIFIED"]
        )
    if not inputs.get("thesis_intact") or inputs.get("value_trap"):
        blockers.append("THESIS_BROKEN_OR_UNVERIFIED")
    hurdle = policy.get("minimum_conservative_upside")
    conservative = normalization.get("conservative")
    if isinstance(conservative, dict):
        conservative = conservative.get("value")
    if (
        not isinstance(hurdle, (int, float))
        or hurdle <= 0
        or not isinstance(conservative, (int, float))
        or conservative <= 0
    ):
        blockers.append("EXPLICIT_RETURN_HURDLE_OR_VALUATION_MISSING")
        zone = None
    else:
        zone = conservative / (1 + hurdle)
    price = observation.get("price")
    eligible = (
        not blockers
        and zone is not None
        and isinstance(price, (int, float))
        and price <= zone
    )
    return {
        "status": "ACTIONABLE_RESEARCH_ZONE" if eligible else "WAIT",
        "blockers": blockers,
        "current_price": price,
        "fair_value_range": normalization,
        "uncertainty_range": (
            (normalization.get("optimistic") - conservative)
            if isinstance(normalization.get("optimistic"), (int, float))
            and isinstance(conservative, (int, float))
            else None
        ),
        "research_age_days": gate.get("research_age_days"),
        "recalculated_at": observation.get("timestamp"),
        "expected_price_return_range": {
            key: (
                value / price - 1
                if isinstance(value, (int, float))
                and isinstance(price, (int, float))
                and price > 0
                else None
            )
            for key, value in normalization.items()
        },
        "actionable_zone_max": zone,
        "preferred_accumulation_price": zone,
        "exceptional_opportunity_price": next(
            (
                row.get("limit_price")
                for row in prediction.get("entry_ladder", {}).get("levels", [])
                if row.get("level") == "L4"
            ),
            None,
        ),
        "valuation_levels": prediction.get("entry_ladder", {}).get("levels", []),
        "policy_role": "CHALLENGER_PLANNING_ASSUMPTION",
        "execution": "MANUAL_ONLY",
        "note": "Separate planning zone never changes frozen L levels; allocation still requires portfolio risk checks.",
    }
