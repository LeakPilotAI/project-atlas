"""E136 D4D-1: read-only recovery assessment contracts."""

from contextlib import closing

from app.services.discord_consent_coordinator import DiscordConsentCoordinator
from app.services.discord_consent_recovery import (
    RecoveryStatus,
    assess_recovery,
)


def make_coordinator(tmp_path):
    return DiscordConsentCoordinator.create(
        tmp_path / "consent.sqlite3",
        tmp_path / "witness.sqlite3",
    )


def test_missing_consent(tmp_path):
    coordinator = make_coordinator(tmp_path)
    result = assess_recovery(coordinator, 12345)
    assert result.status is RecoveryStatus.MISSING_CONSENT


def test_matching_consent_is_diagnostic_only(tmp_path):
    coordinator = make_coordinator(tmp_path)
    coordinator.set_subscription(12345, True)
    result = assess_recovery(coordinator, 12345)
    assert result.status is RecoveryStatus.CONSISTENT
    assert result.generation == 1
    assert result.subscribed is True
    assert not hasattr(result, "authorized")


def test_revoked_consent_is_consistent_but_not_subscribed(tmp_path):
    coordinator = make_coordinator(tmp_path)
    coordinator.set_subscription(12345, True)
    coordinator.set_subscription(12345, False)
    result = assess_recovery(coordinator, 12345)
    assert result.status is RecoveryStatus.CONSISTENT
    assert result.generation == 2
    assert result.subscribed is False


def test_witness_ahead_quarantines(tmp_path):
    coordinator = make_coordinator(tmp_path)
    coordinator.set_subscription(12345, True)
    coordinator.witness.observe(
        12345, coordinator.consent.database_id, 2, False
    )
    assert assess_recovery(coordinator, 12345).status is RecoveryStatus.QUARANTINE


def test_missing_witness_quarantines(tmp_path):
    coordinator = make_coordinator(tmp_path)
    coordinator.set_subscription(12345, True)
    with closing(coordinator.witness._connect()) as db:
        db.execute(
            "DELETE FROM witness WHERE recipient_id=?", ("12345",)
        )
        db.commit()
    assert assess_recovery(coordinator, 12345).status is RecoveryStatus.QUARANTINE


def test_invalid_recipient_is_unverifiable(tmp_path):
    coordinator = make_coordinator(tmp_path)
    assert (
        assess_recovery(coordinator, 0).status
        is RecoveryStatus.UNVERIFIABLE
    )
