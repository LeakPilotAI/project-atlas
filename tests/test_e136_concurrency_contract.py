"""E136 lock-compatible concurrency regression contracts."""

import threading
from concurrent.futures import ThreadPoolExecutor

from app.services.discord_consent_coordinator import DiscordConsentCoordinator


def test_competing_coordinators_converge_on_one_transition(tmp_path):
    consent_path = tmp_path / "consent.sqlite3"
    witness_path = tmp_path / "witness.sqlite3"

    first = DiscordConsentCoordinator.create(consent_path, witness_path)
    second = DiscordConsentCoordinator(consent_path, witness_path)

    assert first.set_subscription(12345, True) == 1

    start = threading.Event()

    def update(coordinator):
        if not start.wait(timeout=10):
            raise TimeoutError("concurrent test start timed out")
        return coordinator.set_subscription(12345, False)

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(update, first),
            pool.submit(update, second),
        ]
        start.set()
        results = [future.result(timeout=15) for future in futures]

    assert results == [2, 2]
    assert first._state(12345) == (2, False)
    assert not first.authorized(12345, 1)
    assert not first.authorized(12345, 2)
    assert first.witness.matches(
        12345,
        first.consent.database_id,
        2,
        False,
    )


def test_sequential_duplicate_transition_is_idempotent(tmp_path):
    coordinator = DiscordConsentCoordinator.create(
        tmp_path / "consent.sqlite3",
        tmp_path / "witness.sqlite3",
    )

    assert coordinator.set_subscription(12345, True) == 1
    assert coordinator.set_subscription(12345, True) == 1

    assert coordinator.set_subscription(12345, False) == 2
    assert coordinator.set_subscription(12345, False) == 2

    assert not coordinator.authorized(12345, 1)
    assert not coordinator.authorized(12345, 2)
    assert coordinator.witness.matches(
        12345,
        coordinator.consent.database_id,
        2,
        False,
    )
