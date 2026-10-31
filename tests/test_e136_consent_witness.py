"""Isolated E136 witness behavior."""

import pytest
from app.services.discord_consent_witness import (
    ConsentWitnessError,
    DiscordConsentWitness,
)


def test_explicit_provisioning(tmp_path):
    path = tmp_path / "witness.sqlite3"
    with pytest.raises(ConsentWitnessError):
        DiscordConsentWitness(path)
    assert not path.exists()


def test_monotonic_observations_survive_restart(tmp_path):
    path = tmp_path / "witness.sqlite3"
    witness = DiscordConsentWitness.create(path)
    identity = "a" * 32

    witness.observe(12345, identity, 1, True)
    witness.observe(12345, identity, 1, True)
    witness.observe(12345, identity, 2, False)

    reopened = DiscordConsentWitness(path)
    assert reopened.matches(12345, identity, 2, False)
    assert not reopened.matches(12345, identity, 1, True)


def test_generation_rollback_rejected(tmp_path):
    witness = DiscordConsentWitness.create(tmp_path / "witness.sqlite3")
    identity = "a" * 32

    witness.observe(12345, identity, 2, False)

    with pytest.raises(ConsentWitnessError, match="rollback"):
        witness.observe(12345, identity, 1, True)


def test_conflicting_same_generation_rejected(tmp_path):
    witness = DiscordConsentWitness.create(tmp_path / "witness.sqlite3")
    identity = "a" * 32

    witness.observe(12345, identity, 1, True)

    with pytest.raises(ConsentWitnessError, match="conflicting"):
        witness.observe(12345, identity, 1, False)


def test_database_identity_change_rejected(tmp_path):
    witness = DiscordConsentWitness.create(tmp_path / "witness.sqlite3")

    witness.observe(12345, "a" * 32, 1, True)

    with pytest.raises(ConsentWitnessError, match="identity"):
        witness.observe(12345, "b" * 32, 2, False)


def test_missing_witness_fails_closed(tmp_path):
    path = tmp_path / "witness.sqlite3"
    witness = DiscordConsentWitness.create(path)
    witness.observe(12345, "a" * 32, 1, True)

    path.unlink()

    assert not witness.matches(12345, "a" * 32, 1, True)
    assert not path.exists()
