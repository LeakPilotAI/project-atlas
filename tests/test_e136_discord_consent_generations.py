"""Isolated regression tests for E136 consent generations."""

import sqlite3

import pytest
from app.services.discord_consent_generations import (
    ConsentStateError,
    DiscordConsentGenerations,
)


def test_subscribe_revoke_resubscribe(tmp_path):
    store = DiscordConsentGenerations.create(tmp_path / "consent.sqlite3")

    assert store.set_subscription(12345, True) == 1
    assert store.authorized(12345, 1)

    assert store.set_subscription(12345, False) == 2
    assert not store.authorized(12345, 1)
    assert not store.authorized(12345, 2)

    assert store.set_subscription(12345, True) == 3
    assert store.authorized(12345, 3)
    assert not store.authorized(12345, 1)


def test_noop_does_not_increment_generation(tmp_path):
    store = DiscordConsentGenerations.create(tmp_path / "consent.sqlite3")

    assert store.set_subscription(12345, True) == 1
    assert store.set_subscription(12345, True) == 1
    assert store.set_subscription(12345, False) == 2
    assert store.set_subscription(12345, False) == 2


def test_restart_preserves_revocation(tmp_path):
    path = tmp_path / "consent.sqlite3"
    store = DiscordConsentGenerations.create(path)

    store.set_subscription(12345, True)
    store.set_subscription(12345, False)

    reopened = DiscordConsentGenerations(path)

    assert not reopened.authorized(12345, 1)
    assert reopened.set_subscription(12345, True) == 3
    assert reopened.authorized(12345, 3)


def test_recipient_independence(tmp_path):
    store = DiscordConsentGenerations.create(tmp_path / "consent.sqlite3")

    store.set_subscription(12345, True)
    store.set_subscription(67890, True)
    store.set_subscription(67890, False)

    assert store.authorized(12345, 1)
    assert not store.authorized(67890, 1)


def test_unknown_and_invalid_generations_fail_closed(tmp_path):
    store = DiscordConsentGenerations.create(tmp_path / "consent.sqlite3")

    assert not store.authorized(12345, 1)

    store.set_subscription(12345, True)

    for generation in (0, -1, True, "1", None):
        assert not store.authorized(12345, generation)


def test_database_constraint_rejects_invalid_generation(tmp_path):
    path = tmp_path / "consent.sqlite3"
    store = DiscordConsentGenerations.create(path)
    store.set_subscription(12345, True)

    with sqlite3.connect(path) as db, pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "UPDATE consent_generations "
            "SET generation=0 WHERE recipient_id='12345'"
        )

    assert store.authorized(12345, 1)


def test_invalid_recipient_ids_rejected(tmp_path):
    store = DiscordConsentGenerations.create(tmp_path / "consent.sqlite3")

    for recipient_id in (0, -1, True, "12345", 1 << 64):
        with pytest.raises(ValueError):
            store.set_subscription(recipient_id, True)


def test_missing_parent_directory_rejected(tmp_path):
    with pytest.raises(ConsentStateError):
        DiscordConsentGenerations(tmp_path / "missing" / "consent.sqlite3")


def test_concurrent_subscription_transitions(tmp_path):
    """Concurrent writers must serialize without losing transitions."""
    from concurrent.futures import ThreadPoolExecutor

    path = tmp_path / "consent.sqlite3"
    store = DiscordConsentGenerations.create(path)
    store.set_subscription(12345, True)

    def toggle(value):
        return store.set_subscription(12345, value)

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(toggle, [False] * 8))

    assert set(results) == {2}
    assert not store.authorized(12345, 1)
    assert not store.authorized(12345, 2)


def test_missing_database_after_initialization_fails_closed(tmp_path):
    """Removing consent evidence must never authorize delivery."""
    path = tmp_path / "consent.sqlite3"
    store = DiscordConsentGenerations.create(path)
    store.set_subscription(12345, True)

    path.unlink()

    assert not store.authorized(12345, 1)


def test_generation_overflow_must_not_wrap_or_authorize(tmp_path):
    """An exhausted generation must not roll back to an older one."""
    path = tmp_path / "consent.sqlite3"
    store = DiscordConsentGenerations.create(path)
    store.set_subscription(12345, True)

    with sqlite3.connect(path) as db:
        db.execute(
            "UPDATE consent_generations SET generation=? "
            "WHERE recipient_id='12345'",
            (9223372036854775807,),
        )

    with pytest.raises((OverflowError, ConsentStateError, sqlite3.Error)):
        store.set_subscription(12345, False)

    assert not store.authorized(12345, 1)


def test_explicit_provisioning_required(tmp_path):
    path = tmp_path / "consent.sqlite3"

    with pytest.raises(ConsentStateError, match="explicitly provisioned"):
        DiscordConsentGenerations(path)

    assert not path.exists()


def test_duplicate_provisioning_rejected(tmp_path):
    path = tmp_path / "consent.sqlite3"
    first = DiscordConsentGenerations.create(path)

    with pytest.raises(ConsentStateError, match="already exists"):
        DiscordConsentGenerations.create(path)

    assert DiscordConsentGenerations(path).database_id == first.database_id


def test_database_identity_persists_across_restart(tmp_path):
    path = tmp_path / "consent.sqlite3"
    first = DiscordConsentGenerations.create(path)
    first.set_subscription(12345, True)

    reopened = DiscordConsentGenerations(path)

    assert reopened.database_id == first.database_id
    assert reopened.authorized(12345, 1)


def test_reprovisioning_changes_database_identity(tmp_path):
    path = tmp_path / "consent.sqlite3"
    first = DiscordConsentGenerations.create(path)
    original_identity = first.database_id
    first.set_subscription(12345, True)

    path.unlink()

    with pytest.raises(ConsentStateError):
        DiscordConsentGenerations(path)

    replacement = DiscordConsentGenerations.create(path)

    assert replacement.database_id != original_identity
    assert not replacement.authorized(12345, 1)


def test_invalid_database_identity_rejected(tmp_path):
    path = tmp_path / "consent.sqlite3"
    DiscordConsentGenerations.create(path)

    with sqlite3.connect(path) as db:
        db.execute(
            "UPDATE consent_metadata SET value=? WHERE key='database_id'",
            ("not-a-valid-uuid",),
        )

    with pytest.raises(ConsentStateError, match="invalid consent database"):
        DiscordConsentGenerations(path)


def test_existing_instance_rejects_replaced_database(tmp_path):
    """An existing consent store must reject a new database at its old path."""
    path = tmp_path / "consent.sqlite3"
    original = DiscordConsentGenerations.create(path)
    original.set_subscription(12345, True)
    original_identity = original.database_id

    path.unlink()

    replacement = DiscordConsentGenerations.create(path)
    assert replacement.database_id != original_identity
    assert replacement.set_subscription(12345, True) == 1

    assert not original.authorized(12345, 1)

    with pytest.raises(ConsentStateError):
        original.set_subscription(12345, True)
