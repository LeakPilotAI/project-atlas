"""E136 D4D-2A: recovery assessor failure-injection contracts."""

import sqlite3
from contextlib import closing
from unittest.mock import patch

import pytest
from app.services.discord_consent_coordinator import DiscordConsentCoordinator
from app.services.discord_consent_recovery import RecoveryStatus, assess_recovery


def make_coordinator(tmp_path):
    coordinator = DiscordConsentCoordinator.create(
        tmp_path / "consent.sqlite3",
        tmp_path / "witness.sqlite3",
    )
    assert coordinator.set_subscription(12345, True) == 1
    return coordinator


@pytest.mark.parametrize(
    ("failure", "expected"),
    [
        (sqlite3.DatabaseError("corrupt database"), RecoveryStatus.UNVERIFIABLE),
        (OSError("database unavailable"), RecoveryStatus.UNVERIFIABLE),
        (ValueError("invalid evidence"), RecoveryStatus.UNVERIFIABLE),
    ],
)
def test_consent_read_failures_are_unverifiable(tmp_path, failure, expected):
    coordinator = make_coordinator(tmp_path)
    with patch.object(coordinator, "_state", side_effect=failure):
        result = assess_recovery(coordinator, 12345)
    assert result.status is expected
    assert result.generation is None
    assert result.subscribed is None


def test_witness_read_failure_never_reports_consistent(tmp_path):
    coordinator = make_coordinator(tmp_path)
    with patch.object(
        coordinator.witness,
        "matches",
        side_effect=sqlite3.DatabaseError("witness unreadable"),
    ):
        result = assess_recovery(coordinator, 12345)
    assert result.status is RecoveryStatus.UNVERIFIABLE


def test_witness_identity_failure_never_reports_consistent(tmp_path):
    coordinator = make_coordinator(tmp_path)
    with patch.object(coordinator.witness, "matches", return_value=False):
        result = assess_recovery(coordinator, 12345)
    assert result.status is RecoveryStatus.QUARANTINE


def test_assessment_does_not_mutate_consent_or_witness(tmp_path):
    coordinator = make_coordinator(tmp_path)

    with closing(coordinator.consent._connect()) as db:
        consent_before = db.execute(
            "SELECT generation, subscribed FROM consent_generations "
            "WHERE recipient_id=?",
            ("12345",),
        ).fetchone()
        consent_before = tuple(consent_before)

    with closing(coordinator.witness._connect()) as db:
        witness_before = db.execute(
            "SELECT * FROM witness WHERE recipient_id=?",
            ("12345",),
        ).fetchone()
        witness_before = tuple(witness_before)

    result = assess_recovery(coordinator, 12345)
    assert result.status is RecoveryStatus.CONSISTENT

    with closing(coordinator.consent._connect()) as db:
        consent_after = db.execute(
            "SELECT generation, subscribed FROM consent_generations "
            "WHERE recipient_id=?",
            ("12345",),
        ).fetchone()
        consent_after = tuple(consent_after)

    with closing(coordinator.witness._connect()) as db:
        witness_after = db.execute(
            "SELECT * FROM witness WHERE recipient_id=?",
            ("12345",),
        ).fetchone()
        witness_after = tuple(witness_after)

    assert consent_before == consent_after
    assert witness_before == witness_after
