"""Independent fail-closed delivery-admission tests for E136."""

import sqlite3
import threading
import time

from app.services.discord_consent_coordinator import DiscordConsentCoordinator
from app.services.discord_consent_delivery_adapter import DiscordConsentDeliveryAdapter
from app.services.discord_consent_recovery import RecoveryStatus, assess_recovery


def _make_adapter(tmp_path):
    consent_path = tmp_path / "consent.sqlite3"
    witness_path = tmp_path / "witness.sqlite3"
    coordinator = DiscordConsentCoordinator.create(consent_path, witness_path)
    adapter = DiscordConsentDeliveryAdapter(coordinator, tmp_path / "delivery.sqlite3")
    return coordinator, adapter


def test_missing_consent_evidence_rejected(tmp_path):
    _, adapter = _make_adapter(tmp_path)

    assert not adapter.enqueue("evt-missing-1", 12345, generation=None, database_id=None)
    assert not adapter.enqueue("evt-missing-2", 12345, generation=1, database_id=None)


def test_revoked_generation_fails_closed_for_dispatch(tmp_path):
    coordinator, adapter = _make_adapter(tmp_path)
    coordinator.set_subscription(12345, True)

    assert adapter.enqueue(
        "evt-revoked",
        12345,
        generation=1,
        database_id=coordinator.consent.database_id,
    )

    coordinator.set_subscription(12345, False)

    assert not adapter.dispatch_due("evt-revoked", 12345, lambda: True)

    with sqlite3.connect(adapter.path) as db:
        status = db.execute(
            "SELECT status FROM delivery_queue WHERE event_id=?",
            ("evt-revoked",),
        ).fetchone()[0]
    assert status == "denied"


def test_mismatched_database_identity_rejected(tmp_path):
    coordinator, adapter = _make_adapter(tmp_path)
    coordinator.set_subscription(12345, True)

    assert not adapter.enqueue(
        "evt-database-mismatch",
        12345,
        generation=1,
        database_id="0123456789abcdef0123456789abcdef",
    )


def test_missing_witness_evidence_rejected(tmp_path):
    coordinator, adapter = _make_adapter(tmp_path)
    coordinator.set_subscription(12345, True)

    coordinator.witness.path.unlink()

    assert not adapter.enqueue(
        "evt-no-witness",
        12345,
        generation=1,
        database_id=coordinator.consent.database_id,
    )


def test_dispatch_rejects_mismatched_recipient(tmp_path):
    coordinator, adapter = _make_adapter(tmp_path)
    coordinator.set_subscription(12345, True)

    assert adapter.enqueue(
        "evt-recipient-mismatch",
        12345,
        generation=1,
        database_id=coordinator.consent.database_id,
    )

    assert not adapter.dispatch_due("evt-recipient-mismatch", 12346, lambda: True)

    with sqlite3.connect(adapter.path) as db:
        status = db.execute(
            "SELECT status FROM delivery_queue WHERE event_id=?",
            ("evt-recipient-mismatch",),
        ).fetchone()[0]
    assert status == "denied"


def test_duplicate_dispatch_is_not_retried_after_success(tmp_path):
    coordinator, adapter = _make_adapter(tmp_path)
    coordinator.set_subscription(12345, True)

    assert adapter.enqueue(
        "evt-idempotent",
        12345,
        generation=1,
        database_id=coordinator.consent.database_id,
    )

    sends = []

    def sender():
        sends.append("sent")
        return True

    assert adapter.dispatch_due("evt-idempotent", 12345, sender)
    assert not adapter.dispatch_due("evt-idempotent", 12345, sender)
    assert sends == ["sent"]


def test_concurrent_dispatch_workers_only_one_claims_transport(tmp_path):
    coordinator, adapter = _make_adapter(tmp_path)
    coordinator.set_subscription(12345, True)

    assert adapter.enqueue(
        "evt-concurrent",
        12345,
        generation=1,
        database_id=coordinator.consent.database_id,
    )

    sends = []
    lock = threading.Lock()

    def sender():
        with lock:
            sends.append("sent")
        return True

    threads = [
        threading.Thread(target=adapter.dispatch_due, args=("evt-concurrent", 12345, sender))
        for _ in range(2)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert len(sends) == 1
    with sqlite3.connect(adapter.path) as db:
        status = db.execute(
            "SELECT status FROM delivery_queue WHERE event_id=?",
            ("evt-concurrent",),
        ).fetchone()[0]
    assert status == "sent"


def test_old_generation_cannot_be_reactivated_by_resubscribe(tmp_path):
    coordinator, adapter = _make_adapter(tmp_path)
    coordinator.set_subscription(12345, True)

    assert adapter.enqueue(
        "evt-old-generation",
        12345,
        generation=1,
        database_id=coordinator.consent.database_id,
    )

    coordinator.set_subscription(12345, False)
    coordinator.set_subscription(12345, True)

    assert not adapter.dispatch_due("evt-old-generation", 12345, lambda: True)

    assert adapter.enqueue(
        "evt-new-generation",
        12345,
        generation=3,
        database_id=coordinator.consent.database_id,
    )
    assert adapter.dispatch_due("evt-new-generation", 12345, lambda: True)


def test_transport_errors_fail_closed_and_mark_uncertain(tmp_path):
    coordinator, adapter = _make_adapter(tmp_path)
    coordinator.set_subscription(12345, True)

    assert adapter.enqueue(
        "evt-transport-error",
        12345,
        generation=1,
        database_id=coordinator.consent.database_id,
    )

    def boom() -> bool:
        raise RuntimeError("transport failure")

    assert not adapter.dispatch_due("evt-transport-error", 12345, boom)

    with sqlite3.connect(adapter.path) as db:
        status = db.execute(
            "SELECT status FROM delivery_queue WHERE event_id=?",
            ("evt-transport-error",),
        ).fetchone()[0]
    assert status == "uncertain"


def test_process_interruption_after_claim_is_recovered_by_stale_lease(tmp_path):
    coordinator, adapter = _make_adapter(tmp_path)
    coordinator.set_subscription(12345, True)

    assert adapter.enqueue(
        "evt-stale-lease",
        12345,
        generation=1,
        database_id=coordinator.consent.database_id,
    )

    with sqlite3.connect(adapter.path) as db:
        db.execute(
            "UPDATE delivery_queue SET status='dispatching', lease_expires_at=?, lease_token='stale' WHERE event_id=?",
            (time.time() - 5, "evt-stale-lease"),
        )
        db.commit()

    assert adapter.dispatch_due("evt-stale-lease", 12345, lambda: True)

    with sqlite3.connect(adapter.path) as db:
        status = db.execute(
            "SELECT status FROM delivery_queue WHERE event_id=?",
            ("evt-stale-lease",),
        ).fetchone()[0]
    assert status == "sent"


def test_active_dispatch_lease_blocks_reentry_from_a_second_worker(tmp_path):
    coordinator, adapter = _make_adapter(tmp_path)
    coordinator.set_subscription(12345, True)

    assert adapter.enqueue(
        "evt-active-lease",
        12345,
        generation=1,
        database_id=coordinator.consent.database_id,
    )

    with sqlite3.connect(adapter.path) as db:
        db.execute(
            "UPDATE delivery_queue SET status='dispatching', lease_expires_at=?, lease_token='active' WHERE event_id=?",
            (time.time() + 120, "evt-active-lease"),
        )
        db.commit()

    assert not adapter.dispatch_due("evt-active-lease", 12345, lambda: True)


def test_retry_after_uncertain_transport_outcome_is_rejected_until_requeue(tmp_path):
    coordinator, adapter = _make_adapter(tmp_path)
    coordinator.set_subscription(12345, True)

    assert adapter.enqueue(
        "evt-uncertain-retry",
        12345,
        generation=1,
        database_id=coordinator.consent.database_id,
    )

    def boom() -> bool:
        raise RuntimeError("transport failure")

    assert not adapter.dispatch_due("evt-uncertain-retry", 12345, boom)
    assert not adapter.dispatch_due("evt-uncertain-retry", 12345, lambda: True)

    with sqlite3.connect(adapter.path) as db:
        status = db.execute(
            "SELECT status FROM delivery_queue WHERE event_id=?",
            ("evt-uncertain-retry",),
        ).fetchone()[0]
    assert status == "uncertain"


def test_revocation_after_authorization_is_limitated_to_pre_admission_boundary(tmp_path):
    coordinator, adapter = _make_adapter(tmp_path)
    coordinator.set_subscription(12345, True)

    assert adapter.enqueue(
        "evt-revocation-limit",
        12345,
        generation=1,
        database_id=coordinator.consent.database_id,
    )

    def revoke_then_send() -> bool:
        coordinator.set_subscription(12345, False)
        return True

    assert adapter.dispatch_due("evt-revocation-limit", 12345, revoke_then_send)

    assert not adapter.authorize_for_delivery(12345, 1, coordinator.consent.database_id)


def test_recovery_assessment_is_diagnostic_only(tmp_path):
    coordinator, adapter = _make_adapter(tmp_path)
    coordinator.set_subscription(12345, True)

    assessment = assess_recovery(coordinator, 12345)

    assert assessment.status == RecoveryStatus.CONSISTENT
    assert not adapter.authorize_for_delivery(12345, None, coordinator.consent.database_id)
    assert not adapter.authorize_for_delivery(12345, 1, None)
