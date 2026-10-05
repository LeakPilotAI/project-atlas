"""Read-only evidence-health checkpoint persistence.

This module stores diagnostics only. It is separate from strategy journals and
cannot place orders or change strategy state, thresholds, sizing, or exits.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Dict, Optional

CHECKPOINT_PATH = Path(__file__).resolve().parents[2] / "data" / "evidence_health_checkpoints.jsonl"
MAX_HISTORY = 500
DEFAULT_LIMIT = 50
MIN_UNCHANGED_INTERVAL_SECONDS = 3600


def _dt(value: Any) -> Optional[datetime]:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None


def load_history(path: Path = CHECKPOINT_PATH, limit: int = DEFAULT_LIMIT) -> list[Dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[Dict[str, Any]] = []
    try:
        with path.open(encoding="utf-8") as stream:
            for raw in stream:
                if not raw.strip():
                    continue
                try:
                    row = json.loads(raw)
                except (json.JSONDecodeError, TypeError):
                    continue
                if isinstance(row, dict) and row.get("telemetry_only") is True:
                    rows.append(row)
    except OSError:
        return []
    return rows[-max(1, min(int(limit), MAX_HISTORY)):]


def previous_lanes(history: list[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    if not history:
        return {}
    lanes = history[-1].get("lanes") or {}
    return {str(name): dict(value) for name, value in lanes.items() if isinstance(value, dict)}


def observation(report: Dict[str, Any], observed_at: Optional[datetime] = None) -> Dict[str, Any]:
    lanes: Dict[str, Dict[str, Any]] = {}
    for lane in report.get("lanes") or []:
        integrity = lane.get("journal_integrity") or {}
        freshness = lane.get("freshness") or {}
        health = lane.get("evidence_health") or {}
        lanes[str(lane.get("lane"))] = {
            "sample_size": int(lane.get("sample_size") or 0),
            "open_sample_size": int(lane.get("open_sample_size") or 0),
            "latest_evidence_at": freshness.get("latest_evidence_at"),
            "evidence_health_band": health.get("band"),
            "integrity_status": integrity.get("status"),
            "reconstruction_status": integrity.get("reconstruction_status"),
            "malformed_records": integrity.get("malformed_records"),
            "last_durable_evidence_at": integrity.get("last_durable_evidence_at"),
        }
    return {
        "observed_at": (observed_at or datetime.now(timezone.utc)).isoformat(),
        "scorecard_version": report.get("scorecard_version"),
        "telemetry_only": True,
        "performance_interpretation": None,
        "strategy_action": None,
        "lanes": lanes,
    }


def persist(report: Dict[str, Any], path: Path = CHECKPOINT_PATH, now: Optional[datetime] = None) -> Dict[str, Any]:
    observed = now or datetime.now(timezone.utc)
    row = observation(report, observed)
    history = load_history(path, MAX_HISTORY)
    if history:
        previous = history[-1]
        same = previous.get("scorecard_version") == row.get("scorecard_version") and previous.get("lanes") == row.get("lanes")
        previous_at = _dt(previous.get("observed_at"))
        if same and previous_at is not None and (observed - previous_at).total_seconds() < MIN_UNCHANGED_INTERVAL_SECONDS:
            return {"persisted": False, "reason": "UNCHANGED_WITHIN_INTERVAL"}
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(row, sort_keys=True) + "\n")
        history.append(row)
        if len(history) > MAX_HISTORY:
            retained = history[-MAX_HISTORY:]
            temp = path.with_suffix(path.suffix + ".tmp")
            with temp.open("w", encoding="utf-8") as stream:
                for item in retained:
                    stream.write(json.dumps(item, sort_keys=True) + "\n")
            temp.replace(path)
        return {"persisted": True, "reason": "RECORDED"}
    except OSError:
        return {"persisted": False, "reason": "TELEMETRY_WRITE_FAILED"}


def history_view(path: Path = CHECKPOINT_PATH, limit: int = DEFAULT_LIMIT) -> Dict[str, Any]:
    rows = load_history(path, limit)
    return {
        "telemetry_only": True,
        "performance_interpretation": None,
        "strategy_action": None,
        "retention_max": MAX_HISTORY,
        "returned": len(rows),
        "checkpoints": rows,
    }


def transition_summary(history: list[Dict[str, Any]]) -> Dict[str, Any]:
    """Describe adjacent telemetry movement without interpreting performance."""
    if len(history) < 2:
        return {"status": "BASELINE", "telemetry_only": True, "performance_interpretation": None, "strategy_action": None, "lanes": {}}
    previous, current = history[-2], history[-1]
    previous_lanes_map = previous.get("lanes") or {}
    current_lanes_map = current.get("lanes") or {}
    lanes: Dict[str, Dict[str, Any]] = {}
    for name in sorted(set(previous_lanes_map) | set(current_lanes_map)):
        before = previous_lanes_map.get(name) or {}
        after = current_lanes_map.get(name) or {}
        before_sample = int(before.get("sample_size") or 0)
        after_sample = int(after.get("sample_size") or 0)
        before_time = _dt(before.get("latest_evidence_at"))
        after_time = _dt(after.get("latest_evidence_at"))
        freshness_delta = None
        if before_time is not None and after_time is not None:
            freshness_delta = round((after_time - before_time).total_seconds() / 3600.0, 4)
        lanes[name] = {
            "sample_delta": after_sample - before_sample,
            "freshness_delta_hours": freshness_delta,
            "integrity_transition": str(before.get("integrity_status") or "UNKNOWN") + "->" + str(after.get("integrity_status") or "UNKNOWN"),
            "reconstruction_transition": str(before.get("reconstruction_status") or "UNKNOWN") + "->" + str(after.get("reconstruction_status") or "UNKNOWN"),
            "health_transition": str(before.get("evidence_health_band") or "UNKNOWN") + "->" + str(after.get("evidence_health_band") or "UNKNOWN"),
            "performance_interpretation": None,
            "strategy_action": None,
        }
    return {"status": "ADJACENT_CHECKPOINTS", "telemetry_only": True, "performance_interpretation": None, "strategy_action": None, "from_observed_at": previous.get("observed_at"), "to_observed_at": current.get("observed_at"), "lanes": lanes}


def capture_status(history: list[Dict[str, Any]], now: Optional[datetime] = None) -> Dict[str, Any]:
    """Expose checkpoint cadence without causing or requiring a write."""
    current = now or datetime.now(timezone.utc)
    if not history:
        return {"status": "BASELINE_DUE", "last_observed_at": None, "next_eligible_at": current.isoformat(), "seconds_until_eligible": 0, "minimum_unchanged_interval_seconds": MIN_UNCHANGED_INTERVAL_SECONDS, "telemetry_only": True, "strategy_action": None}
    last_at = _dt(history[-1].get("observed_at"))
    if last_at is None:
        return {"status": "TIMESTAMP_UNAVAILABLE", "last_observed_at": history[-1].get("observed_at"), "next_eligible_at": None, "seconds_until_eligible": None, "minimum_unchanged_interval_seconds": MIN_UNCHANGED_INTERVAL_SECONDS, "telemetry_only": True, "strategy_action": None}
    elapsed = max(0.0, (current - last_at).total_seconds())
    remaining = max(0, int(MIN_UNCHANGED_INTERVAL_SECONDS - elapsed))
    next_at = last_at.timestamp() + MIN_UNCHANGED_INTERVAL_SECONDS
    return {"status": "ELIGIBLE" if remaining == 0 else "DEDUP_WINDOW", "last_observed_at": last_at.isoformat(), "next_eligible_at": datetime.fromtimestamp(next_at, timezone.utc).isoformat(), "seconds_until_eligible": remaining, "minimum_unchanged_interval_seconds": MIN_UNCHANGED_INTERVAL_SECONDS, "telemetry_only": True, "strategy_action": None}


def diagnostic_alerts(transitions: Dict[str, Any]) -> list[Dict[str, Any]]:
    """Return integrity/reconstruction diagnostics only; never an action signal."""
    alerts: list[Dict[str, Any]] = []
    for lane, item in (transitions.get("lanes") or {}).items():
        integrity = str(item.get("integrity_transition") or "")
        reconstruction = str(item.get("reconstruction_transition") or "")
        integrity_after = integrity.split("->")[-1]
        reconstruction_after = reconstruction.split("->")[-1]
        if integrity_after not in {"OK", "MISSING_EMPTY", "UNKNOWN"} or reconstruction_after not in {"OK", "UNKNOWN"}:
            alerts.append({"lane": lane, "severity": "DIAGNOSTIC", "integrity_transition": integrity, "reconstruction_transition": reconstruction, "telemetry_only": True, "performance_interpretation": None, "strategy_action": None, "automatic_response": None})
    return alerts
