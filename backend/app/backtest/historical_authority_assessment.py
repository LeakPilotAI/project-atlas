"""Offline refusal-only historical authority assessment.

Structural consistency is not independently witnessed publication.
No authentication or trading authority can be granted here.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.backtest.historical_evidence_contract import HistoricalEvidenceResult


@dataclass(frozen=True)
class HistoricalAuthorityAssessment:
    structurally_accepted: bool
    historical_availability_authenticated: bool
    authority_verified: bool
    classification: str
    reasons: tuple[str, ...]


def assess_historical_authority(
    evidence: HistoricalEvidenceResult,
    *,
    claimed_authority: str | None = None,
) -> HistoricalAuthorityAssessment:
    """Classify supplied evidence without granting external trust."""

    if not isinstance(evidence, HistoricalEvidenceResult):
        return HistoricalAuthorityAssessment(
            False, False, False, "AUTHORITY_REFUSED",
            ("Invalid structural evidence result",),
        )

    if evidence.historical_availability_authenticated:
        return HistoricalAuthorityAssessment(
            False, False, False, "AUTHORITY_REFUSED",
            ("Unverified upstream authentication claim",),
        )

    if not evidence.accepted_structurally:
        return HistoricalAuthorityAssessment(
            False, False, False, "EVIDENCE_REFUSED",
            ("Structural evidence verification failed",),
        )

    if evidence.classification != (
        "STRUCTURALLY_CONSISTENT_UNAUTHENTICATED"
    ):
        return HistoricalAuthorityAssessment(
            False, False, False, "AUTHORITY_REFUSED",
            ("Unexpected evidence classification",),
        )

    if claimed_authority is not None:
        return HistoricalAuthorityAssessment(
            True, False, False, "AUTHORITY_UNVERIFIED",
            ("Caller-supplied authority claim is not independent proof",),
        )

    return HistoricalAuthorityAssessment(
        True, False, False, "AUTHORITY_NOT_PROVIDED",
        ("No independent historical publication authority supplied",),
    )
