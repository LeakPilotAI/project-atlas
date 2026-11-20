"""E136 Phase 2H: coordinated consent authorization security contract."""

import shutil

from app.services.discord_consent_coordinator import DiscordConsentCoordinator


def test_coordinator_revocation_survives_consent_database_rollback(tmp_path):
    consent_path = tmp_path / "consent.sqlite3"
    witness_path = tmp_path / "witness.sqlite3"
    backup_path = tmp_path / "consent-backup.sqlite3"

    coordinator = DiscordConsentCoordinator.create(
        consent_path,
        witness_path,
    )

    generation = coordinator.set_subscription(12345, True)
    assert generation == 1
    assert coordinator.authorized(12345, generation)

    shutil.copy2(consent_path, backup_path)

    generation = coordinator.set_subscription(12345, False)
    assert generation == 2
    assert not coordinator.authorized(12345, 1)

    shutil.copy2(backup_path, consent_path)

    reopened = DiscordConsentCoordinator(
        consent_path,
        witness_path,
    )

    assert not reopened.authorized(12345, 1)


def test_coordinator_missing_witness_denies_authorization(tmp_path):
    consent_path = tmp_path / "consent.sqlite3"
    witness_path = tmp_path / "witness.sqlite3"

    coordinator = DiscordConsentCoordinator.create(
        consent_path,
        witness_path,
    )

    generation = coordinator.set_subscription(12345, True)
    assert coordinator.authorized(12345, generation)

    witness_path.unlink()

    assert not coordinator.authorized(12345, generation)
    assert not witness_path.exists()
