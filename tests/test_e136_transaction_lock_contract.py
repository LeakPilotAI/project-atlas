"""E136 deterministic consent-lock ordering regression."""

import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor

from app.services.discord_consent_coordinator import DiscordConsentCoordinator


def test_consent_lock_precedes_witness_update(tmp_path, monkeypatch):
    consent_path = tmp_path / "consent.sqlite3"
    witness_path = tmp_path / "witness.sqlite3"

    coordinator = DiscordConsentCoordinator.create(
        consent_path,
        witness_path,
    )
    assert coordinator.set_subscription(12345, True) == 1

    writer = DiscordConsentCoordinator(consent_path, witness_path)

    reached_witness = threading.Event()
    release_witness = threading.Event()
    original_observe = writer.witness.observe

    def observed_write(*args, **kwargs):
        reached_witness.set()
        if not release_witness.wait(timeout=3):
            raise TimeoutError("witness checkpoint timed out")
        return original_observe(*args, **kwargs)

    monkeypatch.setattr(writer.witness, "observe", observed_write)

    with sqlite3.connect(consent_path, timeout=5) as blocker:
        blocker.execute("BEGIN IMMEDIATE")

        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(writer.set_subscription, 12345, False)

            try:
                # Correct locking prevents the worker from reaching
                # witness.observe while the consent writer holds its lock.
                assert not reached_witness.wait(timeout=0.5)
            finally:
                blocker.rollback()
                release_witness.set()

            assert future.result(timeout=10) == 2

    assert coordinator._state(12345) == (2, False)
    assert coordinator.witness.matches(
        12345,
        coordinator.consent.database_id,
        2,
        False,
    )
