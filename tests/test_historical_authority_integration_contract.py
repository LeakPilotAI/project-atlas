"""Refusal-only historical authority integration contracts."""

from app.backtest.historical_authority_assessment import (
    assess_historical_authority,
)
from app.backtest.historical_evidence_contract import (
    HistoricalEvidenceResult,
)


def test_structural_consistency_does_not_grant_authority():
    evidence = HistoricalEvidenceResult(
        True,
        False,
        "STRUCTURALLY_CONSISTENT_UNAUTHENTICATED",
        (),
    )

    assessment = assess_historical_authority(evidence)

    assert assessment.structurally_accepted is True
    assert assessment.historical_availability_authenticated is False
    assert assessment.authority_verified is False
    assert assessment.classification == "AUTHORITY_NOT_PROVIDED"


def test_external_claim_does_not_grant_authority():
    evidence = HistoricalEvidenceResult(
        True,
        False,
        "STRUCTURALLY_CONSISTENT_UNAUTHENTICATED",
        (),
    )

    assessment = assess_historical_authority(
        evidence,
        claimed_authority="trusted:archive",
    )

    assert assessment.historical_availability_authenticated is False
    assert assessment.authority_verified is False
    assert assessment.classification == "AUTHORITY_UNVERIFIED"


def test_refused_evidence_remains_refused():
    evidence = HistoricalEvidenceResult(
        False,
        False,
        "EVIDENCE_REFUSED",
        ("Invalid receipt",),
    )

    assessment = assess_historical_authority(evidence)

    assert assessment.structurally_accepted is False
    assert assessment.historical_availability_authenticated is False
    assert assessment.authority_verified is False
    assert assessment.classification == "EVIDENCE_REFUSED"
