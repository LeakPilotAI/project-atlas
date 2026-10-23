from app.backtest.historical_authority_assessment import (
    assess_historical_authority,
)
from app.backtest.historical_evidence_contract import (
    HistoricalEvidenceResult,
)


def evidence(accepted=True, authenticated=False,
             classification="STRUCTURALLY_CONSISTENT_UNAUTHENTICATED"):
    return HistoricalEvidenceResult(
        accepted,
        authenticated,
        classification,
        (),
    )


def test_consistent_evidence_remains_unauthenticated():
    result = assess_historical_authority(evidence())
    assert result.structurally_accepted
    assert not result.authority_verified
    assert not result.historical_availability_authenticated
    assert result.classification == "AUTHORITY_NOT_PROVIDED"


def test_claimed_authority_cannot_grant_authentication():
    result = assess_historical_authority(
        evidence(),
        claimed_authority="claimed:trusted-archive",
    )
    assert result.classification == "AUTHORITY_UNVERIFIED"
    assert not result.authority_verified
    assert not result.historical_availability_authenticated


def test_refused_evidence_stays_refused():
    result = assess_historical_authority(
        evidence(False, False, "EVIDENCE_REFUSED"),
    )
    assert result.classification == "EVIDENCE_REFUSED"
    assert not result.structurally_accepted


def test_upstream_authentication_claim_is_refused():
    result = assess_historical_authority(
        evidence(True, True),
    )
    assert result.classification == "AUTHORITY_REFUSED"
    assert not result.historical_availability_authenticated


def test_unexpected_classification_refused():
    result = assess_historical_authority(
        evidence(True, False, "AUTHENTICATED"),
    )
    assert result.classification == "AUTHORITY_REFUSED"


def test_invalid_input_refused():
    result = assess_historical_authority(None)
    assert result.classification == "AUTHORITY_REFUSED"
    assert not result.authority_verified
