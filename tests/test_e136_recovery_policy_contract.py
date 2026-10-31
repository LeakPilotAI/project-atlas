"""E136 Phase 2H-D3: fail-closed recovery policy contracts."""

import pytest
from app.services.discord_consent_coordinator import DiscordConsentCoordinator
from app.services.discord_consent_witness import ConsentWitnessError


@pytest.mark.parametrize(
    ("current", "witness_generation", "witness_status"),
    [
        (True, 2, False),
        (False, 3, True),
    ],
)
def test_witness_ahead_blocks_authorization_and_updates(
    tmp_path, current, witness_generation, witness_status
):
    coordinator = DiscordConsentCoordinator.create(
        tmp_path / "consent.sqlite3",
        tmp_path / "witness.sqlite3",
    )
    assert coordinator.set_subscription(12345, True) == 1

    if not current:
        assert coordinator.set_subscription(12345, False) == 2

    coordinator.witness.observe(
        12345,
        coordinator.consent.database_id,
        witness_generation,
        witness_status,
    )

    assert not coordinator.authorized(12345, 1)
    assert not coordinator.authorized(12345, witness_generation)

    with pytest.raises(ConsentWitnessError):
        coordinator.set_subscription(12345, True)


def test_missing_witness_record_never_authorizes(tmp_path):
    coordinator = DiscordConsentCoordinator.create(
        tmp_path / "consent.sqlite3",
        tmp_path / "witness.sqlite3",
    )
    assert coordinator.set_subscription(12345, True) == 1

    with coordinator.witness._connect() as db:
        db.execute("DELETE FROM witness WHERE recipient_id=?", ("12345",))
        db.commit()

    assert not coordinator.authorized(12345, 1)

    with pytest.raises(ConsentWitnessError):
        coordinator.set_subscription(12345, True)
