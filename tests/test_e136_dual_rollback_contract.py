"""E136 Phase 2H-D2: coordinated historical rollback contract."""

import shutil

import pytest
from app.services.discord_consent_coordinator import DiscordConsentCoordinator


@pytest.mark.xfail(
    strict=True,
    reason="Matching historical copies of both databases can restore revoked consent",
)
def test_dual_database_rollback_cannot_reauthorize_revoked_consent(tmp_path):
    consent_path = tmp_path / "consent.sqlite3"
    witness_path = tmp_path / "witness.sqlite3"
    consent_backup = tmp_path / "consent-backup.sqlite3"
    witness_backup = tmp_path / "witness-backup.sqlite3"

    coordinator = DiscordConsentCoordinator.create(
        consent_path,
        witness_path,
    )

    assert coordinator.set_subscription(12345, True) == 1

    # Back up the matching subscribed state while both databases
    # are closed and no transition is running.
    shutil.copy2(consent_path, consent_backup)
    shutil.copy2(witness_path, witness_backup)

    assert coordinator.set_subscription(12345, False) == 2
    assert not coordinator.authorized(12345, 1)

    # Simulate coordinated restoration of historical files.
    shutil.copy2(consent_backup, consent_path)
    shutil.copy2(witness_backup, witness_path)

    reopened = DiscordConsentCoordinator(
        consent_path,
        witness_path,
    )

    # Required future security property:
    # historical matching snapshots must not restore authorization.
    assert not reopened.authorized(12345, 1)
