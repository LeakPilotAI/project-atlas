"""E136 Phase 2F: expected recovery behavior, isolated from production."""

import shutil

import pytest
from app.services.discord_consent_generations import DiscordConsentGenerations


@pytest.mark.xfail(
    strict=True,
    reason="E136 independent rollback witness not yet implemented",
)
def test_restored_consent_cannot_reauthorize_revoked_generation(tmp_path):
    database = tmp_path / "consent.sqlite3"
    backup = tmp_path / "backup.sqlite3"

    store = DiscordConsentGenerations.create(database)

    assert store.set_subscription(12345, True) == 1
    shutil.copy2(database, backup)

    assert store.set_subscription(12345, False) == 2
    assert not store.authorized(12345, 1)

    shutil.copy2(backup, database)

    restored = DiscordConsentGenerations(database)

    assert not restored.authorized(12345, 1)


def test_missing_consent_database_never_recreates_it(tmp_path):
    database = tmp_path / "consent.sqlite3"

    store = DiscordConsentGenerations.create(database)
    store.set_subscription(12345, True)

    database.unlink()

    assert not store.authorized(12345, 1)
    assert not database.exists()
