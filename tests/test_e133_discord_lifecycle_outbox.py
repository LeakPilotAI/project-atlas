import asyncio
import sqlite3
from datetime import datetime, timedelta, timezone

import pytest
from app.services.discord_lifecycle_outbox import (
    DiscordLifecycleOutbox,
    LifecycleContractError,
    make_lifecycle_event,
)

NOW = datetime(2026, 10, 14, 12, 0, tzinfo=timezone.utc)


def event(
    *,
    event_type="PAPER_ENTRY",
    entity_id="trade-1",
    source_event_id="trade-1:open",
    source_sequence=1,
    payload=None,
    occurred_at=NOW,
):
    return make_lifecycle_event(
        event_type=event_type,
        source="paper_journal",
        entity_id=entity_id,
        source_event_id=source_event_id,
        source_sequence=source_sequence,
        occurred_at=occurred_at,
        payload=payload or {"symbol": "BTC", "side": "LONG"},
    )


def test_event_identity_is_stable_and_source_specific():
    first = event()
    second = event()
    assert first.event_id == second.event_id
    assert len(first.event_id) == 64
    assert (
        event(event_type="PAPER_CLOSE", source_event_id="trade-1:close").event_id
        != first.event_id
    )
    assert (
        event(entity_id="trade-2", source_event_id="trade-2:open").event_id
        != first.event_id
    )


@pytest.mark.parametrize(
    ("event_type", "entity_id", "source_event_id"),
    [
        ("SIGNAL_CREATED", "signal-42", "signal-42:created"),
        ("SIGNAL_INVALIDATED", "signal-42", "signal-42:invalidated"),
        ("PAPER_MARK", "trade-1", "journal-row-99"),
        ("PAPER_INTERRUPTED", "trade-1", "shutdown-run-7:trade-1"),
        ("PAPER_RISK_STOP", "trade-1", "risk-transition-3"),
    ],
)
def test_lifecycle_kind_and_immutable_source_key_define_event_identity(
    event_type, entity_id, source_event_id
):
    one = event(
        event_type=event_type,
        entity_id=entity_id,
        source_event_id=source_event_id,
    )
    two = event(
        event_type=event_type,
        entity_id=entity_id,
        source_event_id=source_event_id,
    )
    assert one.event_id == two.event_id


@pytest.mark.parametrize(
    "kwargs",
    [
        {"event_type": "UNSUPPORTED"},
        {"entity_id": ""},
        {"source_event_id": ""},
        {"source_sequence": True},
        {"source_sequence": 0},
        {"occurred_at": datetime.fromisoformat("2026-10-14T00:00:00")},
        {"payload": {"not_json": object()}},
        {"payload": {"not_finite": float("nan")}},
    ],
)
def test_invalid_event_identity_or_payload_fails_closed(kwargs):
    with pytest.raises(LifecycleContractError):
        event(**kwargs)


def test_payload_size_is_bounded():
    with pytest.raises(LifecycleContractError, match="16 KiB"):
        event(payload={"text": "x" * 17_000})


def test_outbox_rejects_same_identity_with_changed_content(tmp_path):
    store = DiscordLifecycleOutbox(tmp_path / "outbox.sqlite3")
    assert store.enqueue(event(), [1001])
    with pytest.raises(LifecycleContractError, match="conflicting content"):
        store.enqueue(event(payload={"symbol": "ETH"}), [1001])


@pytest.mark.asyncio
async def test_duplicate_event_and_recipient_snapshot_do_not_resend(tmp_path):
    path = tmp_path / "outbox.sqlite3"
    store = DiscordLifecycleOutbox(path)
    paper_event = event()
    assert store.enqueue(paper_event, [1001])
    assert not store.enqueue(paper_event, [1001, 1002])

    delivered = []

    async def sender(*, recipient_id, event):
        delivered.append((recipient_id, event.event_id))
        return True

    first = await store.dispatch_due(sender=sender, now=NOW)
    restarted = DiscordLifecycleOutbox(path)
    second = await restarted.dispatch_due(sender=sender, now=NOW + timedelta(minutes=5))
    assert first["delivered"] == 1
    assert second["attempted"] == 0
    assert delivered == [(1001, paper_event.event_id)]
    assert (
        restarted.delivery_states(paper_event.event_id)[1001]["status"] == "delivered"
    )


def test_source_sequences_must_be_contiguous_and_in_order(tmp_path):
    store = DiscordLifecycleOutbox(tmp_path / "outbox.sqlite3")
    later = event(
        event_type="PAPER_MARK", source_event_id="trade-1:mark:2", source_sequence=2
    )
    with pytest.raises(LifecycleContractError, match="expected 1"):
        store.enqueue(later, [1001])
    first = event()
    assert store.enqueue(first, [1001])
    assert store.enqueue(later, [1001])


@pytest.mark.asyncio
async def test_later_event_waits_until_all_earlier_recipients_are_acknowledged(
    tmp_path,
):
    store = DiscordLifecycleOutbox(tmp_path / "outbox.sqlite3")
    first = event()
    later = event(
        event_type="PAPER_CLOSE", source_event_id="trade-1:close", source_sequence=2
    )
    store.enqueue(first, [1001, 1002])
    store.enqueue(later, [1001, 1002])
    attempted_events = []
    earlier_recipient_attempts = 0

    async def sender(*, recipient_id, event):
        nonlocal earlier_recipient_attempts
        attempted_events.append((event.event_id, recipient_id))
        if event.event_id == first.event_id and recipient_id == 1002:
            earlier_recipient_attempts += 1
            return earlier_recipient_attempts > 1
        return event.event_id == first.event_id or recipient_id == 1001

    await store.dispatch_due(sender=sender, now=NOW, batch_size=10)
    assert {event_id for event_id, _ in attempted_events} == {first.event_id}
    await store.dispatch_due(
        sender=sender, now=NOW + timedelta(seconds=5), batch_size=10
    )
    assert {event_id for event_id, _ in attempted_events} == {first.event_id}
    await store.dispatch_due(
        sender=sender, now=NOW + timedelta(seconds=6), batch_size=10
    )
    assert (later.event_id, 1001) in attempted_events
    assert (later.event_id, 1002) in attempted_events
    assert attempted_events.index((first.event_id, 1002), 1) < attempted_events.index(
        (later.event_id, 1001)
    )


@pytest.mark.asyncio
async def test_partial_recipient_failure_retries_only_the_failed_recipient(tmp_path):
    store = DiscordLifecycleOutbox(tmp_path / "outbox.sqlite3")
    paper_event = event()
    store.enqueue(paper_event, [1001, 1002])
    calls = []

    async def sender(*, recipient_id, event):
        calls.append(recipient_id)
        return recipient_id == 1001 or len(calls) > 2

    first = await store.dispatch_due(sender=sender, now=NOW)
    assert first["delivered"] == 1
    assert first["retry"] == 1
    assert calls == [1001, 1002]

    not_due = await store.dispatch_due(sender=sender, now=NOW + timedelta(seconds=4))
    assert not_due["attempted"] == 0
    retried = await store.dispatch_due(sender=sender, now=NOW + timedelta(seconds=5))
    assert retried["delivered"] == 1
    assert calls == [1001, 1002, 1002]
    states = store.delivery_states(paper_event.event_id)
    assert states[1001]["attempts"] == 1
    assert states[1002]["attempts"] == 2


@pytest.mark.asyncio
async def test_sender_exception_is_uncertain_and_not_retried_after_restart(tmp_path):
    path = tmp_path / "outbox.sqlite3"
    store = DiscordLifecycleOutbox(path)
    paper_event = event()
    store.enqueue(paper_event, [1001])

    async def interrupted_sender(*, recipient_id, event):
        raise TimeoutError("delivery outcome unknown")

    result = await store.dispatch_due(sender=interrupted_sender, now=NOW)
    assert result["uncertain"] == 1
    restarted = DiscordLifecycleOutbox(path)
    never_called = []

    async def sender(*, recipient_id, event):
        never_called.append(recipient_id)
        return True

    retry = await restarted.dispatch_due(sender=sender, now=NOW + timedelta(days=1))
    assert retry["attempted"] == 0
    assert never_called == []
    assert (
        restarted.delivery_states(paper_event.event_id)[1001]["status"] == "uncertain"
    )


@pytest.mark.asyncio
async def test_non_boolean_sender_acknowledgement_is_quarantined(tmp_path):
    store = DiscordLifecycleOutbox(tmp_path / "outbox.sqlite3")
    paper_event = event()
    store.enqueue(paper_event, [1001])

    async def invalid_sender(*, recipient_id, event):
        return 1

    result = await store.dispatch_due(sender=invalid_sender, now=NOW)
    assert result["uncertain"] == 1
    assert store.delivery_states(paper_event.event_id)[1001]["status"] == "uncertain"


@pytest.mark.asyncio
async def test_cancelled_worker_lease_recovers_to_uncertain_not_duplicate(tmp_path):
    path = tmp_path / "outbox.sqlite3"
    store = DiscordLifecycleOutbox(path)
    paper_event = event()
    store.enqueue(paper_event, [1001])
    sending = asyncio.Event()

    async def hanging_sender(*, recipient_id, event):
        sending.set()
        await asyncio.Future()

    worker = asyncio.create_task(store.dispatch_due(sender=hanging_sender, now=NOW))
    await asyncio.wait_for(sending.wait(), timeout=2)
    worker.cancel()
    with pytest.raises(asyncio.CancelledError):
        await worker

    restarted = DiscordLifecycleOutbox(path)
    calls = []

    async def sender(*, recipient_id, event):
        calls.append(recipient_id)
        return True

    result = await restarted.dispatch_due(
        sender=sender,
        now=NOW + timedelta(seconds=121),
    )
    assert result["recovered_expired_leases"] == 1
    assert result["attempted"] == 0
    assert calls == []
    assert (
        restarted.delivery_states(paper_event.event_id)[1001]["status"] == "uncertain"
    )


@pytest.mark.asyncio
async def test_concurrent_dispatchers_claim_a_recipient_only_once(tmp_path):
    store = DiscordLifecycleOutbox(tmp_path / "outbox.sqlite3")
    paper_event = event()
    store.enqueue(paper_event, [1001])
    calls = []

    async def sender(*, recipient_id, event):
        calls.append((recipient_id, event.event_id))
        await asyncio.sleep(0.05)
        return True

    first, second = await asyncio.gather(
        store.dispatch_due(sender=sender, now=NOW),
        store.dispatch_due(sender=sender, now=NOW),
    )
    assert sum(result["attempted"] for result in (first, second)) == 1
    assert calls == [(1001, paper_event.event_id)]


@pytest.mark.asyncio
async def test_explicit_non_delivery_has_bounded_retries(tmp_path):
    store = DiscordLifecycleOutbox(tmp_path / "outbox.sqlite3")
    paper_event = event()
    store.enqueue(paper_event, [1001])
    calls = []

    async def failed_sender(*, recipient_id, event):
        calls.append(recipient_id)
        return False

    first = await store.dispatch_due(sender=failed_sender, now=NOW)
    second = await store.dispatch_due(
        sender=failed_sender, now=NOW + timedelta(seconds=5)
    )
    third = await store.dispatch_due(
        sender=failed_sender, now=NOW + timedelta(seconds=35)
    )
    fourth = await store.dispatch_due(sender=failed_sender, now=NOW + timedelta(days=1))
    assert [first["retry"], second["retry"], third["dead"], fourth["attempted"]] == [
        1,
        1,
        1,
        0,
    ]
    assert calls == [1001, 1001, 1001]
    assert store.delivery_states(paper_event.event_id)[1001]["attempts"] == 3


def test_malformed_database_is_preserved_and_rejected(tmp_path):
    path = tmp_path / "malformed.sqlite3"
    original = b"not a sqlite database"
    path.write_bytes(original)
    with pytest.raises(sqlite3.DatabaseError):
        DiscordLifecycleOutbox(path)
    assert path.read_bytes() == original


def test_unknown_schema_version_is_rejected_without_reset(tmp_path):
    path = tmp_path / "outbox.sqlite3"
    DiscordLifecycleOutbox(path)
    with sqlite3.connect(path) as connection:
        connection.execute("PRAGMA user_version=99")
    with pytest.raises(LifecycleContractError, match="unrecognized"):
        DiscordLifecycleOutbox(path)
    with sqlite3.connect(path) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 99


def test_recipient_ids_support_unsigned_64_bit_values(tmp_path):
    store = DiscordLifecycleOutbox(tmp_path / "outbox.sqlite3")
    paper_event = event()
    recipient = (1 << 64) - 1
    store.enqueue(paper_event, [recipient])
    assert store.delivery_states(paper_event.event_id)[recipient]["status"] == "pending"
