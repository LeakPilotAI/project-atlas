"""Composed original contracts with injected Windows/pipe bytes, no workers."""

import copy
import inspect
import ast
import threading
import time
from types import SimpleNamespace

import pytest

from app.services.paper_financial_replay import body, digest
from scripts.observation_runtime.aip06_child_bootstrap import (
    ChildBootstrap,
    InheritedIdentity,
)
from scripts.observation_runtime.aip06_fixture_guard import FixtureGuard
from scripts.observation_runtime.aip06_harness import (
    ROOTS,
    SCOPE_HASH,
    WorkerOwnership,
    need,
)
from scripts.observation_runtime.aip06_ipc import Channel, Broker, RemoteResources
from scripts.observation_runtime.aip06_launch_roles import launch_role
from scripts.observation_runtime.aip06_remote_handles import (
    RetainedPeerHandles,
    RemoteHandleProofs,
)
from scripts.observation_runtime.aip06_pipe_transport import CreditedPipeEndpoint
from scripts.observation_runtime.aip06_native_controller import NativeController
from scripts.observation_runtime.aip06_ownership_probes import OwnershipProbes
from scripts.observation_runtime.aip06_windows_endpoints import WindowsChildEndpoints
from scripts.observation_runtime.launch_ownership import RetainedLaunchBinding
from test_aip06_descendant_closure import fixture, stage, exit_child
from test_aip06_suspended_graph import staged_fixture
from test_aip06_physical_native_proofs import Pipes
from test_aip06_physical_path import probe_fixture, _dmtf
from test_aip06_native_session_stop import EXE
from test_aip06_windows_adapters import ACCOUNTS, Output


@pytest.mark.parametrize(
    "case,role",
    [
        ("direct-worker", "acceptance_worker"),
        ("direct-supervisor", "acceptance_supervisor"),
    ],
)
def test_legacy_actual_guarded_session_binds_formal_launch_role_and_terminal_evidence(
    case, role
):
    x = probe_fixture()
    value = x.c.probe_case(case)
    assert value["ready"]["role"] == role
    bound = next(iter(x.c.legacy_probes.runs.values()))["binding"]
    assert bound.request.role == role and bound.finished and not bound.refused
    assert x.port.all_members() == set()


def test_supervisor_bootstrap_hello_and_guard_role_are_bound_before_target_release():
    from test_aip06_windows_adapters import bootstrap_fixture

    f = bootstrap_fixture(role="acceptance_supervisor")
    f.boot.prepare()
    assert f.boot.guard.launch_role == "acceptance_supervisor"
    result = f.boot.run(lambda path: {"native_acceptance": False})
    assert not result["native_acceptance"] and f.events[-1] == "EXIT"


@pytest.mark.parametrize(
    "damage", ["target", "case", "nonce", "extra", "role-on-financial"]
)
def test_supervisor_role_cannot_be_requested_for_an_unreviewed_launch(damage):
    x = probe_fixture()
    target = x.c.profile["targets"]["query"]
    argv = [EXE, "-B", target, "--case", "direct-supervisor", "--nonce", "a" * 32]
    targets = dict(x.c.profile["targets"])
    if damage == "target":
        targets["query"] = r"D:\foreign.py"
    elif damage == "case":
        argv[4] = "direct-unexpected-extra"
    elif damage == "nonce":
        argv[6] = "wrong"
    elif damage == "extra":
        argv.append("--role=acceptance_supervisor")
    else:
        from dataclasses import replace

        p = x.port.plan([EXE, "-B", x.targets["financial_worker"]], {})
        with pytest.raises(ValueError):
            x.guard.ownership.prepare(
                "financial_worker", replace(p["request"], role="acceptance_supervisor")
            )
        return
    with pytest.raises(ValueError):
        launch_role(argv, targets)


def inherited(z, damage=None):
    """Actual credited transport/Channel/Broker, rooted BIND and remote guard.

    All API results are injected. Child guard factory is an explicit port, not
    an assertion that ChildRuntime's complete native backend ran here.
    """
    x, f = z.x, z.f
    stage(z)
    z.remote.resume_descendant(f.request.nonce, x.calls.native(f.hp))
    api = f.observer_factory(job=f.job, parent=f.parent)
    current = api.observe(f.hp)
    wire = {
        "scope": SCOPE_HASH,
        "session": "a" * 32,
        "nonce": f.request.nonce,
        "parent": f.peer.runtime,
        "child": current,
        "job": f.job,
        "launch": current,
    }
    identity = InheritedIdentity(
        observer=api, current_handle=f.hp, parent_handle=f.parent, job_handle=f.job
    )
    identity.clock = lambda: x.now[0]
    pipes = Pipes(x.calls)
    # These are extra observation-transport allocations, all charged before
    # allocation. The real native installer creates inheritance endpoints
    # before process creation; this fixture does not claim that native proof.
    held = []
    for i in range(4):
        tickets = [
            x.alloc.reserve("qualify-pipe-" + str(i) + "-" + str(j), "pipe")
            for j in range(2)
        ]
        pair = pipes.pair()
        held.extend(zip(tickets, pair, strict=True))
    incoming, outgoing, credit_in, credit_out = [
        tuple(h for _, h in held[i : i + 2]) for i in range(0, 8, 2)
    ]

    def verify(binding):
        need(body(binding) == body(wire), "QUALIFICATION_WIRE_CONFLICT")
        return identity.verify(binding)

    cap = {"data": 65536, "credit": 65536}
    parent_ep = CreditedPipeEndpoint(
        api=pipes,
        read_handle=incoming[0],
        write_handle=outgoing[1],
        credit_read=credit_in[0],
        credit_write=credit_out[1],
        clock_ns=lambda: x.now[0],
        verify_peer=verify,
        session_tag=bytes.fromhex(f.request.nonce),
        capacities=cap,
    )
    child_ep = CreditedPipeEndpoint(
        api=pipes,
        read_handle=outgoing[0],
        write_handle=incoming[1],
        credit_read=credit_out[0],
        credit_write=credit_in[1],
        clock_ns=lambda: x.now[0],
        verify_peer=verify,
        session_tag=bytes.fromhex(f.request.nonce),
        capacities=cap,
    )
    parent = Channel(
        parent_ep,
        binding=wire,
        clock_ns=lambda: x.now[0],
        account_scope=ACCOUNTS,
        role="PARENT",
    )
    child = Channel(
        child_ep,
        binding=wire,
        clock_ns=lambda: x.now[0],
        account_scope=ACCOUNTS,
        role="CHILD",
    )
    output = Output()
    events = []
    box = {}
    target = r"D:\reviewed\child.py"
    pins = {target: "a" * 64}

    def dispatch():
        item = parent.receive(deadline_ns=x.now[0] + 6 * 10**9)
        events.append(item["kind"])
        if item["kind"] == "HELLO":
            local = RetainedLaunchBinding(api, f.request, f.parent, f.hp)
            local.bind_runtime(f.hp, item["payload"])
            z.remote.bind_reserved_process(f.slot, f.owner, local, f.hp)
            z.remote.register_descendant_channel(wire)
            peer = RetainedPeerHandles(
                binding=local,
                resources=z.remote,
                calls=x.calls,
                files=x.files,
                allocations=f.creator,
                allowed_path=lambda path: None,
                objects=f.objects_port,
            )
            box.update(local=local, peer=peer)
            box["broker"] = Broker(
                resources=z.remote,
                channel=parent,
                peer_owner=digest(local.runtime),
                verifier=peer,
                output=output,
                clock_ns=lambda: x.now[0],
            )
            snapshot = copy.deepcopy(z.remote.snapshot)
            if damage == "missing-parent-slot":
                for row in snapshot["state"]["resources"].values():
                    if row["owner"] == f.owner and row["kind"] == "process":
                        row["closed"] = True
            elif damage == "root":
                snapshot["state"]["controller"] = "foreign"
            elif damage == "ancestor-birth":
                snapshot["state"]["owners"][f.owner]["created"] = (
                    current["created"] + 100
                )
            parent.send(
                "BIND",
                {
                    "snapshot": snapshot,
                    "roots": dict(ROOTS),
                    "source_pins": pins,
                    "target": target,
                    "nonce": f.request.nonce,
                },
                deadline_ns=x.now[0] + 6 * 10**9,
            )
        elif item["kind"] == "REQUEST":
            box["broker"].serve_message(item, deadline_ns=x.now[0] + 6 * 10**9)
        elif item["kind"] == "ACK":
            parent.send(
                "RELEASE",
                {
                    "receipt": digest(item["payload"]),
                    "target": target,
                    "sha256": pins[target],
                },
                deadline_ns=x.now[0] + 6 * 10**9,
            )
        elif item["kind"] != "EXIT":
            raise AssertionError(item["kind"])

    # Two independent receive owners model the two real processes. A serial
    # after-write callback cannot drain credits while writing a reply larger
    # than one finite pipe buffer; enlarging that buffer would hide the defect.
    stop = threading.Event()
    condition = threading.Condition()
    until = time.monotonic() + 15
    write, read, available = pipes.write, pipes.read, pipes.available

    def locked_write(h, raw):
        with condition:
            result = write(h, raw)
            condition.notify_all()
            return result

    def locked_read(h, count):
        with condition:
            result = read(h, count)
            condition.notify_all()
            return result

    def locked_available(h):
        with condition:
            return available(h)

    def pause():
        with condition:
            need(
                not stop.is_set() and time.monotonic() < until and "error" not in box,
                "INJECTED_DUPLEX_FIXTURE_WAIT_BOUND",
            )
            condition.wait(0.002)

    pipes.write, pipes.read, pipes.available, pipes.pause = (
        locked_write,
        locked_read,
        locked_available,
        pause,
    )

    def serve():
        try:
            while not stop.is_set() and (not events or events[-1] != "EXIT"):
                dispatch()
        except BaseException as error:
            if not stop.is_set():
                box["error"] = error
            with condition:
                condition.notify_all()

    thread = threading.Thread(target=serve, name="aip06-injected-parent-frames")

    def factory(**kw):
        remote = RemoteResources(
            kw["channel"],
            owner=kw["owner"],
            initial=kw["initial"],
            clock_ns=lambda: x.now[0],
            proofs=RemoteHandleProofs(kw["owner"]),
        )
        return FixtureGuard(
            resources=remote,
            paths=x.guard.paths,
            ownership=WorkerOwnership(remote, all_members=lambda: set()),
            owner=kw["owner"],
            io=x.io,
            processes=SimpleNamespace(),
            clock_ns=lambda: x.now[0],
        )

    boot = ChildBootstrap(
        channel=child,
        identity=identity,
        target=target,
        source_pins=pins,
        verify_source=lambda path: {
            "path": path,
            "file_id": [1, 2, 3],
            "sha256": pins[path],
            "closed": True,
        },
        guard_factory=factory,
        clock_ns=lambda: x.now[0],
    )
    thread.start()
    try:
        boot.prepare()
        boot.run(lambda path: {"domain": "DISPOSABLE", "native_acceptance": False})
        thread.join(1)
        if "error" in box:
            raise box["error"]
    finally:
        stop.set()
        with condition:
            condition.notify_all()
        thread.join(1)
        need(not thread.is_alive(), "INJECTED_FRAME_THREAD_NOT_CLOSED")
    need(
        events[0] == "HELLO" and events[-1] == "EXIT", "QUALIFICATION_FENCED_LIFECYCLE"
    )
    return SimpleNamespace(**locals())


def release(t):
    z = t.z
    x = z.x
    f = z.f
    exit_child(z)
    z.remote.release_descendant(f.request.nonce)
    for key, h in reversed(f.held):
        x.calls.close(h)
        z.remote.close(
            f.owner,
            key,
            observer=SimpleNamespace(closed=lambda owner, k: x.calls.closed(h)),
        )
    x.calls.close(f.hp)
    z.remote.close(
        digest(t.box["local"].runtime),
        f.slot,
        observer=SimpleNamespace(closed=lambda *a: x.calls.closed(f.hp)),
    )
    for key, h in reversed(t.held):
        x.calls.close(h)
        x.alloc.release(key)
    return x


def test_nested_bootstrap_private_physical_frames_preserve_single_root_and_final_release():
    t = inherited(fixture())
    assert t.boot.guard.resources.state["controller"] == t.x.owner != t.f.owner
    assert t.boot.guard.resources.channel is t.child
    assert t.box["local"].runtime == t.current and t.events.count("REQUEST") >= 1
    assert len(t.parent_ep.api.buffers) >= 4 and t.child.sent > 0
    x = release(t)
    assert {r["pid"] for r in t.f.peer.verify()} == {20}
    x.calls.finish(t.f.peer_process.child)
    t.f.peer_process.close()
    x.aggregate.close(deadline_ns=x.now[0] + 10**9)
    assert not x.calls.handles and all(
        r["closed"] for r in x.ledger.state["resources"].values()
    )


@pytest.mark.parametrize("damage", ["missing-parent-slot", "root", "ancestor-birth"])
def test_nested_bootstrap_rejects_unrooted_or_unowned_ancestor(damage):
    with pytest.raises(ValueError):
        inherited(fixture(), damage)


def probes(t, damage=None):
    x = t.x
    c = NativeController.__new__(NativeController)
    c.__dict__.update(x.controller.__dict__)
    c.initialized = True
    c.failed = False
    c.guard = x.guard
    c.process_port = x.port
    c.profile.update(session="a" * 32, accounts=copy.deepcopy(ACCOUNTS))
    x.port.controller = c
    endpoints = WindowsChildEndpoints(
        pipe_calls=t.pipes, clock_ns=lambda: x.now[0], output=t.output
    )
    endpoints.state[t.f.peer.request.nonce] = {
        "closed": False,
        "child": t.f.peer_process.child,
        "port": x.port,
        "verifier": t.z.p,
    }
    x.protocol.endpoints = endpoints

    def read(**kw):
        rows = []
        for p in x.calls.rows.values():
            if p["pid"] in x.calls.exits:
                continue
            rows.append(
                {
                    "ProcessId": p["pid"],
                    "ParentProcessId": p["parent_pid"],
                    "CreationDate": _dmtf(p["created"]),
                    "CommandLine": p["command_line"],
                    "ExecutablePath": p["image"],
                }
            )
        start = x.now[0]
        if damage == "probe-timeout":
            x.now[0] += 6 * 10**9
        return {
            "rows": rows,
            "complete": True,
            "error": None,
            "started_ns": start,
            "finished_ns": x.now[0],
        }

    x.port.ownership_probes = OwnershipProbes(
        x.port, SimpleNamespace(read=read), t.output
    )
    if damage == "supervisor":
        x.calls.rows[10]["created"] += 1
    elif damage == "unexpected":
        x.calls.jobs[x.aggregate.job]["members"].add(999)
    elif damage == "job":
        x.calls.jobs[t.f.job]["members"].discard(t.f.pid)
    one = c.probe_supervisor(deadline_ns=x.now[0] + 5 * 10**9)
    two = c.probe_unexpected_children(deadline_ns=x.now[0] + 5 * 10**9)
    assert {r["pid"] for r in one["descendants"]} == (
        {t.f.peer.runtime["pid"]}
        | ({t.f.pid} if t.f.pid not in x.calls.exits else set())
    )
    return one, two


def test_complete_nested_native_object_probe_accepts_own_child_job_without_confusing_creator_job():
    t = inherited(fixture())
    one, two = probes(t)
    assert one["objects"] and two["case"] == "unexpected-child"
    release(t)
    one, _ = probes(t)
    assert len(one["descendants"]) == 1


def test_partial_descendant_retirement_cannot_be_subtracted_from_peer_inventory():
    t = inherited(fixture())
    z = t.z
    exit_child(z)
    z.remote.release_descendant(z.f.request.nonce)
    wire, broker = z.p.forwarded[z.f.request.nonce]
    with pytest.raises(ValueError, match="RELEASE_INCOMPLETE"):
        z.p.verify_retired_descendant(wire, broker)


@pytest.mark.parametrize("damage", ["supervisor", "unexpected", "job", "probe-timeout"])
def test_nested_probe_refuses_failed_current_source_and_never_grants_stop_success(
    damage,
):
    t = inherited(fixture())
    with pytest.raises(ValueError):
        probes(t, damage)
    assert t.x.aggregate.failed or (t.x.guard.failed and t.x.port.failed)
    assert not t.x.ledger.state["resources"][t.f.slot]["closed"]


def test_full_one_interpreter_composition_is_explicitly_blocked_without_weakening_process_guard(
    tmp_path, monkeypatch
):
    from scripts.observation_runtime.aip06_owned_stop import OwnedStopAssembly
    from test_aip06_physical_path import (
        test_original_three_sample_financial_path_includes_native_query_and_strict_reader_release as original,
    )

    ready = OwnedStopAssembly.ready
    stages = []

    def composed(self, child, **kw):
        ready(self, child, **kw)
        x = self.port._qualification_fixture
        f = staged_fixture(x, child, suffix="-" + str(child.pid))
        t = inherited(fixture(f))
        probes(t)
        stages.append(("inherited", child.pid, t.f.pid))
        release(t)
        assert self.port.all_members() == {child.pid}

    monkeypatch.setattr(OwnedStopAssembly, "ready", composed)
    from test_aip06_physical_path import query_fixture

    def factory(*args, **kw):
        x = query_fixture(*args, **kw)
        x.port._qualification_fixture = x
        return x

    namespace = dict(original.__globals__, query_fixture=factory)
    exec(
        compile(
            ast.parse(inspect.getsource(original)),
            inspect.getsourcefile(original),
            "exec",
        ),
        namespace,
    )
    with pytest.raises(ValueError, match="ONE_FIXTURE_SESSION_ONLY"):
        namespace[original.__name__](tmp_path, None)
    # Component passes cannot turn this refused full composition into PASS.
    assert stages == []


def test_real_parent_bootstrap_escrow_remains_a_specific_unqualified_native_object_boundary():
    from scripts.observation_runtime.aip06_bootstrap_lease import ParentBootstrapLease

    box = {}

    def reserve(x, owner, request):
        lease = ParentBootstrapLease(x.ledger, owner, request.nonce, lambda: x.now[0])
        lease.reserve()
        box["lease"] = lease
        assert "create-suspended" in x.calls.events  # the already-owned parent only
        assert len(x.calls.rows) == 2  # no descendant exists before reservations

    t = inherited(fixture(staged_fixture(before_create=reserve)))
    with pytest.raises(ValueError, match="NATIVE_OBJECT_EVIDENCE_INCOMPLETE"):
        probes(t)
    # This is a preserved source-qualification refusal, not a passing lifecycle.
    assert t.x.guard.failed and not box["lease"].done
    assert all(
        not t.x.ledger.state["resources"][key]["closed"] for key in box["lease"].keys
    )
