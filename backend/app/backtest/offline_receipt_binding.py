"""Fail-closed offline historical receipt binding.

This layer delegates verification to the existing backend audit.
It does not authenticate historical publication or permit trading.
"""

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from app.backtest.offline_evidence_snapshot import (
    capture_evidence_snapshot,
    EvidenceSnapshotError,
)

from app.backtest.historical_availability_audit import (
    audit_historical_availability_bytes,
)



def _evidence_fingerprints(paths: tuple[Path, ...]) -> tuple[str, ...]:
    fingerprints = []

    for path in paths:
        digest = sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        fingerprints.append(digest.hexdigest())

    return tuple(fingerprints)


@dataclass(frozen=True)
class OfflineReceiptBinding:
    classification: str
    integrity_verified: bool
    historical_availability_authenticated: bool
    predictive_skill_established: bool
    reasons: tuple[str, ...]


def bind_offline_receipt(
    dataset: Path,
    manifest: Path,
    receipt: Path,
    *,
    expected_decision_at: str,
    expected_source_id: str,
    expected_source_record_id: str,
) -> OfflineReceiptBinding:
    expectations = (
        expected_decision_at,
        expected_source_id,
        expected_source_record_id,
    )

    if any(not isinstance(value, str) or not value.strip()
           for value in expectations):
        return OfflineReceiptBinding(
            "EVIDENCE_REFUSED",
            False,
            False,
            False,
            ("External decision and source identities are required",),
        )

    if any(not isinstance(value, Path)
           for value in (dataset, manifest, receipt)):
        return OfflineReceiptBinding(
            "EVIDENCE_REFUSED",
            False,
            False,
            False,
            ("Dataset, manifest and receipt paths are required",),
        )

    paths = (dataset, manifest, receipt)

    try:
        before = _evidence_fingerprints(paths)
        captured = capture_evidence_snapshot(paths)

        # Reject persistent changes occurring during capture.
        captured_fingerprints = tuple(
            sha256(payload).hexdigest()
            for payload in captured
        )
        if captured_fingerprints != before:
            return OfflineReceiptBinding(
                "EVIDENCE_REFUSED",
                False,
                False,
                False,
                ("Evidence changed during snapshot capture",),
            )

        audit = audit_historical_availability_bytes(
            captured[0],
            captured[1],
            receipt_bytes=captured[2],
            expected_decision_at=expected_decision_at,
            expected_source_id=expected_source_id,
            expected_source_record_id=expected_source_record_id,
        )

        after = _evidence_fingerprints(paths)
    except (OSError, ValueError) as exc:
        return OfflineReceiptBinding(
            "EVIDENCE_REFUSED",
            False,
            False,
            False,
            ("Evidence snapshot unavailable: " + str(exc),),
        )

    if before != after:
        return OfflineReceiptBinding(
            "EVIDENCE_REFUSED",
            False,
            False,
            False,
            ("Evidence files changed during verification",),
        )

    return OfflineReceiptBinding(
        audit.classification,
        audit.integrity_verified,
        False,
        False,
        audit.reasons,
    )
