"""E136 D4D-2B: deterministic recovery snapshot race contract."""

from unittest.mock import patch

import pytest
from app.services.discord_consent_coordinator import DiscordConsentCoordinator
from app.services.discord_consent_recovery import (
    RecoveryStatus,
    assess_recovery,
)


@pytest.mark.xfail(
    strict=True,
    reason="Two separate reads do not provide an atomic recovery snapshot",
)
def test_revocation_during_assessment_cannot_return_stale_consistent(tmp_path):
    coordinator = DiscordConsentCoordinator.create(
        tmp_path / "consent.sqlite3",
        tmp_path / "witness.sqlite3",
    )
    recipient = 12345
    assert coordinator.set_subscription(recipient, True) == 1

    original_matches = coordinator.witness.matches
    revoked = False

    def matches_then_revoke(*args, **kwargs):
        nonlocal revoked
        matched = original_matches(*args, **kwargs)
        if matched and not revoked:
            revoked = True
            assert coordinator.set_subscription(recipient, False) == 2
        return matched

    with patch.object(
        coordinator.witness,
        "matches",
        side_effect=matches_then_revoke,
    ):
        assessment = assess_recovery(coordinator, recipient)

    assert revoked
    assert coordinator.authorized(recipient, 1) is False

    # A stale positive result would be unsafe as a delivery decision.
    assert not (
        assessment.status is RecoveryStatus.CONSISTENT
        and assessment.subscribed is True
    )
