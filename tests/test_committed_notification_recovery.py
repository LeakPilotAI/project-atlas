"""Canonical pure-accounting commits -> existing durable outbox, fake sender only."""

import asyncio
import copy
import json
import sqlite3
import tempfile
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from app.services.discord_consent_coordinator import DiscordConsentCoordinator
from app.services.discord_consent_delivery_adapter import DiscordConsentDeliveryAdapter
from app.services.discord_consent_generations import ConsentStateError
from app.services.discord_lifecycle_outbox import LifecycleContractError, LifecycleEvent
from app.services.paper_financial_replay import (
    apply_event,
    body,
    digest,
    event_stream_record,
    initial_state,
    strict,
)
from continuation_fixture import manifests, records
from test_quality_dips_current_producer import proof

from scripts.observation_runtime.committed_notification_recovery import (
    CommittedNotificationRecovery,
)


class FakeSender:
    simulation_only = True

    def __init__(self, result=True):
        self.calls = []
        self.result = result

    async def __call__(self, *, recipient_id, event):
        self.calls.append((recipient_id, event))
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


@pytest.fixture
def system(request):
    with tempfile.TemporaryDirectory(prefix="atlas-e135-") as directory:
        root = Path(directory)
        now = [3600]
        ms = manifests()
        for manifest in ms.values():
            manifest["opened_at"] = 3600
        scope = {
            k: {
                "account_id": "SYNTHETIC-" + k,
                "epoch": v["epoch"],
                "currency": v["currency"],
            }
            for k, v in ms.items()
        }
        cut = {
            "schema": "ATLAS_COMMITTED_LIFECYCLE_CUT_V1",
            "execution_domain": "DISPOSABLE",
            "source_id": "SYNTHETIC-ACKNOWLEDGED-CUT",
            "observed_at": now[0],
            "manifests": ms,
            "commits": [],
        }
        source = SimpleNamespace(read_committed=lambda: copy.deepcopy(cut))
        flags = SimpleNamespace(valid=True, mutate=False)

        def accept(context, *, now):
            if not flags.valid:
                return False
            assert context == {"scope": scope, "cut": cut}
            receipt = proof(
                "ATLAS_COMMITTED_EVENTS_VERIFIED_V1",
                context,
                execution_domain="DISPOSABLE",
            )
            if flags.mutate:
                context["cut"]["source_id"] = "FOREIGN"
            return receipt

        authority = SimpleNamespace(verify_committed=accept)
        cpath, wpath = root / "consent.sqlite3", root / "witness.sqlite3"
        consent = DiscordConsentCoordinator.create(cpath, wpath)
        consent.set_subscription(11, True)
        policy = {
            "recipients": {"11": ["PAPER_ENTRY", "PAPER_MARK", "PAPER_CLOSE"]},
            "max_per_minute": 10,
            "max_age_seconds": 120,
        }
        options = getattr(request, "param", {})
        policy["max_per_minute"] = options.get("rate", 10)
        policy["recipients"]["11"] = options.get("types", policy["recipients"]["11"])
        clock = lambda: now[0]

        def open_producer():
            return CommittedNotificationRecovery(
                root,
                source=source,
                authority=authority,
                consent=DiscordConsentCoordinator(cpath, wpath),
                scope=scope,
                policy=policy,
                clock=clock,
            )

        p = open_producer()
        p.activate_for_simulation(approval_reference="EXPLICIT_TEST_SOURCE_ADMISSION")
        p.approve_simulated_delivery(approval_reference="EXPLICIT_FAKE_SEND_ONLY")
        states = {k: initial_state(m) for k, m in ms.items()}
        heads = {k: digest(m) for k, m in ms.items()}
        samples = records()
        counts = {k: 0 for k in ms}

        def advance(seconds):
            now[0] += seconds
            cut["observed_at"] = now[0]

        def append(lane="QUALITY_DIPS", kind="ENTRY", quantity=None):
            sample = next(
                r for r in samples[lane] if strict(r["command"])["kind"] == kind
            )
            command = strict(sample["command"])
            advance(1)
            command.update(
                epoch=ms[lane]["epoch"],
                operation_id=f"SYNTHETIC-{lane}-{counts[lane]}-{kind}",
                expected_source_revision=counts[lane],
                timestamp=now[0],
            )
            if "quote" in command:
                command["quote"]["observed_at"] = now[0]
            if "evidence" in command:
                command["evidence"]["observed_at"] = now[0]
                if "sequence" in command["evidence"]:
                    command["evidence"]["sequence"] = command["operation_id"]
            if kind != "ENTRY":
                pos = next(
                    (k, v)
                    for k, v in states[lane]["positions"].items()
                    if v["remaining"] != "0.0" and v["remaining"] != "0"
                )
                command.update(
                    position_id=pos[0], expected_position_revision=pos[1]["revision"]
                )
                if kind == "EXIT":
                    command["quantity"] = quantity or pos[1]["remaining"]
            state, receipt = apply_event(ms[lane], states[lane], command)
            receipt["projection_required"] = False
            row = event_stream_record(
                state["revision"],
                command["operation_id"],
                body(command),
                heads[lane],
                digest([heads[lane], command, receipt]),
                body(receipt),
            )
            states[lane] = state
            heads[lane] = row["digest"]
            counts[lane] += 1
            cut["commits"].append(
                {
                    "lane": lane,
                    "record": row,
                    "commit_ack": {
                        "schema": "EXPLICIT_SYNTHETIC_ACK_NOT_NATIVE",
                        "record_digest": row["digest"],
                    },
                }
            )
            return row

        yield SimpleNamespace(**locals())


def events(s):
    with closing(sqlite3.connect(s.p.state_path)) as db:
        return [
            LifecycleEvent(**json.loads(row[0]))
            for row in db.execute("SELECT event FROM staged ORDER BY offset")
        ]


def dispatch(s, sender, producer=None):
    return asyncio.run(
        (producer or s.p).dispatch_simulated(
            sender=sender, now=datetime.fromtimestamp(s.now[0], UTC)
        )
    )


def test_committed_identity_payload_and_two_account_separation(system):
    s = system
    q = s.append()
    h = s.append("HYPERLIQUID")
    assert s.p.process() == 2
    staged = events(s)
    assert {e.payload["scope"]["currency"] for e in staged} == {"USD", "USDC"}
    assert {e.payload["record_digest"] for e in staged} == {q["digest"], h["digest"]}
    assert len({e.source for e in staged}) == 2 and all(
        e.payload["execution_domain"] == "DISPOSABLE" for e in staged
    )
    fake = FakeSender()
    result = dispatch(s, fake)
    assert result["delivered"] == 2 and len(fake.calls) == 2
    assert s.p.status()["real_discord_enabled"] is False


@pytest.mark.parametrize("when", ["before-delivery", "after-delivery"])
def test_restart_replays_staging_without_requeueing_acknowledged_events(system, when):
    s = system
    s.append()
    s.p.process()
    fake = FakeSender()
    if when == "after-delivery":
        assert dispatch(s, fake)["delivered"] == 1
    other = s.open_producer()
    assert other.process() == 0
    result = dispatch(s, fake, other)
    assert len(fake.calls) == 1 and result["delivered"] == (
        1 if when == "before-delivery" else 0
    )
    assert other.status()["delivery_states"] == {"delivered": 1}


def test_missing_ack_after_simulated_delivery_quarantines_without_resend(
    system, monkeypatch
):
    s = system
    s.append()
    s.p.process()
    fake = FakeSender()

    def failed_ack(*a, **k):
        raise OSError("interrupted durable ACK")

    monkeypatch.setattr(s.p.outbox, "_finish", failed_ack)
    with pytest.raises(OSError):
        dispatch(s, fake)
    assert len(fake.calls) == 1
    s.advance(121)
    other = s.open_producer()
    assert dispatch(s, fake, other)["recovered_expired_leases"] == 1
    assert len(fake.calls) == 1 and other.status()["delivery_states"] == {
        "uncertain": 1
    }


@pytest.mark.parametrize("outcome", [RuntimeError("ambiguous"), None, "truthy"])
def test_unknown_external_outcome_is_never_retried(system, outcome):
    s = system
    s.append()
    s.p.process()
    fake = FakeSender(outcome)
    assert dispatch(s, fake)["uncertain"] == 1
    s.advance(10)
    assert (
        dispatch(s, fake, s.open_producer())["attempted"] == 0 and len(fake.calls) == 1
    )


def test_known_non_delivery_retry_budget_is_durable_and_exhausts(system):
    s = system
    s.append()
    s.p.process()
    fake = FakeSender(False)
    assert dispatch(s, fake)["retry"] == 1
    assert dispatch(s, fake, s.open_producer())["attempted"] == 0
    s.advance(5)
    assert dispatch(s, fake, s.open_producer())["retry"] == 1
    s.advance(30)
    assert dispatch(s, fake, s.open_producer())["dead"] == 1
    s.advance(30)
    assert dispatch(s, fake)["attempted"] == 0 and len(fake.calls) == 3


@pytest.mark.parametrize(
    "damage",
    [
        "duplicate",
        "receipt",
        "source-revision",
        "account",
        "domain",
        "missing-ack",
        "reordered",
        "authority",
        "boolean-proof",
        "mutating-proof",
        "truncation",
    ],
)
def test_unverified_conflicting_or_reordered_commits_fail_closed(system, damage):
    s = system
    s.append()
    s.append("HYPERLIQUID")
    s.p.process()
    before = s.p.state_path.read_bytes()
    if damage == "duplicate":
        s.cut["commits"].append(copy.deepcopy(s.cut["commits"][0]))
    elif damage == "receipt":
        s.cut["commits"][0]["record"]["receipt"] = "{}"
    elif damage == "source-revision":
        s.cut["commits"][0]["record"]["revision"] = 2
    elif damage == "account":
        s.cut["manifests"]["QUALITY_DIPS"]["currency"] = "USDC"
    elif damage == "domain":
        s.cut["execution_domain"] = "OPERATIONAL"
    elif damage == "missing-ack":
        s.cut["commits"][0]["commit_ack"] = {}
    elif damage == "reordered":
        s.cut["commits"].reverse()
    elif damage == "authority":
        s.flags.valid = False
    elif damage == "boolean-proof":
        s.authority.verify_committed = lambda *a, **k: True
    elif damage == "mutating-proof":
        s.flags.mutate = True
    else:
        s.cut["commits"].pop()
    with pytest.raises((LifecycleContractError, ValueError, KeyError)):
        s.p.process()
    assert s.p.state_path.read_bytes() == before


@pytest.mark.parametrize("damage", ["payload", "sequence", "database"])
def test_corrupted_outbox_refuses_restart_without_repair(system, damage):
    s = system
    s.append()
    s.p.process()
    if damage == "database":
        s.p.outbox_path.write_bytes(b"not a sqlite journal")
    else:
        with closing(sqlite3.connect(s.p.outbox_path)) as db:
            db.execute(
                "UPDATE lifecycle_events SET "
                + ("payload_json='{}'" if damage == "payload" else "source_sequence=2")
            )
            db.commit()
    before = s.p.outbox_path.read_bytes()
    with pytest.raises((LifecycleContractError, sqlite3.Error)):
        s.open_producer()
    assert s.p.outbox_path.read_bytes() == before


def test_stop_persists_without_dropping_pending_work(system):
    s = system
    s.append()
    s.p.process()
    s.p.stop()
    fake = FakeSender()
    for p in (s.p, s.open_producer()):
        with pytest.raises(LifecycleContractError):
            dispatch(s, fake, p)
        assert p.status()["stopped"] and p.status()["delivery_states"] == {"pending": 1}
    assert fake.calls == []


def test_stop_during_send_blocks_remaining_transport_and_preserves_true_ack(system):
    s = system
    s.append()
    s.append("HYPERLIQUID")
    s.p.process()

    class Stopping(FakeSender):
        async def __call__(self, **kwargs):
            result = await super().__call__(**kwargs)
            s.p.stop()
            return result

    fake = Stopping()
    result = dispatch(s, fake)
    assert (
        len(fake.calls) == 1 and result["delivered"] == 1 and result["uncertain"] == 1
    )


def test_consent_resubscribe_does_not_revive_old_frozen_recipients(system):
    s = system
    s.append()
    s.p.process()
    s.consent.set_subscription(11, False)
    s.consent.set_subscription(11, True)
    fake = FakeSender()
    assert dispatch(s, fake)["uncertain"] == 1 and not fake.calls


def test_category_scope_is_frozen_before_enqueue(system):
    s = system
    # This test explicitly provisions a separate producer scope at an empty cut.
    s.policy["recipients"]["11"] = ["PAPER_CLOSE"]
    # A scoped policy cannot be mutated after the durable activation watermark.
    other = s.open_producer()
    with pytest.raises(LifecycleContractError):
        other.process()


def test_rate_and_staleness_never_fabricate_delivery(system):
    s = system
    s.append()
    s.p.process()
    s.advance(121)
    fake = FakeSender()
    assert dispatch(s, fake)["uncertain"] == 1 and fake.calls == []


def test_duplicate_ack_cannot_rewrite_an_acknowledged_delivery(system):
    s = system
    s.append()
    s.p.process()
    fake = FakeSender()
    dispatch(s, fake)
    event = events(s)[0]
    assert (
        s.p.outbox._finish(
            event.event_id, "11", "wrong-lease", outcome="delivered", now=s.now[0]
        )
        == "uncertain"
    )
    assert s.p.status()["delivery_states"] == {"delivered": 1}


def test_status_is_read_only_bounded_dashboard_data(system):
    s = system
    s.append()
    s.p.process()
    before = {p.name: p.read_bytes() for p in s.root.iterdir() if p.is_file()}
    view = s.p.status()
    assert view == s.p.status() and json.loads(body(view)) == view
    assert (
        view["schema"] == "ATLAS_NOTIFICATION_STATUS_V1"
        and not view["startup_authorized"]
    )
    assert not view["exactly_once_external_delivery"] and "recipient" not in body(view)
    assert before == {p.name: p.read_bytes() for p in s.root.iterdir() if p.is_file()}


def test_unmarked_transport_is_refused_before_send(system):
    s = system
    s.append()
    s.p.process()

    async def real_looking(**kwargs):
        raise AssertionError("must not enter transport")

    with pytest.raises(LifecycleContractError):
        dispatch(s, real_looking)


def test_legacy_delivery_enqueue_does_not_reset_sent_or_uncertain(system):
    s = system
    adapter = DiscordConsentDeliveryAdapter(
        s.consent, s.root / "isolated-delivery.sqlite3"
    )
    args = {"generation": 1, "database_id": s.consent.consent.database_id}
    assert adapter.enqueue("done", 11, **args) and adapter.dispatch_due(
        "done", 11, lambda: True
    )
    assert adapter.enqueue("done", 11, **args) and not adapter.dispatch_due(
        "done", 11, lambda: True
    )
    assert adapter.enqueue("unknown", 11, **args)
    assert not adapter.dispatch_due("unknown", 11, lambda: None)
    assert not adapter.enqueue("unknown", 11, **args)


def test_missing_or_corrupt_consent_checkpoint_never_reauthorizes(system):
    s = system
    checkpoint = s.consent.consent.checkpoint.path / "scope.json"
    original = checkpoint.read_bytes()
    checkpoint.write_bytes(b"{")
    assert not s.consent.authorized(11, 1)
    with pytest.raises((ConsentStateError, ValueError)):
        s.consent.consent.set_subscription(11, False)
    assert checkpoint.read_bytes() == b"{" and original != b"{"


@pytest.mark.parametrize("system", [{"types": ["PAPER_CLOSE"]}], indirect=True)
def test_positive_category_scope_does_not_backfill_entry_messages(system):
    s = system
    s.append()
    s.p.process()
    fake = FakeSender()
    assert dispatch(s, fake)["attempted"] == 0
    s.append(kind="EXIT")
    s.p.process()
    assert dispatch(s, fake)["delivered"] == 1
    assert [event.event_type for _, event in fake.calls] == ["PAPER_CLOSE"]


@pytest.mark.parametrize("system", [{"rate": 1}], indirect=True)
def test_rate_budget_is_durable_before_fake_transport(system):
    s = system
    s.append()
    s.append("HYPERLIQUID")
    s.p.process()
    fake = FakeSender()
    result = dispatch(s, fake)
    assert (
        result["delivered"] == 1 and result["uncertain"] == 1 and len(fake.calls) == 1
    )
    assert dispatch(s, fake, s.open_producer())["attempted"] == 0


def test_missing_previously_transferred_event_cannot_be_silently_requeued(system):
    s = system
    s.append()
    s.p.process()
    dispatch(s, FakeSender())
    with closing(sqlite3.connect(s.p.outbox_path)) as db:
        db.execute("DELETE FROM lifecycle_deliveries")
        db.execute("DELETE FROM lifecycle_events")
        db.commit()
    before = s.p.outbox_path.read_bytes()
    with pytest.raises(LifecycleContractError, match="transferred"):
        s.open_producer()
    assert s.p.outbox_path.read_bytes() == before


def test_stale_source_receipt_refuses_admission(system):
    s = system
    s.append()
    s.cut["observed_at"] -= 6
    with pytest.raises(LifecycleContractError, match="current"):
        s.p.process()


def test_checkpoint_write_interruption_leaves_consent_quarantined(system, monkeypatch):
    s = system

    def fail(*a, **k):
        raise OSError("checkpoint publication interrupted")

    monkeypatch.setattr(s.consent.consent.checkpoint, "advance", fail)
    with pytest.raises(OSError):
        s.consent.set_subscription(11, False)
    assert s.consent._state(11) == (1, True) and not s.consent.authorized(11, 1)


def test_completed_partial_exit_is_not_mislabelled_as_full_close(system):
    s = system
    s.append("HYPERLIQUID")
    s.append("HYPERLIQUID", "EXIT", "0.2")
    s.p.process()
    rows = events(s)
    assert rows[-1].event_type == "PAPER_MARK" and rows[-1].payload["kind"] == "EXIT"
    assert rows[-1].payload["remaining"] == "0.3"


def test_notification_status_can_be_served_without_transport_or_read_mutation(system):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    s = system
    s.append()
    s.p.process()
    before = {p.name: p.read_bytes() for p in s.root.iterdir() if p.is_file()}
    app = FastAPI()
    app.add_api_route("/notification-status", s.p.status, methods=["GET"])
    with TestClient(app) as client:
        value = client.get("/notification-status").json()
        assert client.get("/notification-status").json() == value
        assert client.post("/notification-status").status_code == 405
    assert (
        value["execution_domain"] == "DISPOSABLE" and not value["real_discord_enabled"]
    )
    assert before == {p.name: p.read_bytes() for p in s.root.iterdir() if p.is_file()}


def test_central_real_discord_sender_still_refuses_before_any_side_effect():
    import ast

    path = Path(__file__).resolve().parents[1] / "backend/app/alerts/discord.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    function = next(
        n
        for n in tree.body
        if isinstance(n, ast.AsyncFunctionDef) and n.name == "send_discord_alert"
    )
    assert isinstance(function.body[0], ast.Return)
    assert (
        isinstance(function.body[0].value, ast.Constant)
        and function.body[0].value.value is False
    )
