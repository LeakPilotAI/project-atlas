"""Offline structural contract for historical availability receipts.

A locally supplied receipt is NOT independent authentication.
This validator never grants historical authentication or trading authority.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from app.backtest.manifest import load_manifest_bytes

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_REQUIRED = frozenset({
    "schema_version", "dataset_sha256", "manifest_id",
    "source_id", "source_record_id", "published_at",
    "observed_at", "decision_at"
})


@dataclass(frozen=True)
class HistoricalEvidenceResult:
    accepted_structurally: bool
    historical_availability_authenticated: bool
    classification: str
    reasons: tuple[str, ...]


def _reject_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key: " + key)
        result[key] = value
    return result


def _reject_nonfinite(value):
    raise ValueError("nonfinite receipt value: " + value)


def _timestamp(value: object) -> datetime:
    if not isinstance(value, str):
        raise ValueError("timestamp must be a string")
    if not value.endswith("Z"):
        raise ValueError("timestamp must use UTC Z notation")
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.utcoffset() != UTC.utcoffset(result):
        raise ValueError("timestamp must be UTC")
    return result


def validate_historical_evidence_bytes(
    dataset_bytes: bytes,
    manifest_bytes: bytes,
    receipt_bytes: bytes,
    *,
    expected_decision_at: str | None = None,
    expected_source_id: str | None = None,
    expected_source_record_id: str | None = None,
) -> HistoricalEvidenceResult:
    reasons = []

    try:
        identity = load_manifest_bytes(
            manifest_bytes, dataset_bytes
        )
        payload = json.loads(
            receipt_bytes.decode("utf-8"),
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_nonfinite,
        )

        if not isinstance(payload, dict):
            raise ValueError("receipt must be an object")

        missing = sorted(_REQUIRED - payload.keys())
        if missing:
            raise ValueError("missing receipt fields: " + ", ".join(missing))

        if type(payload["schema_version"]) is not int or payload["schema_version"] != 1:
            raise ValueError("unsupported receipt schema")

        if payload["dataset_sha256"] != identity["dataset_sha256"]:
            raise ValueError("dataset identity mismatch")

        if payload["manifest_id"] != identity["manifest_id"]:
            raise ValueError("manifest identity mismatch")

        if not isinstance(payload["dataset_sha256"], str) or not _SHA256.fullmatch(payload["dataset_sha256"]):
            raise ValueError("invalid dataset checksum")

        for field in ("source_id", "source_record_id"):
            if not isinstance(payload[field], str) or not payload[field].strip():
                raise ValueError("invalid source identity: " + field)

        if expected_source_id is not None and payload["source_id"] != expected_source_id:
            raise ValueError("source identity contradicts expected source")

        if expected_source_record_id is not None and payload["source_record_id"] != expected_source_record_id:
            raise ValueError("record identity contradicts expected record")

        if expected_decision_at is not None:
            expected_decision = _timestamp(expected_decision_at)
            if _timestamp(payload["decision_at"]) != expected_decision:
                raise ValueError("decision timestamp contradicts expected decision")

        published = _timestamp(payload["published_at"])
        observed = _timestamp(payload["observed_at"])
        decision = _timestamp(payload["decision_at"])

        if published > observed:
            raise ValueError("publication occurs after observation")

        if observed > decision:
            raise ValueError("observation occurs after decision")

        if published > decision:
            raise ValueError("publication occurs after decision")

    except (OSError, ValueError, TypeError, KeyError, OverflowError) as exc:
        reasons.append(str(exc))
        return HistoricalEvidenceResult(
            False,
            False,
            "EVIDENCE_REFUSED",
            tuple(reasons),
        )

    return HistoricalEvidenceResult(
        True,
        False,
        "STRUCTURALLY_CONSISTENT_UNAUTHENTICATED",
        ("Receipt has no independently verified publication authority",),
    )


def validate_historical_evidence(
    dataset: Path,
    manifest: Path,
    receipt: Path,
    *,
    expected_decision_at: str | None = None,
    expected_source_id: str | None = None,
    expected_source_record_id: str | None = None,
) -> HistoricalEvidenceResult:
    """Compatibility interface for filesystem evidence."""
    try:
        dataset_bytes = Path(dataset).read_bytes()
        manifest_bytes = Path(manifest).read_bytes()
        receipt_bytes = Path(receipt).read_bytes()
    except (OSError, ValueError, TypeError) as exc:
        return HistoricalEvidenceResult(
            False, False, "EVIDENCE_REFUSED", (str(exc),)
        )

    return validate_historical_evidence_bytes(
        dataset_bytes,
        manifest_bytes,
        receipt_bytes,
        expected_decision_at=expected_decision_at,
        expected_source_id=expected_source_id,
        expected_source_record_id=expected_source_record_id,
    )
