"""E136 Phase 2H-B: crash consistency and fail-closed regression contracts."""

import shutil

import pytest
from app.services.discord_consent_coordinator import DiscordConsentCoordinator
from app.services.discord_consent_witness import ConsentWitnessError


def provision(tmp_path):
    coordinator = DiscordConsentCoordinator.create(
        tmp_path / "consent.sqlite3",
        tmp_path / "witness.sqlite3",
    )
    return coordinator


def test_failed_witness_update_cannot_leave_committed_revocation(tmp_path, monkeypatch):
    coordinator = provision(tmp_path)
    assert coordinator.set_subscription(12345, True) == 1

    def fail_observe(*args, **kwargs):
        raise ConsentWitnessError("simulated witness write failure")

    monkeypatch.setattr(coordinator.witness, "observe", fail_observe)

    with pytest.raises(ConsentWitnessError):
        coordinator.set_subscription(12345, False)

    # A failed witness commit must not leave consent committed ahead of it.
    assert coordinator._state(12345) == (1, True)


def test_witness_ahead_of_consent_denies_authorization(tmp_path):
    coordinator = provision(tmp_path)
    assert coordinator.set_subscription(12345, True) == 1

    coordinator.witness.observe(
        12345,
        coordinator.consent.database_id,
        2,
        False,
    )

    assert not coordinator.authorized(12345, 1)

    with pytest.raises(ConsentWitnessError):
        coordinator.set_subscription(12345, True)


def test_restored_witness_denies_newer_consent(tmp_path):
    coordinator = provision(tmp_path)
    assert coordinator.set_subscription(12345, True) == 1

    witness_backup = tmp_path / "witness-backup.sqlite3"
    shutil.copy2(coordinator.witness.path, witness_backup)

    assert coordinator.set_subscription(12345, False) == 2

    shutil.copy2(witness_backup, coordinator.witness.path)

    reopened = DiscordConsentCoordinator(
        coordinator.consent.path,
        coordinator.witness.path,
    )

    assert not reopened.authorized(12345, 2)

    with pytest.raises(ConsentWitnessError):
        reopened.set_subscription(12345, True)


def test_consent_rollback_blocks_new_subscription_update(tmp_path):
    coordinator = provision(tmp_path)
    assert coordinator.set_subscription(12345, True) == 1

    consent_backup = tmp_path / "consent-backup.sqlite3"
    shutil.copy2(coordinator.consent.path, consent_backup)

    assert coordinator.set_subscription(12345, False) == 2

    shutil.copy2(consent_backup, coordinator.consent.path)

    reopened = DiscordConsentCoordinator(
        coordinator.consent.path,
        coordinator.witness.path,
    )

    assert not reopened.authorized(12345, 1)

    with pytest.raises(ConsentWitnessError):
        reopened.set_subscription(12345, True)
