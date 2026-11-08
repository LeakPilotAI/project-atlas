"""Temporary synthetic integration only; fake Discord transport, no runtime hooks."""
import asyncio
import json
import tempfile
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from app.alerts.subscriptions import DiscordSubscriptionStore
from app.services.discord_lifecycle_outbox import LifecycleContractError
from app.services.paper_journal_identity import read_paper_journal_identities
from app.services.paper_lifecycle_producer import IsolatedPaperLifecycleProducer

STAMP = "2026-10-14T10:00:00+00:00"
NOW = datetime(2026, 10, 14, 11, tzinfo=UTC)


def append(p, kind, trade="new", **extra):
    row = {"event": kind, "trade_id": trade, "timestamp": STAMP, **extra}
    with p.journal.open("ab") as handle:
        handle.write((json.dumps(row) + "\n").encode())


@pytest.fixture
def producer():
    with tempfile.TemporaryDirectory(prefix="atlas-e135-") as directory:
        p = IsolatedPaperLifecycleProducer(Path(directory))
        p.journal.touch()
        DiscordSubscriptionStore(p.subscriptions).save({11, 22})
        yield p


def activate(p):
    p.activate_for_simulation(approval_reference="fixture operator approval")
    p.approve_simulated_delivery(approval_reference="fixture fake delivery approval")


class FakeSender:
    simulation_only = True

    def __init__(self, outcomes=None):
        self.calls = []
        self.outcomes = outcomes or {}

    async def __call__(self, *, recipient_id, event):
        self.calls.append((recipient_id, event.event_id))
        outcome = self.outcomes.get(recipient_id, True)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def test_not_connected_to_production(tmp_path):
    with pytest.raises(LifecycleContractError, match="OS-temp"):
        IsolatedPaperLifecycleProducer(tmp_path)
    root = Path(__file__).resolve().parents[1] / "backend/app"
    references = [p.relative_to(root).as_posix() for p in root.rglob("*.py")
                  if "paper_lifecycle_producer" in p.read_text(encoding="utf-8")]
    assert references == []  # No import/hook in runtime code, including itself.


def test_missing_watermark_never_auto_activates(producer):
    append(producer, "open", "history")
    with pytest.raises(LifecycleContractError, match="watermark"):
        producer.process()
    assert producer.outbox.delivery_states(read_paper_journal_identities(producer.journal).events[0].event_id) == {}
    with pytest.raises(LifecycleContractError, match="approval"):
        producer.activate_for_simulation(approval_reference="")


def test_history_and_preactivation_trade_followups_are_excluded(producer):
    append(producer, "open", "old")
    append(producer, "mark", "old")
    old_bytes = producer.journal.read_bytes()
    activate(producer)
    append(producer, "close", "old")
    append(producer, "open")
    append(producer, "mark")
    append(producer, "close", exit_reason="SETUP_STOP")
    events = read_paper_journal_identities(producer.journal).events
    assert producer.process() == 3
    assert all(not producer.outbox.delivery_states(e.event_id) for e in events[:3])
    assert all(set(producer.outbox.delivery_states(e.event_id)) == {11, 22} for e in events[3:])
    assert producer.journal.read_bytes().startswith(old_bytes)
    assert [e.source_sequence for e in events[3:]] == [1, 2, 3]


def test_restart_identity_dedup_and_order(producer):
    activate(producer)
    for kind in ("open", "mark", "close"):
        append(producer, kind)
    ids = [e.event_id for e in read_paper_journal_identities(producer.journal).events]
    assert producer.process() == 3
    p = IsolatedPaperLifecycleProducer(producer.root)
    assert p.process() == 0
    fake = FakeSender()
    for _ in range(3):
        assert asyncio.run(p.dispatch_simulated(sender=fake, now=NOW))["delivered"] == 2
    assert [event for _, event in fake.calls] == [ids[0], ids[0], ids[1], ids[1], ids[2], ids[2]]
    assert asyncio.run(p.dispatch_simulated(sender=fake, now=NOW))["attempted"] == 0


def test_crash_after_staging_preserves_original_recipients(producer, monkeypatch):
    activate(producer)
    append(producer, "open")

    def crash(*args):
        raise OSError("simulated interruption before transfer")

    monkeypatch.setattr(producer.outbox, "enqueue", crash)
    with pytest.raises(OSError):
        producer.process()
    DiscordSubscriptionStore(producer.subscriptions).save({33})
    p = IsolatedPaperLifecycleProducer(producer.root)
    assert p.process() == 0
    event = read_paper_journal_identities(p.journal).events[0]
    assert set(p.outbox.delivery_states(event.event_id)) == {11, 22}
    fake = FakeSender()
    assert asyncio.run(p.dispatch_simulated(sender=fake, now=NOW))["uncertain"] == 2
    assert fake.calls == []


@pytest.mark.parametrize("subscribers", [{11}, {11, 22, 33}, set()])
def test_subscription_changes_do_not_add_old_recipients(producer, subscribers):
    activate(producer)
    append(producer, "open", "first")
    producer.process()
    first = read_paper_journal_identities(producer.journal).events[0]
    DiscordSubscriptionStore(producer.subscriptions).save(subscribers)
    append(producer, "open", "second")
    producer.process()
    second = read_paper_journal_identities(producer.journal).events[1]
    assert set(producer.outbox.delivery_states(first.event_id)) == {11, 22}
    assert set(producer.outbox.delivery_states(second.event_id)) == subscribers
    fake = FakeSender()
    result = asyncio.run(producer.dispatch_simulated(sender=fake, now=NOW))
    assert result["uncertain"] == 2
    assert {uid for uid, eid in fake.calls if eid == second.event_id} == subscribers
    assert not any(eid == first.event_id for _, eid in fake.calls)


def test_unsubscribe_resubscribe_does_not_revive_old_consent(producer):
    activate(producer)
    append(producer, "open")
    producer.process()
    DiscordSubscriptionStore(producer.subscriptions).save(set())
    DiscordSubscriptionStore(producer.subscriptions).save({11, 22})
    fake = FakeSender()
    assert asyncio.run(producer.dispatch_simulated(sender=fake, now=NOW))["uncertain"] == 2
    assert not fake.calls


def test_empty_recipient_snapshot_stays_empty(producer):
    DiscordSubscriptionStore(producer.subscriptions).save(set())
    activate(producer)
    append(producer, "open")
    producer.process()
    DiscordSubscriptionStore(producer.subscriptions).save({33})
    p = IsolatedPaperLifecycleProducer(producer.root)
    p.process()
    fake = FakeSender()
    assert asyncio.run(p.dispatch_simulated(sender=fake, now=NOW))["attempted"] == 0


def test_partial_recipient_failure_only_retries_known_failure(producer):
    activate(producer)
    append(producer, "open")
    append(producer, "close")
    producer.process()
    fake = FakeSender({22: False})
    first = asyncio.run(producer.dispatch_simulated(sender=fake, now=NOW))
    assert (first["delivered"], first["retry"]) == (1, 1)
    assert asyncio.run(producer.dispatch_simulated(sender=fake, now=NOW))["attempted"] == 0
    fake.outcomes = {}
    assert asyncio.run(producer.dispatch_simulated(sender=fake, now=NOW + timedelta(seconds=5)))["delivered"] == 1
    assert asyncio.run(producer.dispatch_simulated(sender=fake, now=NOW + timedelta(seconds=6)))["delivered"] == 2
    assert [uid for uid, _ in fake.calls[:3]] == [11, 22, 22]


@pytest.mark.parametrize("outcome", [TimeoutError("unknown outcome"), None, "yes"])
def test_uncertain_delivery_quarantines_stream_across_restart(producer, outcome):
    activate(producer)
    append(producer, "open")
    append(producer, "close")
    producer.process()
    fake = FakeSender({22: outcome})
    assert asyncio.run(producer.dispatch_simulated(sender=fake, now=NOW))["uncertain"] == 1
    p = IsolatedPaperLifecycleProducer(producer.root)
    later = FakeSender()
    assert asyncio.run(p.dispatch_simulated(sender=later, now=NOW + timedelta(days=1)))["attempted"] == 0
    assert not later.calls


@pytest.mark.parametrize("damage", ["truncate", "rewrite", "replace", "missing", "partial", "malformed"])
def test_damaged_journal_fails_closed_without_repair(producer, damage):
    append(producer, "open", "old")
    activate(producer)
    before = producer.journal.read_bytes()
    if damage == "truncate":
        producer.journal.write_bytes(b"")
    elif damage == "rewrite":
        producer.journal.write_bytes(before.replace(b'old', b'bad'))
    elif damage == "replace":
        new = producer.root / "replacement"
        new.write_bytes(before)
        new.replace(producer.journal)
    elif damage == "missing":
        producer.journal.unlink()
    else:
        with producer.journal.open("ab") as handle:
            handle.write(b'{"event":' if damage == "partial" else b'bad\n')
    damaged = producer.journal.read_bytes() if producer.journal.exists() else None
    p = IsolatedPaperLifecycleProducer(producer.root)
    with pytest.raises((LifecycleContractError, OSError)):
        p.process()
    assert (producer.journal.read_bytes() if producer.journal.exists() else None) == damaged


def test_completed_partial_tail_recovers_without_backfill(producer):
    activate(producer)
    with producer.journal.open("ab") as handle:
        handle.write(b'{"event":"open",')
    with pytest.raises(LifecycleContractError):
        producer.process()
    with producer.journal.open("ab") as handle:
        handle.write(b'"trade_id":"new","timestamp":"2026-10-14T10:00:00Z"}\n')
    assert producer.process() == 1
    assert producer.process() == 0


def test_orphan_postactivation_event_rejected(producer):
    activate(producer)
    append(producer, "close")
    with pytest.raises(LifecycleContractError, match="orphan"):
        producer.process()


def test_concurrent_process_and_dispatch_are_idempotent(producer):
    activate(producer)
    append(producer, "open")
    copies = [IsolatedPaperLifecycleProducer(producer.root) for _ in range(4)]
    with ThreadPoolExecutor(max_workers=4) as pool:
        assert sum(pool.map(lambda p: p.process(), copies)) == 1
    fake = FakeSender()

    async def dispatch():
        return await asyncio.gather(*(p.dispatch_simulated(sender=fake, now=NOW) for p in copies))

    assert sum(r["delivered"] for r in asyncio.run(dispatch())) == 2
    assert len(set(fake.calls)) == 2


def test_delivery_requires_separate_approval(producer):
    producer.activate_for_simulation(approval_reference="activation only")
    append(producer, "open")
    producer.process()
    with pytest.raises(LifecycleContractError, match="delivery approval"):
        asyncio.run(producer.dispatch_simulated(sender=FakeSender()))
    with pytest.raises(LifecycleContractError, match="simulation transport"):
        asyncio.run(producer.dispatch_simulated(sender=lambda **kw: True))
    with pytest.raises(LifecycleContractError, match="already exists"):
        producer.activate_for_simulation(approval_reference="reset forbidden")


def test_cancellation_quarantines_inflight_without_resend(producer):
    activate(producer)
    append(producer, "open")
    producer.process()

    async def scenario():
        entered = asyncio.Event()

        class PendingSender:
            simulation_only = True

            async def __call__(self, **kwargs):
                entered.set()
                await asyncio.Event().wait()

        task = asyncio.create_task(producer.dispatch_simulated(sender=PendingSender(), now=NOW))
        await entered.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(scenario())
    p = IsolatedPaperLifecycleProducer(producer.root)
    fake = FakeSender()
    result = asyncio.run(p.dispatch_simulated(sender=fake, now=NOW + timedelta(seconds=121)))
    assert result["recovered_expired_leases"] == 2 and not fake.calls


def test_stop_preserves_durable_work_and_sends_nothing(producer):
    activate(producer)
    append(producer, "open")
    producer.process()
    before = producer.journal.read_bytes()
    producer.stop()
    with pytest.raises(LifecycleContractError, match="stopped"):
        producer.process()
    with pytest.raises(LifecycleContractError, match="stopped"):
        asyncio.run(producer.dispatch_simulated(sender=FakeSender()))
    assert producer.journal.read_bytes() == before


def test_corrupt_subscriptions_block_enqueue_and_delivery(producer):
    activate(producer)
    append(producer, "open")
    producer.subscriptions.write_text("bad")
    with pytest.raises(LifecycleContractError, match="subscription"):
        producer.process()


def test_no_live_owner_fallback_when_subscription_store_absent(producer):
    producer.subscriptions.unlink()
    activate(producer)
    append(producer, "open")
    producer.process()
    assert asyncio.run(producer.dispatch_simulated(sender=FakeSender(), now=NOW))["attempted"] == 0


def test_stop_during_dispatch_prevents_remaining_sends(producer):
    activate(producer)
    append(producer, "open")
    producer.process()

    class StopSender(FakeSender):
        async def __call__(self, **kwargs):
            result = await super().__call__(**kwargs)
            producer.stop()
            return result

    fake = StopSender()
    result = asyncio.run(producer.dispatch_simulated(sender=fake, now=NOW))
    assert result["delivered"] == 1 and result["uncertain"] == 1
    assert len(fake.calls) == 1


def test_outbox_replacement_never_reconstructs_acknowledged_delivery(producer):
    activate(producer)
    append(producer, "open")
    producer.process()
    asyncio.run(producer.dispatch_simulated(sender=FakeSender(), now=NOW))
    replacement = producer.root / "old-outbox.sqlite3"
    producer.outbox_path.replace(replacement)
    restarted = IsolatedPaperLifecycleProducer(producer.root)
    with pytest.raises(LifecycleContractError, match="outbox replaced"):
        restarted.process()
    with pytest.raises(LifecycleContractError, match="outbox replaced"):
        asyncio.run(restarted.dispatch_simulated(sender=FakeSender()))


def test_corrupt_watermark_store_is_never_reset(producer):
    activate(producer)
    producer.state_path.write_bytes(b"not sqlite")
    with pytest.raises(Exception, match="database"):
        IsolatedPaperLifecycleProducer(producer.root)
    assert producer.state_path.read_bytes() == b"not sqlite"


def test_cannot_activate_missing_or_partial_source(producer):
    producer.journal.unlink()
    with pytest.raises(OSError):
        producer.activate_for_simulation(approval_reference="fixture")
    producer.journal.write_bytes(b'{"event":')
    with pytest.raises(LifecycleContractError):
        producer.activate_for_simulation(approval_reference="fixture")
    producer.journal.write_bytes(b"")
    producer.activate_for_simulation(approval_reference="fixture")


def test_payload_and_original_source_identity_are_preserved(producer):
    activate(producer)
    append(producer, "open", secret="must not escape E134 allowlist")
    append(producer, "close", interrupted=True)
    expected = read_paper_journal_identities(producer.journal).events
    producer.process()

    class InspectSender(FakeSender):
        async def __call__(self, *, recipient_id, event):
            assert event in expected
            assert "secret" not in event.payload
            return await super().__call__(recipient_id=recipient_id, event=event)

    fake = InspectSender()
    asyncio.run(producer.dispatch_simulated(sender=fake, now=NOW))
    asyncio.run(producer.dispatch_simulated(sender=fake, now=NOW))
    assert len(fake.calls) == 4


def test_unsubscribe_during_authorization_yield_never_enters_sender(producer, monkeypatch):
    activate(producer)
    append(producer, "open")
    producer.process()
    original = asyncio.to_thread

    async def changed_after_worker(func, *args, **kwargs):
        value = await original(func, *args, **kwargs)
        if func.__name__ == "authorize" and args:
            DiscordSubscriptionStore(producer.subscriptions).save(set())
        return value

    monkeypatch.setattr(asyncio, "to_thread", changed_after_worker)
    fake = FakeSender()
    result = asyncio.run(producer.dispatch_simulated(sender=fake, now=NOW))
    assert not fake.calls and result["uncertain"] == 2
