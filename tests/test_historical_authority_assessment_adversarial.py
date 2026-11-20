import pytest

from app.backtest.historical_authority_assessment import (
    assess_historical_authority,
)
from app.backtest.historical_evidence_contract import (
    HistoricalEvidenceResult,
)


def evidence(accepted, authenticated, classification):
    return HistoricalEvidenceResult(
        accepted, authenticated, classification, ()
    )


@pytest.mark.parametrize("accepted,authenticated,classification", [
    (True, True, "STRUCTURALLY_CONSISTENT_UNAUTHENTICATED"),
    (True, True, "AUTHENTICATED"),
    (False, True, "EVIDENCE_REFUSED"),
    (True, False, "AUTHENTICATED"),
    (True, False, "AUTHORITY_VERIFIED"),
    (False, False, "AUTHENTICATED"),
])
def test_forged_or_contradictory_states_never_authenticate(
    accepted, authenticated, classification
):
    result = assess_historical_authority(
        evidence(accepted, authenticated, classification),
        claimed_authority="trusted:archive",
    )

    assert result.historical_availability_authenticated is False
    assert result.authority_verified is False
    assert result.classification in (
        "AUTHORITY_REFUSED",
        "EVIDENCE_REFUSED",
    )


@pytest.mark.parametrize("claim", [
    "",
    "trusted:archive",
    "SIGNED",
    "VERIFIED",
    "2020-01-01T00:00:00Z",
    "a" * 4096,
    None,
    123,
    True,
    {"verified": True},
])
def test_untrusted_authority_claims_never_grant_trust(claim):
    result = assess_historical_authority(
        evidence(
            True,
            False,
            "STRUCTURALLY_CONSISTENT_UNAUTHENTICATED",
        ),
        claimed_authority=claim,
    )

    assert result.historical_availability_authenticated is False
    assert result.authority_verified is False
    assert result.classification in (
        "AUTHORITY_UNVERIFIED",
        "AUTHORITY_NOT_PROVIDED",
    )


@pytest.mark.parametrize("invalid", [
    None,
    {},
    "AUTHENTICATED",
    True,
    123,
])
def test_invalid_evidence_inputs_refused(invalid):
    result = assess_historical_authority(invalid)

    assert result.classification == "AUTHORITY_REFUSED"
    assert result.historical_availability_authenticated is False
    assert result.authority_verified is False
