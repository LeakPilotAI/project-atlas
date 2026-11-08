"""Offline source closure. No backend load, OS child, native query or acceptance."""

import copy
from types import SimpleNamespace

import pytest

from app.services.paper_financial_replay import digest
from scripts.observation_runtime.aip06_bootstrap_lease import (
    ParentBootstrapLease,
    InheritedBootstrapLease,
    ObserverBatch,
)
from scripts.observation_runtime.aip06_child_entry import main as child_main
from scripts.observation_runtime.aip06_harness import ROOTS, SCOPE_HASH
from scripts.observation_runtime.aip06_native_controller import NativeAllocations
from scripts.observation_runtime.aip06_owned_stop import OwnedStopAssembly
from scripts.observation_runtime.aip06_stop import GuardedStopCollector
from scripts.observation_runtime.aip06_windows_io import AllocationBook
from test_aip06_harness import financial_fixture
from test_aip06_native_session_stop import fixture, EXE
from test_aip06_physical_native_proofs import aggregate_fixture


def lease_fixture():
    x = fixture()
    x.lease = ParentBootstrapLease(x.ledger, x.owner, "a" * 32, lambda: x.now[0])
    descriptor = x.lease.reserve()
    x.binding = {
        "parent": x.parent,
        "child": {**x.parent, "pid": 20, "parent_pid": 10, "created": 20000},
        "nonce": "a" * 32,
    }
    x.client = InheritedBootstrapLease(descriptor, x.binding, lambda: x.now[0])
    return x


def test_startup_allocations_are_precharged_and_local_close_does_not_refund_parent():
    x = lease_fixture()
    before = x.ledger.state["charged_bytes"]
    x.client.reserve(x.client.owner, "actual-local", "handle")
    x.client.close(
        x.client.owner, "actual-local", observer=SimpleNamespace(closed=lambda *a: True)
    )
    assert not any(x.ledger.state["resources"][k]["closed"] for k in x.lease.keys)
    result = x.client.seal()
    assert not result["parent_reservations_released"] and not result["financial_ack"]
    with pytest.raises(ValueError):
        x.client.reserve(x.client.owner, "late", "handle")
    assert x.ledger.state["charged_bytes"] == before


@pytest.mark.parametrize(
    "damage",
    ["expired", "scope", "nonce", "owner", "slots", "duplicate", "entry", "live"],
)
def test_startup_refuses_stale_conflicting_or_unreserved_effects(damage):
    x = lease_fixture()
    d = x.lease.descriptor()
    if damage == "expired":
        x.now[0] = d["expires_ns"]
    elif damage == "scope":
        d["scope"] = "wrong"
    elif damage == "nonce":
        d["nonce"] = "b" * 32
    elif damage == "owner":
        d["parent_owner"] = "foreign"
    elif damage == "slots":
        d["slots"].pop(next(iter(d["slots"])))
    if damage in ("expired", "scope", "nonce", "owner", "slots"):
        with pytest.raises(ValueError):
            InheritedBootstrapLease(d, x.binding, lambda: x.now[0])
    elif damage == "duplicate":
        x.client.reserve(x.client.owner, "same", "handle")
        with pytest.raises(ValueError):
            x.client.reserve(x.client.owner, "same", "handle")
    elif damage == "entry":
        with pytest.raises(ValueError):
            x.client.reserve(x.client.owner, "file", "file", entries=1, size=1)
    else:
        x.client.reserve(x.client.owner, "unclosed", "handle")
        with pytest.raises(ValueError):
            x.client.seal()


def test_observer_prepaid_batch_can_verify_wire_without_recursive_rpc_reservation():
    x = lease_fixture()
    batch = ObserverBatch(x.client)
    allocator = NativeAllocations(batch, x.client.owner, namespace="read-only-observer")
    for i in range(20):
        thread = allocator.reserve("CIM", "thread")
        handles = [allocator.reserve("COM", "handle") for _ in range(7)]
        with pytest.raises(ValueError):
            allocator.reserve("extra", "handle")
        for key in handles + [thread]:
            allocator.release(key)
    serial = batch.serial
    x.client.seal(retained=tuple(batch.slots))
    again = allocator.reserve("fresh-CIM", "thread")
    allocator.release(again)
    assert batch.serial > serial and not batch.live
    batch.finish()
    assert not any(x.ledger.state["resources"][k]["closed"] for k in x.lease.keys)


def test_parent_only_releases_bootstrap_reservations_after_original_exit_or_no_creation():
    x = lease_fixture()
    child = SimpleNamespace(launch_handle=None, creation_attempted=True)
    with pytest.raises(ValueError, match="OUTCOME_UNKNOWN"):
        x.lease.release(calls=x.calls, child=child, deadline_ns=x.now[0] + 10**9)
    child.creation_attempted = False
    out = x.lease.release(calls=x.calls, child=child, deadline_ns=x.now[0] + 10**9)
    assert out["closed"] and not out["financial_ack"]
    assert all(x.ledger.state["resources"][k]["closed"] for k in x.lease.keys)
    assert len(x.lease.done) == 128


@pytest.mark.parametrize(
    "argv,env",
    [
        ([], {}),
        (["--inherited-session", "x"], {}),
        (["--inherited-session", "a" * 32], {}),
        (
            ["--inherited-session", "a" * 32],
            {"ATLAS_AIP06_INHERITED_HANDLES": "1,2,3,4,5,5"},
        ),
        (
            ["--inherited-session", "a" * 32],
            {"ATLAS_AIP06_INHERITED_HANDLES": "-1,2,3,4,5,6"},
        ),
    ],
)
def test_native_entry_refuses_invalid_arguments_before_loading_a_backend(argv, env):
    with pytest.raises(ValueError):
        child_main(argv, env)


def test_account_scoped_allocators_cannot_collide_in_the_one_parent_ledger():
    x = fixture()
    child = {**x.parent, "pid": 20, "parent_pid": 10, "created": 20000}
    other = x.ledger.register_owner(child)
    first = NativeAllocations(x.ledger, x.owner)
    second = NativeAllocations(x.ledger, other)
    a = first.reserve("same", "handle")
    b = second.reserve("same", "handle")
    assert (
        a != b
        and x.ledger.state["resources"][a]["owner"]
        != x.ledger.state["resources"][b]["owner"]
    )
    # IO handles use the same owner fence even though both counters start at 1.
    calls = SimpleNamespace(closed=lambda h: True, close=lambda h: None)
    one = AllocationBook(x.ledger, x.owner, calls, lambda: x.now[0])
    two = AllocationBook(x.ledger, other, calls, lambda: x.now[0])
    k1, h1 = one.open(lambda: 100)
    k2, h2 = two.open(lambda: 101)
    assert k1 != k2
    one.close(k1, h1)
    two.close(k2, h2)


def test_actual_guard_factory_collector_and_original_financial_verifier_complete_three_offline_samples(
    tmp_path,
):
    from test_composed_accounting_risk_recovery import verified
    from test_quality_dips_autonomous_paper import candidate, entry, monitor, setup
    from app.services.paper_financial_replay import replay_verified_events

    q = setup(tmp_path)
    assert entry(q)["filled"]
    assert monitor(q, candidate(q), "partial", "110", {"fundamentals_score": 60})[
        "filled"
    ]
    assert monitor(
        q, candidate(q), "final", "120", {"classification": "THESIS_BROKEN"}
    )["filled"]
    cut = verified(q.ledger)
    pure, _, _ = replay_verified_events(q.m, cut["rows"])
    x = aggregate_fixture()
    events = []

    def socket_cut(**kw):
        events.append("socket")
        n = x.now[0]
        return {
            "scope": SCOPE_HASH,
            "at_ns": n,
            "readers": {
                k: {
                    "complete": True,
                    "owned_endpoints": [],
                    "unknown": False,
                    "started_ns": n,
                    "finished_ns": n,
                }
                for k in ("CIM", "IP_HELPER", "NETSTAT")
            },
        }

    def process_cut(**kw):
        events.append("process")
        assert x.port.all_members() == set()
        return {
            "scope": SCOPE_HASH,
            "started_ns": x.now[0],
            "at_ns": x.now[0],
            "survivors": [],
            "unknown": False,
        }

    def finalize(**kw):
        events.append("release-envelope")
        x.aggregate.close(**kw)

    collector = GuardedStopCollector(
        clock_ns=lambda: x.now[0],
        output=SimpleNamespace(append=lambda v: events.append("output")),
        sockets=SimpleNamespace(collect=socket_cut),
        processes=SimpleNamespace(collect=process_cut),
        close_io=lambda: None,
        finalize_resources=finalize,
    )
    base = financial_fixture()
    base["accounts"] = {
        k: v for k, v in base["accounts"].items() if k == "QUALITY_DIPS"
    }
    base["acknowledgements"] = {
        k: v for k, v in base["acknowledgements"].items() if k == "QUALITY_DIPS"
    }
    account = base["accounts"]["QUALITY_DIPS"]
    account.update(
        manifest=q.m, events=cut["rows"], snapshot=pure, source_head=cut["head"]
    )
    ack = {
        "account_id": account["account_id"],
        "epoch": q.m["epoch"],
        "currency": "USD",
        "revision": 3,
        "head": cut["head"],
        "state_digest": digest(pure),
        "native_source": account["native_source"],
    }
    base["acknowledgements"]["QUALITY_DIPS"] = {
        stage: copy.deepcopy(ack)
        for stage in ("source", "projection", "report", "global")
    }
    params = lambda: {k: copy.deepcopy(account[k]) for k in ("account_id", "manifest")}
    assembly = OwnedStopAssembly(x.port, collector, fixture_parameters=params)
    x.port.stop_assembly = assembly

    def ready(session, **kw):
        root = assembly.active["root"]
        native = copy.deepcopy(account)
        x.io.add(root + "\\account", "directory")
        x.io.add(root + "\\account\\source", "directory")
        fid = x.io.rows[root + "\\account\\source"]["id"]
        native = {
            "account_id": account["account_id"],
            "epoch": account["manifest"]["epoch"],
            "resources": {
                "source": {"path": root + "\\account\\source", "native_id": fid}
            },
        }
        x.protocol.financial = copy.deepcopy(base)
        x.protocol.financial["accounts"]["QUALITY_DIPS"]["native_source"] = (
            copy.deepcopy(fid)
        )
        for row in x.protocol.financial["acknowledgements"]["QUALITY_DIPS"].values():
            row["native_source"] = copy.deepcopy(fid)
        actual = session.binding.runtime
        return {
            "phase": "READY",
            "timing_channel": session.plan["request"].nonce,
            "identity": {
                "pid": actual["pid"],
                "creation_filetime": actual["created"],
                "image": actual["image"],
            },
            "value": {
                "native": native,
                "manifest": account["manifest"],
                "source_revision": 2,
            },
        }

    x.protocol.financial_ready = ready
    x.protocol.readback_input = lambda *a, **kw: {}
    previous_cpu = 0
    charges = []
    with x.guard.installed():
        x.guard.mkdir(ROOTS["T"])
        for sample in (1, 2, 3):
            result = x.guard.run_owned_stop_sample(sample, ROOTS["T"])
            assert (
                result["source_contract_passed"]
                and result["native_acceptance"] is False
            )
            assert result["cash_by_lane"] == {"QUALITY_DIPS": "1015.9136"}
            assert x.aggregate.dormant and not x.aggregate.held and not x.calls.handles
            assert x.ledger.state["cpu_ns"] >= previous_cpu
            previous_cpu = x.ledger.state["cpu_ns"]
            charges.append(x.ledger.state["charged_bytes"])
            assert all(r["closed"] for r in x.ledger.state["resources"].values())
        assert charges[0] < charges[1] < charges[2] and x.aggregate.generation == 2
        assert events == ["socket", "process", "output", "release-envelope"] * 3
        with pytest.raises(ValueError):
            x.guard.run_owned_stop_sample(4, ROOTS["T"])


@pytest.mark.parametrize("state", ["FAILED", "PENDING"])
def test_failed_or_incomplete_sample_cannot_rearm_an_envelope(state):
    x = aggregate_fixture()
    x.aggregate.close(deadline_ns=x.now[0] + 10**9)
    x.ledger._state["stops"]["unresolved"] = {"request": "a" * 64, "state": state}
    with pytest.raises(ValueError):
        x.aggregate.rearm(2)


@pytest.mark.parametrize("when", ["before-create", "after-create"])
def test_failed_inheritance_restoration_retains_original_creation_outcome(
    monkeypatch, when
):
    import os
    import _winapi
    from scripts.observation_runtime.aip06_windows_process import (
        Win32ProcessCalls,
        SuspendedLaunchFailure,
    )

    flags = {11: False, 12: True}
    events = []

    def set_flag(h, value):
        events.append((h, value))
        if h == 11 and value is False:
            raise OSError("injected restore refusal")
        flags[h] = value

    def create(*a):
        if when == "before-create":
            raise OSError("injected CreateProcess refusal")
        return (101, 102, 20, 21)

    monkeypatch.setattr(os, "get_handle_inheritable", lambda h: flags[h])
    monkeypatch.setattr(os, "set_handle_inheritable", set_flag)
    monkeypatch.setattr(_winapi, "CreateProcess", create)
    with pytest.raises(SuspendedLaunchFailure) as raised:
        Win32ProcessCalls.create_suspended(
            object(),
            executable=EXE,
            argv=[EXE, "-B", "exact.py"],
            environment={},
            cwd="D:\\reviewed",
            inherit_handles=[11, 12],
            stdin=11,
            stdout=12,
            stderr=12,
        )
    assert raised.value.created == (
        None if when == "before-create" else (101, 102, 20, 21)
    )
    assert len(raised.value.restore_errors) == 1 and flags[12] is True
    assert (12, True) in events


def test_guard_aborts_the_original_suspended_child_when_inheritance_restore_fails():
    from scripts.observation_runtime.aip06_windows_process import SuspendedLaunchFailure

    x = fixture()
    create = x.calls.create_suspended

    def fail(**kw):
        original = create(**kw)
        raise SuspendedLaunchFailure(
            created=original, cause=None, restore_errors=[OSError("injected")]
        )

    x.calls.create_suspended = fail
    with pytest.raises(SuspendedLaunchFailure), x.guard.installed():
        x.guard.spawn([EXE, "-B", x.targets["financial_worker"]])
    assert not x.calls.handles and x.port.failed
    assert "terminate-original-created-handle" in x.calls.events
    assert "resume" not in x.calls.events and "release" not in x.protocol.events


def test_partial_physical_pipe_bootstrap_releases_escrow_without_creating_a_child():
    from test_aip06_physical_native_proofs import Pipes
    from scripts.observation_runtime.aip06_windows_endpoints import (
        WindowsChildEndpoints,
    )

    x = fixture()
    pipes = Pipes(x.calls)
    ep = WindowsChildEndpoints(
        pipe_calls=pipes,
        clock_ns=lambda: x.now[0],
        output=SimpleNamespace(append=lambda v: None),
    )
    count = [0]

    def pair():
        count[0] += 1
        if count[0] == 2:
            raise OSError("injected second pipe refusal")
        return pipes.pair()

    x.calls.pipe = pair
    x.protocol.resource_kinds = ep.resource_kinds
    x.protocol.command = ep.command
    x.protocol.prepare = ep.prepare
    x.protocol.close = ep.close
    x.protocol.closed = ep.closed
    with pytest.raises(OSError), x.guard.installed():
        x.guard.spawn([EXE, "-B", x.targets["financial_worker"]])
    state = next(iter(ep.state.values()))
    assert state["closed"] and len(state["lease"].done) == 128
    assert not x.calls.handles and "create-suspended" not in x.calls.events
    assert all(x.ledger.state["resources"][k]["closed"] for k in state["lease"].keys)
    before = x.ledger.head
    ep.close(x.port.sessions[0], deadline_ns=x.now[0] + 10**9)
    assert x.ledger.head == before


@pytest.mark.parametrize("damage", ["identity", "cpu", "reservation", "failed"])
def test_closed_envelope_cannot_admit_new_effects_or_reset_failed_usage(damage):
    x = aggregate_fixture()
    x.aggregate.close(deadline_ns=x.now[0] + 10**9)
    if damage == "identity":
        x.calls.rows[10]["created"] += 1
    elif damage == "cpu":
        x.calls.usage = lambda h: (0, 121 * 10**9)
    elif damage == "reservation":
        x.ledger.reserve(x.owner, "unreleased", "job")
    else:
        x.aggregate.failed = True
    with pytest.raises(ValueError):
        x.aggregate.rearm(2)


def test_child_descendant_path_refuses_before_an_unguarded_creation():
    from scripts.observation_runtime.aip06_child_entry import ChildServices

    services = ChildServices(SimpleNamespace(), SimpleNamespace())
    with pytest.raises(ValueError, match="STAGED_DESCENDANT_GATEWAY"):
        services.plan([EXE, "-B", "D:\\reviewed\\worker.py"], {})
    assert services.descendant_gateway is None


@pytest.mark.parametrize("damage", [None, "root", "release", "source", "identity"])
def test_actual_child_factory_uses_prepaid_bootstrap_and_same_parent_rpc_cut(damage):
    import hashlib
    from scripts.observation_runtime.aip06_child_entry import ChildRuntime
    from test_aip06_windows_adapters import bootstrap_fixture, FileResponses

    f = bootstrap_fixture("release" if damage == "release" else None)
    x = f.x
    now = lambda: x.s.now[0]
    parent = x.s.ledger.state["controller"]
    escrow = ParentBootstrapLease(x.s.ledger, parent, "b" * 32, now)
    lease = InheritedBootstrapLease(escrow.reserve(), x.child_channel.binding, now)
    # The old helper builds its test broker early. The physical provider builds
    # Broker only after escrow/launch at BIND, with this exact current cut.
    f.broker.peer_head = x.s.ledger.head
    files = FileResponses()
    files.rows[f.target] = {
        "path": f.target,
        "parent_id": [1, 799, 0],
        "id": [1, 800, 0],
        "kind": "file",
        "links": 1,
        "reparse": False,
    }
    files.raw[f.target] = b"OFFLINE_PINNED_TARGET_NOT_NATIVE_EXECUTION"
    files.open_image = files.allocate
    pin = hashlib.sha256(files.raw[f.target]).hexdigest()
    f.pins[f.target] = pin
    f.boot.pins[f.target] = pin
    runtime = ChildRuntime(
        files=files,
        calls=SimpleNamespace(),
        cim_api=SimpleNamespace(),
        pipes=SimpleNamespace(),
        clock_ns=now,
    )
    runtime.validated = True
    runtime.identity = f.identity
    if damage=='identity':runtime.identity=None
    runtime.lease = lease
    runtime.observer_batch = ObserverBatch(lease)
    runtime.bootstrap_book = runtime.book = AllocationBook(lease, x.owner, files, now)
    runtime.self_key, runtime.self_handle = runtime.book.open(files.open_drive)
    runtime.descriptor = {
        "root_bindings": {},
        "sid": "owner",
        "argv": [EXE, "-B", f.target],
        "images": {},
        "source_pins": f.pins,
        "targets": {"readonly_reader": f.target},
    }
    if damage == "root":
        runtime.descriptor["root_bindings"]["T"] = {
            "path": ROOTS["T"],
            "id": [1, 900, 0],
            "parent_id": [1, 999, 0],
            "kind": "directory",
            "links": 1,
            "reparse": False,
        }
    if damage == "source":
        files.raw[f.target] = b"CHANGED"
    f.boot.factory = runtime.guard_factory
    f.boot.verify_source = runtime.verify_source
    before = x.s.ledger.head
    ran = []
    if damage:
        with pytest.raises(ValueError):
            f.boot.prepare()
            f.boot.run(lambda p: ran.append(p))
        assert not ran
    else:
        receipt = f.boot.prepare()
        assert receipt["reservation_head"] == before == x.s.ledger.head
        assert (
            runtime.lease.sealed and f.boot.guard.resources.channel is x.child_channel
        )
        result = f.boot.run(lambda p: ran.append(p) or {"native_acceptance": False})
        assert not result["native_acceptance"] and ran == [f.target]
        assert f.events[0] == "HELLO" and f.events[-1] == "EXIT"
        assert runtime.guard.paths.port is runtime.guard.io
    # Only the independently retained startup duplicate and observer envelope
    # can remain locally; neither refunds the parent's precharged reservations.
    runtime.bootstrap_book.close(runtime.self_key, runtime.self_handle)
    runtime.observer_batch.finish()
    assert not files.handles
    assert all(not x.s.ledger.state["resources"][k]["closed"] for k in escrow.keys)
