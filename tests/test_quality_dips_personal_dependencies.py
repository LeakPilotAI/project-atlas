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
