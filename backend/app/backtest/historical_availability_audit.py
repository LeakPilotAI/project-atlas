"""Conservative offline historical availability audit.

A self-declared PIT manifest is not independent evidence of publication time.
This module never authenticates historical availability.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

from app.backtest.manifest import load_manifest
from app.backtest.historical_evidence_contract import validate_historical_evidence


@dataclass(frozen=True)
class HistoricalAvailabilityAudit:
    dataset: str
    manifest: str
    integrity_verified: bool
    historical_availability_authenticated: bool
    classification: str
    reasons: tuple[str, ...]


def audit_historical_availability(
    dataset: Path,
    manifest: Path,
    *,
    receipt: Path | None = None,
    expected_decision_at: str | None = None,
    expected_source_id: str | None = None,
    expected_source_record_id: str | None = None,
) -> HistoricalAvailabilityAudit:
    dataset = Path(dataset)
    manifest = Path(manifest)
    reasons = []

    try:
        payload = load_manifest(manifest, dataset)
    except (OSError, ValueError, TypeError, KeyError) as exc:
        reasons.append(f"manifest verification failed: {exc}")
        return HistoricalAvailabilityAudit(
            str(dataset),
            str(manifest),
            False,
            False,
            "INTEGRITY_REFUSED",
            tuple(reasons),
        )

    if not payload.get("pit_aligned") is True:
        reasons.append("PIT alignment not established")
    if payload.get("current_state_backfill_used") is not False:
        reasons.append("current-state backfill cannot establish availability")

    if reasons:
        return HistoricalAvailabilityAudit(
            str(dataset),
            str(manifest),
            False,
            False,
            "INTEGRITY_REFUSED",
            tuple(reasons),
        )

    if receipt is not None:
        if expected_decision_at is None:
            return HistoricalAvailabilityAudit(
                str(dataset),
                str(manifest),
                True,
                False,
                "EVIDENCE_REFUSED",
                ("External expected decision time is required",),
            )

        evidence = validate_historical_evidence(
            dataset,
            manifest,
            receipt,
            expected_decision_at=expected_decision_at,
            expected_source_id=expected_source_id,
            expected_source_record_id=expected_source_record_id,
        )

        # ATLAS_PHASE_2D3_REFUSAL_ONLY_AUTHORITY_GATE
        from app.backtest.historical_authority_assessment import (
            assess_historical_authority,
        )
        authority = assess_historical_authority(evidence)
        if (
            authority.authority_verified
            or authority.historical_availability_authenticated
            or (
                evidence.accepted_structurally
                and not authority.structurally_accepted
            )
        ):
            return HistoricalAvailabilityAudit(
                str(dataset) if isinstance(dataset, Path) else "<captured dataset>",
                str(manifest) if isinstance(manifest, Path) else "<captured manifest>",
                False,
                False,
                "AUTHORITY_REFUSED",
                ("Historical authority assessment rejected evidence",),
            )

        return HistoricalAvailabilityAudit(
            str(dataset),
            str(manifest),
            True,
            False,
            evidence.classification,
            evidence.reasons,
        )

    return HistoricalAvailabilityAudit(
        str(dataset),
        str(manifest),
        True,
        False,
        "CLAIMED_HISTORICAL_AVAILABILITY",
        ("No independently authenticated historical availability evidence supplied",),
    )


def audit_historical_availability_bytes(
    dataset_bytes: bytes,
    manifest_bytes: bytes,
    *,
    receipt_bytes: bytes | None = None,
    expected_decision_at: str | None = None,
    expected_source_id: str | None = None,
    expected_source_record_id: str | None = None,
) -> HistoricalAvailabilityAudit:
    """Audit captured evidence without filesystem reads."""
    from app.backtest.manifest import load_manifest_bytes
    from app.backtest.historical_evidence_contract import (
        validate_historical_evidence_bytes,
    )

    reasons = []

    try:
        payload = load_manifest_bytes(
            manifest_bytes, dataset_bytes
        )
    except (OSError, ValueError, TypeError, KeyError) as exc:
        reasons.append(f"manifest verification failed: {exc}")
        return HistoricalAvailabilityAudit(
            "<captured dataset>",
            "<captured manifest>",
            False,
            False,
            "INTEGRITY_REFUSED",
            tuple(reasons),
        )

    if payload.get("pit_aligned") is not True:
        reasons.append("PIT alignment not established")

    if payload.get("current_state_backfill_used") is not False:
        reasons.append(
            "current-state backfill cannot establish availability"
        )

    if reasons:
        return HistoricalAvailabilityAudit(
            "<captured dataset>",
            "<captured manifest>",
            False,
            False,
            "INTEGRITY_REFUSED",
            tuple(reasons),
        )

    if receipt_bytes is not None:
        if expected_decision_at is None:
            return HistoricalAvailabilityAudit(
                "<captured dataset>",
                "<captured manifest>",
                True,
                False,
                "EVIDENCE_REFUSED",
                ("External expected decision time is required",),
            )

        evidence = validate_historical_evidence_bytes(
            dataset_bytes,
            manifest_bytes,
            receipt_bytes,
            expected_decision_at=expected_decision_at,
            expected_source_id=expected_source_id,
            expected_source_record_id=expected_source_record_id,
        )

        # ATLAS_PHASE_2D3_REFUSAL_ONLY_AUTHORITY_GATE
        from app.backtest.historical_authority_assessment import (
            assess_historical_authority,
        )
        authority = assess_historical_authority(evidence)
        if (
            authority.authority_verified
            or authority.historical_availability_authenticated
            or (
                evidence.accepted_structurally
                and not authority.structurally_accepted
            )
        ):
            return HistoricalAvailabilityAudit(
                "<captured dataset>",
                "<captured manifest>",
                False,
                False,
                "AUTHORITY_REFUSED",
                ("Historical authority assessment rejected evidence",),
            )

        return HistoricalAvailabilityAudit(
            "<captured dataset>",
            "<captured manifest>",
            True,
            False,
            evidence.classification,
            evidence.reasons,
        )

    return HistoricalAvailabilityAudit(
        "<captured dataset>",
        "<captured manifest>",
        True,
        False,
        "CLAIMED_HISTORICAL_AVAILABILITY",
        (
            "No independently authenticated historical "
            "availability evidence supplied",
        ),
    )
