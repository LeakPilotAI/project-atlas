"""Read-only evidence-health checkpoint persistence.

This module stores diagnostics only. It is separate from strategy journals and
cannot place orders or change strategy state, thresholds, sizing, or exits.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, Optional

CHECKPOINT_PATH = Path(__file__).resolve().parents[2] / "data" / "evidence_health_checkpoints.jsonl"
MAX_HISTORY = 500
DEFAULT_LIMIT = 50
MIN_UNCHANGED_INTERVAL_SECONDS = 3600
SUPPORTED_SCORECARD_VERSIONS = {"cross-strategy-evidence-health-v3"}


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


def checkpoint_fingerprint(row: Dict[str, Any]) -> str:
    identity = {"scorecard_version": row.get("scorecard_version"), "lanes": row.get("lanes") or {}}
    payload = json.dumps(identity, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


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
                if isinstance(row, dict) and row.get("telemetry_only") is True and row.get("scorecard_version") in SUPPORTED_SCORECARD_VERSIONS:
                    fingerprint = checkpoint_fingerprint(row)
                    if rows and checkpoint_fingerprint(rows[-1]) == fingerprint:
                        continue
                    observed = _dt(row.get("observed_at"))
                    if observed is None:
                        continue
                    if rows:
                        previous_observed = _dt(rows[-1].get("observed_at"))
                        if previous_observed is not None and observed <= previous_observed:
                            continue
                    item = dict(row)
                    item["checkpoint_fingerprint"] = fingerprint
                    rows.append(item)
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


def journal_integrity(path: Path = CHECKPOINT_PATH) -> Dict[str, Any]:
    """Inspect the telemetry journal itself without trusting malformed rows."""
    if not path.exists():
        return {"status":"MISSING_EMPTY","readable_rows":0,"malformed_rows":0,"ignored_non_telemetry_rows":0,"newest_valid_checkpoint":None,"retention_status":"WITHIN_LIMIT","telemetry_only":True,"strategy_action":None}
    readable = malformed = ignored = 0
    newest = None
    try:
        with path.open(encoding="utf-8") as stream:
            for raw in stream:
                if not raw.strip():
                    continue
                try:
                    row=json.loads(raw)
                except (json.JSONDecodeError, TypeError):
                    malformed += 1
                    continue
                if not isinstance(row,dict) or row.get("telemetry_only") is not True:
                    ignored += 1
                    continue
                readable += 1
                newest=row.get("observed_at") or newest
    except OSError:
        return {"status":"UNREADABLE","readable_rows":0,"malformed_rows":0,"ignored_non_telemetry_rows":0,"newest_valid_checkpoint":None,"retention_status":"UNKNOWN","telemetry_only":True,"strategy_action":None}
    status="PARTIAL" if malformed or ignored else "OK"
    retention="OVER_LIMIT" if readable > MAX_HISTORY else "WITHIN_LIMIT"
    return {"status":status,"readable_rows":readable,"malformed_rows":malformed,"ignored_non_telemetry_rows":ignored,"newest_valid_checkpoint":newest,"retention_status":retention,"telemetry_only":True,"performance_interpretation":None,"strategy_action":None,"automatic_response":None}


def schema_compatibility(path: Path = CHECKPOINT_PATH) -> Dict[str, Any]:
    supported = unknown = malformed = 0
    unknown_versions: set[str] = set()
    if not path.exists():
        return {"status":"NO_ROWS","supported_rows":0,"unknown_version_rows":0,"malformed_rows":0,"supported_versions":sorted(SUPPORTED_SCORECARD_VERSIONS),"unknown_versions":[],"telemetry_only":True,"strategy_action":None}
    try:
        with path.open(encoding="utf-8") as stream:
            for raw in stream:
                if not raw.strip(): continue
                try: row=json.loads(raw)
                except (json.JSONDecodeError,TypeError): malformed += 1; continue
                if not isinstance(row,dict) or row.get("telemetry_only") is not True: continue
                version=str(row.get("scorecard_version") or "MISSING")
                if version in SUPPORTED_SCORECARD_VERSIONS: supported += 1
                else: unknown += 1; unknown_versions.add(version)
    except OSError:
        return {"status":"UNREADABLE","supported_rows":0,"unknown_version_rows":0,"malformed_rows":0,"supported_versions":sorted(SUPPORTED_SCORECARD_VERSIONS),"unknown_versions":[],"telemetry_only":True,"strategy_action":None}
    status="UNKNOWN_VERSION_PRESENT" if unknown else ("MALFORMED_PRESENT" if malformed else "COMPATIBLE")
    return {"status":status,"supported_rows":supported,"unknown_version_rows":unknown,"malformed_rows":malformed,"supported_versions":sorted(SUPPORTED_SCORECARD_VERSIONS),"unknown_versions":sorted(unknown_versions),"unknown_rows_used_as_current_evidence":False,"telemetry_only":True,"performance_interpretation":None,"strategy_action":None,"automatic_response":None}


def replay_diagnostics(path: Path = CHECKPOINT_PATH) -> Dict[str, Any]:
    physical_supported = duplicates = 0
    previous_fingerprint = None
    fingerprints: set[str] = set()
    replayed_nonadjacent = 0
    if path.exists():
        try:
            with path.open(encoding="utf-8") as stream:
                for raw in stream:
                    if not raw.strip(): continue
                    try: row=json.loads(raw)
                    except (json.JSONDecodeError,TypeError): continue
                    if not isinstance(row,dict) or row.get("telemetry_only") is not True or row.get("scorecard_version") not in SUPPORTED_SCORECARD_VERSIONS: continue
                    physical_supported += 1
                    fp=checkpoint_fingerprint(row)
                    if fp == previous_fingerprint: duplicates += 1
                    elif fp in fingerprints: replayed_nonadjacent += 1
                    fingerprints.add(fp); previous_fingerprint=fp
        except OSError:
            return {"status":"UNREADABLE","telemetry_only":True,"strategy_action":None}
    usable=len(load_history(path,MAX_HISTORY))
    status="REPLAY_PRESENT" if replayed_nonadjacent else ("DUPLICATE_PRESENT" if duplicates else "CLEAN")
    return {"status":status,"physical_supported_rows":physical_supported,"usable_history_rows":usable,"adjacent_duplicate_rows":duplicates,"nonadjacent_replay_rows":replayed_nonadjacent,"unique_fingerprints":len(fingerprints),"duplicates_inflate_usable_history":False,"telemetry_only":True,"performance_interpretation":None,"strategy_action":None,"automatic_response":None}


def sequence_diagnostics(path: Path = CHECKPOINT_PATH) -> Dict[str, Any]:
    supported_rows = invalid_timestamps = ordering_anomalies = 0
    previous_at: Optional[datetime] = None
    newest_monotonic_at: Optional[datetime] = None
    if path.exists():
        try:
            with path.open(encoding="utf-8") as stream:
                for raw in stream:
                    if not raw.strip(): continue
                    try: row=json.loads(raw)
                    except (json.JSONDecodeError,TypeError): continue
                    if not isinstance(row,dict) or row.get("telemetry_only") is not True or row.get("scorecard_version") not in SUPPORTED_SCORECARD_VERSIONS: continue
                    supported_rows += 1
                    observed=_dt(row.get("observed_at"))
                    if observed is None:
                        invalid_timestamps += 1; continue
                    if previous_at is not None and observed <= previous_at:
                        ordering_anomalies += 1; continue
                    previous_at=observed; newest_monotonic_at=observed
        except OSError:
            return {"status":"UNREADABLE","telemetry_only":True,"strategy_action":None}
    usable=len(load_history(path,MAX_HISTORY))
    status="ORDERING_ANOMALY" if ordering_anomalies else ("INVALID_TIMESTAMP" if invalid_timestamps else "MONOTONIC")
    return {"status":status,"physical_supported_rows":supported_rows,"usable_monotonic_rows":usable,"ordering_anomaly_rows":ordering_anomalies,"invalid_timestamp_rows":invalid_timestamps,"newest_monotonic_checkpoint":newest_monotonic_at.isoformat() if newest_monotonic_at else None,"ordering_anomalies_used_for_transitions":False,"history_rewritten":False,"telemetry_only":True,"performance_interpretation":None,"strategy_action":None,"automatic_response":None}


def provenance_chain(path: Path = CHECKPOINT_PATH) -> Dict[str, Any]:
    history = load_history(path, MAX_HISTORY)
    links: list[Dict[str, Any]] = []
    previous: Optional[Dict[str, Any]] = None
    for row in history:
        fingerprint = row.get("checkpoint_fingerprint") or checkpoint_fingerprint(row)
        links.append({
            "observed_at": row.get("observed_at"),
            "checkpoint_fingerprint": fingerprint,
            "previous_checkpoint_fingerprint": (previous or {}).get("checkpoint_fingerprint"),
            "position": len(links),
        })
        previous = {"checkpoint_fingerprint": fingerprint}
    discontinuities = 0
    for index, link in enumerate(links):
        expected = None if index == 0 else links[index - 1]["checkpoint_fingerprint"]
        if link["previous_checkpoint_fingerprint"] != expected:
            discontinuities += 1
    return {
        "status": "CONTIGUOUS" if discontinuities == 0 else "DISCONTINUITY",
        "accepted_checkpoints": len(links),
        "derived_links": links,
        "chain_discontinuities": discontinuities,
        "chain_metadata_derived_only": True,
        "durable_history_rewritten": False,
        "backfill_performed": False,
        "telemetry_only": True,
        "performance_interpretation": None,
        "strategy_action": None,
        "automatic_response": None,
    }


def provenance_anchor(path: Path = CHECKPOINT_PATH, limit: int = MAX_HISTORY) -> Dict[str, Any]:
    full_history = load_history(path, MAX_HISTORY)
    retained = full_history[-max(1, int(limit)):] if full_history else []
    first = retained[0] if retained else None
    pruned_accepted = max(0, len(full_history) - len(retained))
    origin_kind = "NO_EVIDENCE" if first is None else ("RETAINED_WINDOW_ORIGIN" if pruned_accepted else "TRUE_JOURNAL_ORIGIN")
    return {
        "status": origin_kind,
        "retained_checkpoints": len(retained),
        "accepted_checkpoints_before_window": pruned_accepted,
        "first_retained_observed_at": (first or {}).get("observed_at"),
        "first_retained_fingerprint": (first or {}).get("checkpoint_fingerprint"),
        "predecessor_known_within_retained_window": False,
        "missing_predecessor_fabricated": False,
        "pruned_history_reconstructed": False,
        "backfill_performed": False,
        "telemetry_only": True,
        "performance_interpretation": None,
        "strategy_action": None,
        "automatic_response": None,
    }


def window_completeness(path: Path = CHECKPOINT_PATH, limit: int = MAX_HISTORY) -> Dict[str, Any]:
    anchor = provenance_anchor(path, limit)
    schema = schema_compatibility(path)
    replay = replay_diagnostics(path)
    sequence = sequence_diagnostics(path)
    reasons: list[str] = []
    if anchor.get("accepted_checkpoints_before_window", 0) > 0:
        reasons.append("RETENTION_TRUNCATED")
    if schema.get("unknown_version_rows", 0) > 0 or schema.get("malformed_rows", 0) > 0:
        reasons.append("SCHEMA_FILTERED")
    if replay.get("adjacent_duplicate_rows", 0) > 0 or replay.get("nonadjacent_replay_rows", 0) > 0:
        reasons.append("REPLAY_FILTERED")
    if sequence.get("ordering_anomaly_rows", 0) > 0 or sequence.get("invalid_timestamp_rows", 0) > 0:
        reasons.append("SEQUENCE_FILTERED")
    status = "COMPLETE" if not reasons else ("RETENTION_TRUNCATED" if reasons == ["RETENTION_TRUNCATED"] else "DIAGNOSTICALLY_FILTERED")
    return {
        "status": status,
        "reasons": reasons,
        "visible_usable_checkpoints": len(load_history(path, max(1, int(limit)))),
        "missing_observations_inferred": False,
        "continuity_inferred": False,
        "performance_inferred": False,
        "history_rewritten": False,
        "telemetry_only": True,
        "performance_interpretation": None,
        "strategy_action": None,
        "automatic_response": None,
    }


def exclusion_accounting(path: Path = CHECKPOINT_PATH) -> Dict[str, Any]:
    categories = {"usable": 0, "malformed_or_non_telemetry": 0, "unsupported_schema": 0, "replay_or_duplicate": 0, "invalid_timestamp": 0, "ordering_anomaly": 0}
    physical = 0
    previous_accepted_at: Optional[datetime] = None
    seen_fingerprints: set[str] = set()
    if path.exists():
        try:
            with path.open(encoding="utf-8") as stream:
                for raw in stream:
                    if not raw.strip():
                        continue
                    physical += 1
                    try:
                        row = json.loads(raw)
                    except (json.JSONDecodeError, TypeError):
                        categories["malformed_or_non_telemetry"] += 1; continue
                    if not isinstance(row, dict) or row.get("telemetry_only") is not True:
                        categories["malformed_or_non_telemetry"] += 1; continue
                    if row.get("scorecard_version") not in SUPPORTED_SCORECARD_VERSIONS:
                        categories["unsupported_schema"] += 1; continue
                    observed = _dt(row.get("observed_at"))
                    if observed is None:
                        categories["invalid_timestamp"] += 1; continue
                    fingerprint = checkpoint_fingerprint(row)
                    if fingerprint in seen_fingerprints:
                        categories["replay_or_duplicate"] += 1; continue
                    if previous_accepted_at is not None and observed <= previous_accepted_at:
                        categories["ordering_anomaly"] += 1; continue
                    categories["usable"] += 1
                    seen_fingerprints.add(fingerprint)
                    previous_accepted_at = observed
        except OSError:
            return {"status":"UNREADABLE","physical_rows":0,"categorized_rows":0,"reconciled":False,"categories":categories,"excluded_rows_used_as_evidence":False,"telemetry_only":True,"strategy_action":None}
    categorized = sum(categories.values())
    return {"status":"RECONCILED" if categorized == physical else "MISMATCH","physical_rows":physical,"categorized_rows":categorized,"reconciled":categorized == physical,"categories":categories,"excluded_rows_used_as_evidence":False,"missing_rows_inferred":False,"performance_inferred":False,"history_rewritten":False,"telemetry_only":True,"performance_interpretation":None,"strategy_action":None,"automatic_response":None}
