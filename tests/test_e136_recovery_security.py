"""E136 Phase 2G: independent recovery witness security contracts."""

import shutil

import pytest
from app.services.discord_consent_generations import DiscordConsentGenerations
from app.services.discord_consent_witness import (
    ConsentWitnessError,
    DiscordConsentWitness,
)


def test_restored_consent_rejected_by_current_witness(tmp_path):
    consent_path = tmp_path / "consent.sqlite3"
    witness_path = tmp_path / "witness.sqlite3"
    backup_path = tmp_path / "consent-backup.sqlite3"

    consent = DiscordConsentGenerations.create(consent_path)
    witness = DiscordConsentWitness.create(witness_path)

    generation = consent.set_subscription(12345, True)
    witness.observe(12345, consent.database_id, generation, True)
    shutil.copy2(consent_path, backup_path)

    generation = consent.set_subscription(12345, False)
    witness.observe(12345, consent.database_id, generation, False)

    shutil.copy2(backup_path, consent_path)

    restored = DiscordConsentGenerations(consent_path)

    assert restored.authorized(12345, 1)
    assert not witness.matches(12345, restored.database_id, 1, True)


def test_missing_witness_record_denies_match(tmp_path):
    witness = DiscordConsentWitness.create(tmp_path / "witness.sqlite3")

    assert not witness.matches(12345, "a" * 32, 1, True)


def test_witness_database_replacement_does_not_inherit_records(tmp_path):
    path = tmp_path / "witness.sqlite3"
    witness = DiscordConsentWitness.create(path)
    witness.observe(12345, "a" * 32, 2, False)

    path.unlink()

    replacement = DiscordConsentWitness.create(path)

    assert not replacement.matches(12345, "a" * 32, 2, False)


def test_existing_witness_rejects_replacement_with_same_records(tmp_path):
    path = tmp_path / "witness.sqlite3"
    original = DiscordConsentWitness.create(path)
    original.observe(12345, "a" * 32, 2, False)

    path.unlink()
    replacement = DiscordConsentWitness.create(path)
    replacement.observe(12345, "a" * 32, 2, False)

    assert not original.matches(12345, "a" * 32, 2, False)
    with pytest.raises(ConsentWitnessError):
        original.observe(12345, "a" * 32, 2, False)
