"""Quality Dips V2 DEVELOPMENT freeze and untouched HOLDOUT boundary.

This module makes the research split explicit. Once a DEVELOPMENT policy manifest is
frozen, the HOLDOUT boundary is immutable for that cycle and same-window retuning is
forbidden. This is decision-support infrastructure only; it does not place trades.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from hashlib import sha256
import json
from typing import Any, Iterable, Optional


@dataclass(frozen=True)
class DevelopmentPolicyFreeze:
    cycle: str
    frozen_at: str
    development_start: str
    development_end: str
    holdout_start: str
    holdout_end: str
    policy_version: str
    min_upside_hurdle_pct: float
    deep_value_hurdle_pct: float
    generational_hurdle_pct: float
    l1_hurdle_pct: float
    l2_hurdle_pct: float
    l3_hurdle_pct: float
    l4_hurdle_pct: float
    same_window_retuning_allowed: bool = False
    lookahead_allowed: bool = False
    live_capital_allowed: bool = False
    automatic_real_money_execution: bool = False


def _canonical_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def freeze_manifest(freeze: DevelopmentPolicyFreeze) -> dict[str, Any]:
    """Return an immutable-policy manifest plus deterministic SHA-256 fingerprint."""
    payload = asdict(freeze)
    if payload["same_window_retuning_allowed"] or payload["lookahead_allowed"]:
        raise ValueError("Quality Dips V2 freeze must forbid retuning and lookahead")
    if not all(
        isinstance(payload[k], str) and payload[k]
        for k in (
            "cycle",
            "frozen_at",
            "development_start",
            "development_end",
            "holdout_start",
            "holdout_end",
            "policy_version",
        )
    ):
        raise ValueError("freeze manifest requires explicit non-empty cycle/date/version fields")
    fingerprint = sha256(_canonical_json(payload).encode("utf-8")).hexdigest()
    return {
        "status": "DEVELOPMENT_POLICY_FROZEN",
        "policy": payload,
        "policy_sha256": fingerprint,
        "holdout_untouched": True,
        "same_window_retuning_allowed": False,
        "lookahead_allowed": False,
        "execution": "MANUAL_ONLY",
        "live_capital_allowed": False,
        "automatic_real_money_execution": False,
    }


def classify_partition(timestamp: str, manifest: dict[str, Any]) -> str:
    """Classify a PIT observation into DEVELOPMENT, HOLDOUT, or OUT_OF_SCOPE.

    ISO-like timestamps compare lexicographically when normalized to the same format,
    which is the contract used by the V2 validation dataset.
    """
    policy = dict(manifest.get("policy") or {})
    ts = str(timestamp or "")
    if not ts:
        return "OUT_OF_SCOPE"
    dev_start = str(policy.get("development_start") or "")
    dev_end = str(policy.get("development_end") or "")
    hold_start = str(policy.get("holdout_start") or "")
    hold_end = str(policy.get("holdout_end") or "")
    if dev_start and dev_end and dev_start <= ts <= dev_end:
        return "DEVELOPMENT"
    if hold_start and hold_end and hold_start <= ts <= hold_end:
        return "HOLDOUT"
    return "OUT_OF_SCOPE"


def audit_untouched_holdout(
    development_rows: Iterable[dict[str, Any]],
    holdout_rows: Iterable[dict[str, Any]],
    manifest: dict[str, Any],
) -> dict[str, Any]:
    """Fail closed if the supplied split violates the frozen boundary.

    This does not judge performance. It only establishes that rows assigned to the
    HOLDOUT partition are inside the holdout date window and DEVELOPMENT rows are not.
    """
    violations: list[str] = []
    dev_count = 0
    hold_count = 0

    for row in development_rows:
        if not isinstance(row, dict):
            violations.append("non-dict development row")
            continue
        dev_count += 1
        part = classify_partition(str(row.get("timestamp") or ""), manifest)
        if part != "DEVELOPMENT":
            violations.append(f"development row outside DEVELOPMENT boundary: {row.get('timestamp')}")

    for row in holdout_rows:
        if not isinstance(row, dict):
            violations.append("non-dict holdout row")
            continue
        hold_count += 1
        part = classify_partition(str(row.get("timestamp") or ""), manifest)
        if part != "HOLDOUT":
            violations.append(f"holdout row outside untouched HOLDOUT boundary: {row.get('timestamp')}")

    return {
        "status": "HOLDOUT_BOUNDARY_GREEN" if not violations else "HOLDOUT_BOUNDARY_BLOCKED",
        "development_rows": dev_count,
        "holdout_rows": hold_count,
        "violations": violations,
        "holdout_untouched": not violations,
        "same_window_retuning_allowed": False,
        "lookahead_allowed": False,
        "execution": "MANUAL_ONLY",
        "live_capital_allowed": False,
        "automatic_real_money_execution": False,
    }


DEFAULT_V2_FREEZE = DevelopmentPolicyFreeze(
    cycle="QUALITY_DIPS_V2_PATIENT_CAPITAL",
    frozen_at="2026-09-17",
    development_start="2024-01-01",
    development_end="2025-06-30T23:59:59",
    holdout_start="2025-07-01",
    holdout_end="2025-12-31T23:59:59",
    policy_version="quality-dips-v2-phase8-freeze-v1",
    min_upside_hurdle_pct=29.0,
    deep_value_hurdle_pct=40.0,
    generational_hurdle_pct=50.0,
    l1_hurdle_pct=29.0,
    l2_hurdle_pct=35.0,
    l3_hurdle_pct=40.0,
    l4_hurdle_pct=50.0,
)


def default_manifest() -> dict[str, Any]:
    return freeze_manifest(DEFAULT_V2_FREEZE)
