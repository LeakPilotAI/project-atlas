"""Local coordination/clock source tests, not independent authority acceptance."""

from types import SimpleNamespace

import pytest
from app.services.quality_dips_personal_dependencies import (
    PersonalClockContinuity,
    PersonalSessionReservations,
)
from test_quality_dips_autonomous_paper import setup


@pytest.mark.parametrize("phase", [None, "after_pending", "after_ack"])
def test_session_reservation_durable_single_use_restart(tmp_path, phase):
    n = setup(tmp_path)
    with n.ledger.connect() as db:
        db.execute(
            "CREATE TABLE personal_sessions(id TEXT PRIMARY KEY,body TEXT,state TEXT)"
        )
    request = {"grant": {"session_id": "SYNTHETIC_PERSONAL_SESSION"}}

    def fault(at):
        if at == phase:
            raise OSError("SYNTHETIC_RESERVATION_CRASH")

    authorization = SimpleNamespace(verify=lambda request: True)
    reservation = PersonalSessionReservations(
        ledger=n.ledger, authorization=authorization, fault=fault
    )
    if phase:
        with pytest.raises(OSError):
            reservation.reserve(request)
    else:
        receipt = reservation.reserve(request)
        assert reservation.verify(request, receipt)
    restarted = PersonalSessionReservations(
        ledger=n.ledger, authorization=authorization
    )
    with pytest.raises(ValueError, match="REPLAY_OR_UNCERTAIN"):
        restarted.reserve(request)


@pytest.mark.parametrize(
    "damage", [None, "revoked", "boot", "wall", "expired", "monotonic"]
)
def test_accepted_local_anchor_continuity(damage):
    anchor = {
        "schema": "QD_PERSONAL_UTC_ANCHOR_V1",
        "utc": 1000,
        "monotonic_ns": 10**9,
        "boot_id": "SYNTHETIC_BOOT",
        "source": "SYNTHETIC_LOCAL_CLOCK",
        "expires_at": 1030,
        "uncertainty_ms": 100,
    }
    mono, wall, boot = [2 * 10**9], [1001], ["SYNTHETIC_BOOT"]
    clock = PersonalClockContinuity(
        anchor=anchor,
        authority=SimpleNamespace(verify=lambda a: damage != "revoked"),
        monotonic_ns=lambda: mono[0],
        wall_utc=lambda: wall[0],
        boot_identity=lambda: boot[0],
    )
    if damage == "boot":
        boot[0] = "FOREIGN_BOOT"
    if damage == "wall":
        wall[0] = 2000
    if damage == "expired":
        mono[0], wall[0] = 50 * 10**9, 1049
    if damage == "monotonic":
        mono[0] = 0
    if damage:
        with pytest.raises(ValueError):
            clock.sample()
    else:
        sample = clock.sample()
        assert sample["utc"] == 1001 and clock.verify(sample)


@pytest.mark.parametrize('damage', ['before-anchor', 'extra-field', 'boolean-uncertainty'])
def test_clock_sample_cannot_precede_anchor_or_change_versioned_shape(damage):
    anchor = {'schema': 'QD_PERSONAL_UTC_ANCHOR_V1', 'utc': 1000, 'monotonic_ns': 10**9,
              'boot_id': 'SYNTHETIC_BOOT', 'source': 'SYNTHETIC_CLOCK', 'expires_at': 1030,
              'uncertainty_ms': 0}
    clock = PersonalClockContinuity(anchor=anchor, authority=SimpleNamespace(verify=lambda a: True),
                                   monotonic_ns=lambda: 10**9, wall_utc=lambda: 1000,
                                   boot_identity=lambda: 'SYNTHETIC_BOOT')
    sample = clock.sample()
    if damage == 'before-anchor':
        sample.update(monotonic_ns=0, utc=999)
    elif damage == 'extra-field':
        sample['foreign_clock_authority'] = True
    else:
        sample['uncertainty_ms'] = False
    assert not clock.verify(sample)


@pytest.mark.parametrize("uncertainty", [-1, 0, 999, 1000, 1001, True, 1.0])
def test_clock_uncertainty_exact_integer_boundary(uncertainty):
    """Synthetic validation only: a small offset cannot supply this declaration."""
    anchor = {
        "schema": "QD_PERSONAL_UTC_ANCHOR_V1",
        "utc": 1000,
        "monotonic_ns": 10**9,
        "boot_id": "SYNTHETIC_BOOT",
        "source": "SYNTHETIC_CLOCK",
        "expires_at": 1030,
        "uncertainty_ms": uncertainty,
    }
    clock = PersonalClockContinuity(
        anchor=anchor,
        authority=SimpleNamespace(verify=lambda a: True),
        monotonic_ns=lambda: 10**9,
        wall_utc=lambda: 1000,
        boot_identity=lambda: "SYNTHETIC_BOOT",
    )
    if type(uncertainty) is int and 0 <= uncertainty <= 1000:
        sample = clock.sample()
        assert sample["uncertainty_ms"] == uncertainty
        assert clock.verify(sample)
    else:
        with pytest.raises(ValueError, match="PERSONAL_ACCEPTED_CLOCK_ANCHOR_REQUIRED"):
            clock.sample()


def test_zero_uncertainty_is_not_a_substitute_for_anchor_authentication():
    anchor = {
        "schema": "QD_PERSONAL_UTC_ANCHOR_V1",
        "utc": 1000,
        "monotonic_ns": 10**9,
        "boot_id": "SYNTHETIC_BOOT",
        "source": "SYNTHETIC_CLOCK",
        "expires_at": 1030,
        "uncertainty_ms": 0,
    }
    clock = PersonalClockContinuity(
        anchor=anchor,
        authority=SimpleNamespace(verify=lambda a: False),
        monotonic_ns=lambda: 10**9,
        wall_utc=lambda: 1000,
        boot_identity=lambda: "SYNTHETIC_BOOT",
    )
    with pytest.raises(ValueError, match="PERSONAL_ACCEPTED_CLOCK_ANCHOR_REQUIRED"):
        clock.sample()
