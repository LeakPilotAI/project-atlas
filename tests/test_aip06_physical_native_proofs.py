"""Actual source providers over injected Windows responses; no native launch."""

import copy
import ctypes as C
import struct
import socket
from dataclasses import replace
from types import SimpleNamespace

import pytest

from app.services.paper_financial_replay import digest
from scripts.observation_runtime.aip06_child_bootstrap import InheritedIdentity
from scripts.observation_runtime.aip06_cleanup_providers import (
    CimSockets,
    CimTables,
    GuardedNetstat,
    StrictProcessCleanup,
    TcpTables,
    ThreeReaderCleanup,
)
from scripts.observation_runtime.aip06_harness import LIMITS, SCOPE_HASH
from scripts.observation_runtime.aip06_job_budget import AggregateJobBudget
from scripts.observation_runtime.aip06_native_objects import (
    DeclaredDescendants,
    UnicodeString,
    WindowsObjectCalls,
)
from scripts.observation_runtime.aip06_remote_handles import (
    RemoteHandleProofs,
    RetainedPeerHandles,
)
from scripts.observation_runtime.aip06_windows_endpoints import (
    InheritedChannel,
    WindowsChildEndpoints,
)
from scripts.observation_runtime.launch_ownership import RetainedLaunchBinding
from test_aip06_native_session_stop import EXE, fixture
from test_aip06_windows_adapters import ACCOUNTS, CimResponses
from test_launch_ownership import setup


def aggregate_fixture():
    x = fixture()
    x.calls.usage = lambda h: (x.memory.get(x.calls.native(h)["pid"], 0), 0)
    x.memory = {10: 32 * 1024**2}
    x.cpu = {"user_ns": 100, "kernel_ns": 200, "terminated": 0}
    x.calls.job_accounting = lambda job: {
        **x.cpu,
        "active": len(x.calls.members(job)),
        "total": len(x.calls.rows),
    }
    x.aggregate = AggregateJobBudget(
        calls=x.calls,
        resources=x.ledger,
        allocations=x.alloc,
        clock_ns=lambda: x.now[0],
    )
    x.aggregate.initialize()
    x.port.aggregate = x.aggregate
    old_finish = x.calls.finish

    def finish(child):
        pid = x.calls.native(child.launch_handle)["pid"]
        old_finish(child)
        x.calls.jobs[x.aggregate.job]["members"].discard(pid)

    x.calls.finish = finish
    return x


def test_aggregate_envelope_includes_controller_and_nested_child_and_preserves_restart_cpu():
    x = aggregate_fixture()
    child = x.guard.spawn([EXE, "-B", x.targets["financial_worker"]])
    assert x.calls.members(x.aggregate.job) == {10, child.pid}
    assert x.aggregate.observe()["memory"].keys() == x.ledger.state["memory"].keys()
    x.cpu.update(user_ns=500)
    child.communicate()
    assert x.aggregate.observe()["memory"] == {x.owner: x.memory[10]}
    again = x.guard.spawn([EXE, "-B", x.targets["readonly_reader"]])
    assert x.aggregate.observe()["cpu_ns"] == 700
    again.communicate()
    out = x.aggregate.close(deadline_ns=x.now[0] + 10**9)
    assert out["owned_handles_closed"] and not out["financial_ack"]
    assert all(
        x.ledger.state["resources"][k]["closed"] for k in x.aggregate.closed_keys
    )


@pytest.mark.parametrize(
    "damage",
    [
        "root_member",
        "memory",
        "cpu",
        "cpu_rollback",
        "birth",
        "terminated",
        "missing_member",
        "per_child",
    ],
)
def test_aggregate_refuses_overuse_even_with_compliant_leaf_limits(damage):
    x = aggregate_fixture()
    child = x.guard.spawn([EXE, "-B", x.targets["financial_worker"]])
    if damage == "root_member":
        x.calls.jobs[x.aggregate.job]["members"].add(999)
    elif damage == "memory":
        x.memory.update({10: LIMITS["private_bytes"] - 1, child.pid: 2})
    elif damage == "cpu":
        x.cpu.update(kernel_ns=LIMITS["cpu_ns"])
    elif damage == "cpu_rollback":
        x.cpu.update(kernel_ns=0, user_ns=0)
    elif damage == "birth":
        x.calls.rows[child.pid]["created"] += 1
    elif damage == "terminated":
        x.cpu["terminated"] = 1
    elif damage == "missing_member":
        x.calls.jobs[x.aggregate.job]["members"].remove(child.pid)
    else:
        x.memory[child.pid] = LIMITS["child_private_bytes"] + 1
    with pytest.raises(ValueError):
        x.aggregate.observe()
    assert x.aggregate.failed
    with pytest.raises(ValueError, match="LATCHED"):
        x.aggregate.observe()


def test_aggregate_initial_assignment_failure_is_not_a_pass_or_refund():
    x = fixture()
    x.calls.fail = "assign"
    budget = AggregateJobBudget(
        calls=x.calls,
        resources=x.ledger,
        allocations=x.alloc,
        clock_ns=lambda: x.now[0],
    )
    with pytest.raises(OSError):
        budget.initialize()
    assert budget.failed and budget.held
    assert all(not x.ledger.state["resources"][key]["closed"] for key, _ in budget.held)


def test_aggregate_counts_pre_assignment_controller_cpu_prefix_without_double_counting_job_cpu():
    x = aggregate_fixture()
    x.calls.usage = lambda h: (32 * 1024**2, LIMITS["cpu_ns"] + 1)
    with pytest.raises(ValueError, match="CPU_LIMIT"):
        x.aggregate.observe()


@pytest.mark.parametrize("where", ["root", "leaf"])
def test_aggregate_rechecks_effective_job_limits_after_launch(where):
    x = aggregate_fixture()
    child = x.guard.spawn([EXE, "-B", x.targets["financial_worker"]])
    job = x.aggregate.job if where == "root" else child.child.job
    x.calls.jobs[job]["limits"]["private_bytes"] += 1
    with pytest.raises(ValueError, match="LIMIT_CONFIGURATION_CHANGED"):
        x.aggregate.observe()


def test_aggregate_retains_terminated_child_cpu_after_handle_close():
    x = aggregate_fixture()
    amounts = {10: 500, 20: 600}
    x.calls.usage = lambda h: (32 * 1024**2, amounts.get(x.calls.native(h)["pid"], 0))
    child = x.guard.spawn([EXE, "-B", x.targets["financial_worker"]])
    assert x.aggregate.observe()["cpu_ns"] == 1100
    child.communicate()
    assert x.aggregate.observe()["cpu_ns"] == 1100


class Pipes:
    """In-memory Win32 byte/credit responses, never real anonymous pipes."""

    def __init__(self, calls):
        self.calls, self.buffers, self.writers = calls, {}, {}
        self.capacity_value = 65536

    def pair(self):
        r, w = self.calls.allocate("pipe"), self.calls.allocate("pipe")
        self.buffers[r] = bytearray()
        self.writers[w] = r
        return r, w

    def capacity(self, h):
        return self.capacity_value

    def available(self, h):
        return len(self.buffers[h])

    def write(self, h, raw):
        self.buffers[self.writers[h]].extend(raw)
        return len(raw)

    def read(self, h, count):
        value = bytes(self.buffers[h][:count])
        del self.buffers[h][:count]
        return value

    def pause(self):
        raise AssertionError("Unexpected wait: fixture evidence missing")


def endpoints_fixture():
    x = fixture()
    x.controller.profile.update(session="a" * 32, accounts=copy.deepcopy(ACCOUNTS))
    x.pipes = Pipes(x.calls)
    x.calls.pipe = x.pipes.pair
    x.records = []
    x.ep = WindowsChildEndpoints(
        pipe_calls=x.pipes,
        clock_ns=lambda: x.now[0],
        output=SimpleNamespace(append=x.records.append),
    )
    x.protocol.resource_kinds = x.ep.resource_kinds
    x.protocol.command = x.ep.command
    x.protocol.prepare = x.ep.prepare
    x.child = x.guard.spawn([EXE, "-B", x.targets["financial_worker"]])
    x.session = x.child.child
    return x


def test_physical_pipe_provider_uses_exact_reserved_handles_and_real_channel_frames():
    x = endpoints_fixture()
    parent = x.ep.channel(x.session, x.session.binding.runtime)
    state = x.ep._state(x.session)
    observer = SimpleNamespace(
        job=x.session.job,
        parent=x.session.parent_handle,
        observe=lambda h: (
            x.session.binding.parent
            if h == x.session.parent_handle
            else x.session.binding.runtime
        ),
        members=lambda: {x.child.pid},
    )
    identity = InheritedIdentity(
        observer=observer,
        current_handle=9999,
        parent_handle=x.session.parent_handle,
        job_handle=x.session.job,
    )
    peer, descriptor = InheritedChannel.open(
        handles=state["peer"] + (x.session.parent_handle, x.session.job),
        nonce=x.session.plan["request"].nonce,
        pipes=x.pipes,
        identity=identity,
        clock_ns=lambda: x.now[0],
    )
    assert descriptor["argv"] == list(x.session.argv)
    assert set(descriptor["handles"]) <= {
        v["handle"] for v in x.session.native.values()
    }
    peer.send("HELLO", {"genuine_fixture_frame": True}, deadline_ns=x.now[0] + 10**9)
    assert parent.receive(deadline_ns=x.now[0] + 10**9, expected_kind="HELLO")[
        "payload"
    ] == {"genuine_fixture_frame": True}
    # Same packet cannot satisfy a second frame or be interpreted as financial ACK.
    peer.send("OUTPUT", {"value": "fixture"}, deadline_ns=x.now[0] + 10**9)
    peer.send("DRAIN", {"unexpected": True}, deadline_ns=x.now[0] + 10**9)
    with pytest.raises(ValueError, match="UNEXPECTED_SESSION_FRAME"):
        parent.receive(deadline_ns=x.now[0] + 10**9, expected_kind="ACK")
    assert x.records[-1]["schema"] == "AIP06_CHILD_FRAME_V1"


@pytest.mark.parametrize(
    "damage", ["capacity", "nonce", "handles", "identity", "descriptor"]
)
def test_physical_inherited_bootstrap_refuses_ambiguous_or_conflicting_input(damage):
    x = endpoints_fixture()
    if damage == "capacity":
        x.ep._state(x.session)["capacities"]["data"] = 1
        with pytest.raises(ValueError):
            x.ep.channel(x.session, x.session.binding.runtime)
        return
    x.ep.channel(x.session, x.session.binding.runtime)
    state = x.ep._state(x.session)
    observer = SimpleNamespace(
        job=x.session.job,
        parent=x.session.parent_handle,
        observe=lambda h: (
            x.session.binding.parent
            if h == x.session.parent_handle
            else x.session.binding.runtime
        ),
        members=lambda: {999} if damage == "identity" else {x.child.pid},
    )
    identity = InheritedIdentity(
        observer=observer,
        current_handle=9999,
        parent_handle=x.session.parent_handle,
        job_handle=x.session.job,
    )
    handles = state["peer"] + (x.session.parent_handle, x.session.job)
    if damage == "handles":
        handles = handles[:5] + (handles[0],)
    if damage == "descriptor":
        data = x.pipes.buffers[handles[0]]
        data[:4] = struct.pack("!I", 65537)
    with pytest.raises(ValueError):
        InheritedChannel.open(
            handles=handles,
            nonce="wrong" if damage == "nonce" else x.session.plan["request"].nonce,
            pipes=x.pipes,
            identity=identity,
            clock_ns=lambda: x.now[0],
        )


def test_pipe_close_refuses_live_child_and_does_not_close_session_handles():
    x = endpoints_fixture()
    before = set(x.calls.handles)
    with pytest.raises(ValueError, match="ORIGINAL_CHILD_EXIT"):
        x.ep.close(x.session, deadline_ns=x.now[0] + 10**9)
    assert set(x.calls.handles) == before
    x.calls.finish(x.session)
    x.ep.close(x.session, deadline_ns=x.now[0] + 10**9)
    assert set(x.calls.handles) == before


@pytest.mark.parametrize(
    "kind",
    [
        "Event",
        "Mutant",
        "Semaphore",
        "Timer",
        "Thread",
        "Process",
        "Token",
        "Job",
        "File",
    ],
)
def test_concrete_object_observer_preserves_typed_native_identity(kind):
    calls = WindowsObjectCalls.__new__(WindowsObjectCalls)
    calls.type_name = lambda h: kind

    def times(h, *args):
        args[0]._obj.dwLowDateTime = 123
        return True

    calls.k = SimpleNamespace(
        GetProcessIdOfThread=lambda h: 20,
        GetThreadId=lambda h: 21,
        GetThreadTimes=times,
        GetFileType=lambda h: 1,
    )
    calls.processes = SimpleNamespace(
        check=lambda v: v,
        native=lambda h: {"pid": 20, "created": 123, "image": EXE},
        lifecycle=lambda h: {
            "pid": 20,
            "created": 123,
            "exited": False,
            "exit_code": 259,
        },
        members=lambda h: {20},
        job_limits=lambda h: dict(LIMITS),
    )
    calls.files = SimpleNamespace(
        token_identity=lambda h: {"sid": "fixture", "type": 1},
        describe=lambda h: {
            "kind": "file",
            "links": 1,
            "reparse": False,
            "id": [1, 2, 3],
        },
        final_path=lambda h: r"D:\fixture",
    )
    value = calls.observe(100)
    assert value["type"] == kind
    if kind == "Thread":
        assert value["pid"] == 20 and value["created"] == 123


@pytest.mark.parametrize("kind", ["Socket", "Unknown", "ALPC Port"])
def test_unknown_or_socket_kernel_objects_are_not_treated_as_generic_handles(kind):
    calls = WindowsObjectCalls.__new__(WindowsObjectCalls)
    calls.type_name = lambda h: kind
    with pytest.raises(ValueError, match="UNSUPPORTED_NATIVE_OBJECT"):
        calls.observe(100)


def test_descendant_proof_preserves_original_handles_and_rejects_foreign_parent():
    api, request, ready = setup()
    api.rows[1] = api.rows.pop("parent")
    api.rows[2] = api.rows.pop("launch")
    request = replace(request, role="acceptance_worker")
    ready["role"] = request.role
    bound = RetainedLaunchBinding(api, request, 1, 2)
    bound.bind_runtime(2, ready)
    api.job = 55
    proofs = RemoteHandleProofs(digest(bound.parent))
    proof = proofs.child(bound, 2)
    assert proof["parent"] == 1 and proof["launch"] == 2
    with pytest.raises(ValueError, match="EXACT_PARENT"):
        RemoteHandleProofs("foreign").child(bound, 2)


def test_descendant_transfer_requires_prior_exact_declaration_before_any_duplicate():
    api, req, ready = setup()
    parent = RetainedLaunchBinding(api, req, "parent", "launch")
    parent.bind_runtime("launch", ready)
    calls = SimpleNamespace(duplicate=lambda *a: pytest.fail("No undeclared duplicate"))
    registry = DeclaredDescendants(
        peer=parent,
        calls=calls,
        objects=None,
        allocations=None,
        observer_factory=None,
        aggregate=None,
    )
    with pytest.raises(ValueError, match="DECLARATION"):
        registry.import_binding(
            {
                "nonce": "a" * 32,
                "parent": 1,
                "launch": 2,
                "runtime": 2,
                "job": 3,
                "ready": {},
            }
        )


def test_real_nested_job_shape_is_still_blocked_before_descendant_adoption():
    """Records the unresolved staging connection; never filters a native member."""
    x = fixture()
    api, req, ready = setup()
    parent = RetainedLaunchBinding(api, req, "parent", "launch")
    parent.bind_runtime("launch", ready)
    owner = x.ledger.register_owner(parent.runtime)
    x.ledger.reserve(owner, "descendant-before-create", "launch")
    child_request = replace(req, role="acceptance_worker", nonce="c" * 32)
    duplicates = []
    registry = DeclaredDescendants(
        peer=parent,
        calls=SimpleNamespace(duplicate=lambda *a: duplicates.append(a)),
        objects=None,
        allocations=None,
        observer_factory=None,
        aggregate=None,
    )
    registry.declare(
        child_request,
        slot="descendant-before-create",
        parent_owner=owner,
        resources=x.ledger,
    )
    # A real Windows descendant inherits its parent's non-breakaway Job chain.
    api.pids.add(40)
    with pytest.raises(ValueError, match="JOB_PROCESS"):
        registry.import_binding(
            {
                "nonce": child_request.nonce,
                "parent": 1,
                "launch": 2,
                "runtime": 2,
                "job": 3,
                "ready": {
                    "pid": 40,
                    "nonce": child_request.nonce,
                    "role": child_request.role,
                },
            }
        )
    assert not duplicates and registry.failed


@pytest.mark.parametrize("damage", [None, "status", "length", "pointer", "size"])
def test_native_object_type_query_checks_status_buffer_and_pointer_before_decoding(
    damage,
):
    def type_query(handle, info, raw, capacity, count):
        if damage == "status":
            return -1
        text = "Event".encode("utf-16-le")
        n = C.sizeof(UnicodeString)
        value = UnicodeString.from_buffer(raw)
        value.length = len(text) if damage != "length" else 999
        value.maximum = len(text)
        value.buffer = C.addressof(raw) + n if damage != "pointer" else 1
        C.memmove(C.addressof(raw) + n, text, len(text))
        count._obj.value = n + len(text) if damage != "size" else capacity + 1
        return 0

    kernel = SimpleNamespace(
        **{
            name: (lambda *a: True)
            for name in (
                "CompareObjectHandles",
                "GetThreadId",
                "GetProcessIdOfThread",
                "GetThreadTimes",
                "GetFileType",
                "GetNamedPipeInfo",
            )
        }
    )
    native = WindowsObjectCalls(
        kernel,
        SimpleNamespace(NtQueryObject=type_query),
        process_calls=None,
        files=None,
    )
    if damage is None:
        assert native.type_name(123) == "Event"
    else:
        with pytest.raises(ValueError):
            native.type_name(123)


@pytest.mark.parametrize(
    "kind",
    [
        "Event",
        "Thread",
        "Token",
        "foreign_thread",
        "foreign_token",
        "unknown",
        "object_changed",
    ],
)
def test_remote_native_objects_require_original_peer_and_independent_object_continuity(
    kind,
):
    x = fixture()
    child = x.guard.spawn([EXE, "-B", x.targets["financial_worker"]])
    owner = digest(child.child.binding.runtime)
    x.ledger.reserve(owner, "remote-object", "handle")
    local = set()

    def duplicate(source, handle):
        assert source == child.child.binding.runtime_handle and handle == 999
        h = 500 + len(local)
        local.add(h)
        return h

    calls = SimpleNamespace(
        duplicate=duplicate,
        close=lambda h: local.remove(h),
        closed=lambda h: h not in local,
    )
    described = {"type": kind}
    if kind in ("Thread", "foreign_thread"):
        described = {"type": "Thread", "pid": child.pid if kind == "Thread" else 999}
    if kind in ("Token", "foreign_token"):
        described = {
            "type": "Token",
            "sid": "owner" if kind == "Token" else "foreign",
            "token_type": 1,
        }
    if kind == "object_changed":
        described = {"type": "Event"}
    objects = SimpleNamespace(
        observe=lambda h: described, same=lambda *a: kind != "object_changed"
    )
    proofs = RetainedPeerHandles(
        binding=child.child.binding,
        resources=x.ledger,
        calls=calls,
        files=None,
        allocations=x.alloc,
        allowed_path=lambda p: None,
        objects=objects,
        sid="owner",
    )
    wire = {"parent": child.child.binding.parent, "child": child.child.binding.runtime}
    if kind in ("foreign_thread", "foreign_token", "unknown", "object_changed"):
        with pytest.raises(ValueError):
            proofs.bind_native_handle(wire, "remote-object", 999)
        assert (
            proofs.failed and not x.ledger.state["resources"]["remote-object"]["closed"]
        )
    else:
        proofs.bind_native_handle(wire, "remote-object", 999)
        assert proofs.live["remote-object"]["verified"] and len(local) == 1


def test_com_release_declaration_keeps_budget_live_until_independent_original_peer_exit():
    x = fixture()
    child = x.guard.spawn([EXE, "-B", x.targets["financial_worker"]])
    owner = digest(child.child.binding.runtime)
    x.ledger.reserve(owner, "remote-com-pointer", "handle")
    proofs = RetainedPeerHandles(
        binding=child.child.binding,
        resources=x.ledger,
        calls=x.calls,
        files=x.files,
        allocations=x.alloc,
        allowed_path=lambda p: None,
    )
    wire = {"parent": child.child.binding.parent, "child": child.child.binding.runtime}
    ack = proofs.defer_native_release(wire, "remote-com-pointer")
    assert ack["closed"] is False and ack["financial_ack"] is False
    assert not x.ledger.state["resources"]["remote-com-pointer"]["closed"]
    with pytest.raises(ValueError):
        proofs.dispose_after_exit(deadline_ns=x.now[0] + 10**9)
    x.calls.finish(child.child)
    released = proofs.dispose_after_exit(deadline_ns=x.now[0] + 10**9)
    assert x.ledger.state["resources"]["remote-com-pointer"]["closed"]
    assert released["release_only"] and not released["financial_ack"]


def test_physical_factory_refuses_missing_aggregate_before_any_native_allocation():
    from scripts.observation_runtime.aip06_native_session import (
        NativeSessionFactory,
        ChannelSessionProtocol,
    )

    x = fixture()
    output = SimpleNamespace(append=lambda value: None)
    protocol = ChannelSessionProtocol(
        WindowsChildEndpoints(
            pipe_calls=None, clock_ns=lambda: x.now[0], output=output
        ),
        lambda: x.now[0],
        output,
    )
    factory = NativeSessionFactory(protocol)
    before = dict(x.calls.handles)
    with pytest.raises(ValueError, match="AGGREGATE_ENVELOPE"):
        factory(x.controller, x.ledger, x.io, x.cim, x.alloc)
    assert x.calls.handles == before


class TableResponses(CimResponses):
    def __init__(self, rows):
        super().__init__()
        self.rows = list(rows)
        self.index = 0
        self.bad = None

    def enable_cancellation(self):
        self.events.append("enabled")

    def disable_cancellation(self):
        self.events.append("disabled")

    def cancel(self, tid):
        pass

    def next_row(self, enum, remaining):
        if self.bad == "timeout":
            raise ValueError("CIM_TABLE_ENUMERATION_INCOMPLETE")
        if self.index == len(self.rows):
            return None
        i = self.index
        self.index += 1
        return i

    def property(self, obj, name):
        return self.rows[obj][name]


def test_cim_full_table_requires_authoritative_end_and_releases_all_references():
    x = fixture()
    api = TableResponses([{"ProcessId": 20}, {"ProcessId": 30}])
    tables = CimTables(
        api=api,
        allocations=x.alloc,
        worker=SimpleNamespace(run=lambda f, **kw: f()),
        clock_ns=lambda: x.now[0],
    )
    result = tables.read(
        namespace=r"ROOT\CIMV2",
        query="SELECT ProcessId FROM Win32_Process",
        fields=("ProcessId",),
        deadline_ns=x.now[0] + 10**9,
    )
    assert result["complete"] and result["rows"] == [
        {"ProcessId": 20},
        {"ProcessId": 30},
    ]
    assert not x.alloc.live and api.events[-1] == "uninitialize"


def test_cim_timeout_is_not_an_empty_table_or_complete_observation():
    x = fixture()
    api = TableResponses([])
    api.bad = "timeout"
    tables = CimTables(
        api=api,
        allocations=x.alloc,
        worker=SimpleNamespace(run=lambda f, **kw: f()),
        clock_ns=lambda: x.now[0],
    )
    with pytest.raises(ValueError, match="INCOMPLETE"):
        tables.read(
            namespace=r"ROOT\CIMV2",
            query="SELECT ProcessId FROM Win32_Process",
            fields=("ProcessId",),
            deadline_ns=x.now[0] + 10**9,
        )
    assert api.events[-1] == "uninitialize"


@pytest.mark.parametrize("state", [0, 2, 11])
def test_native_tcp_provider_decodes_both_complete_address_family_tables_without_relabeling(
    state,
):
    port = 54321
    data = {
        socket.AF_INET: struct.pack(
            "<I6I", 1, state, 0x0100007F, socket.htons(port), 0, 0, 20
        ),
        socket.AF_INET6: struct.pack("<I", 0),
    }

    def get(buffer, size, *args):
        raw = data[args[1]]
        size._obj.value = len(raw)
        if buffer is None:
            return 122
        C.memmove(buffer, raw, len(raw))
        return 0

    tables = TcpTables(
        SimpleNamespace(GetExtendedTcpTable=get),
        worker=SimpleNamespace(run=lambda f, **kw: f()),
        clock_ns=lambda: 10**9,
    )
    result = tables.read(deadline_ns=2 * 10**9)
    assert result["complete"] and len(result["rows"]) == 1
    assert (
        result["rows"][0]["state"] == state and result["rows"][0]["local_port"] == port
    )


@pytest.mark.parametrize("mode", ["truncated", "query_error", "buffer_limit"])
def test_native_tcp_reader_refuses_incomplete_native_enumeration(mode):
    def get(buffer, size, *args):
        size._obj.value = 4 if mode != "buffer_limit" else 16 * 1024**2
        if buffer is None:
            return 5 if mode == "query_error" else 122
        C.memmove(buffer, struct.pack("<I", 100), 4)
        return 0

    tables = TcpTables(
        SimpleNamespace(GetExtendedTcpTable=get),
        worker=SimpleNamespace(run=lambda f, **kw: f()),
        clock_ns=lambda: 10**9,
    )
    with pytest.raises(ValueError):
        tables.read(deadline_ns=2 * 10**9)


@pytest.mark.parametrize("state", [0, 2, 11])
def test_cim_tcp_adapter_preserves_raw_state_instead_of_inventing_listening(state):
    table = {
        "rows": [
            {
                "LocalAddress": "127.0.0.1",
                "LocalPort": 54321,
                "RemoteAddress": "0.0.0.0",
                "RemotePort": 0,
                "State": state,
                "OwningProcess": 20,
            }
        ],
        "complete": True,
        "error": None,
        "started_ns": 1,
        "finished_ns": 2,
    }
    result = CimSockets(SimpleNamespace(read=lambda **kw: copy.deepcopy(table))).read(
        deadline_ns=100
    )
    assert result["rows"][0]["state"] == state


def socket_fixture():
    x = SimpleNamespace(now=[10**9], records=[])
    x.port = SimpleNamespace(
        aggregate=SimpleNamespace(rows={20: {"native": {"pid": 20}}})
    )
    x.values = {
        k: {
            "rows": [],
            "complete": True,
            "error": None,
            "started_ns": 10**9,
            "finished_ns": 10**9,
        }
        for k in ("CIM", "IP_HELPER", "NETSTAT")
    }
    x.cleanup = ThreeReaderCleanup(
        readers={
            k: SimpleNamespace(read=lambda deadline_ns, k=k: copy.deepcopy(x.values[k]))
            for k in x.values
        },
        port=x.port,
        output=SimpleNamespace(append=x.records.append),
        clock_ns=lambda: x.now[0],
    )
    return x


def tcp(state=2, pid=20, family=4):
    return {
        "protocol": "TCP",
        "family": family,
        "local_address": "127.0.0.1" if family == 4 else "::1",
        "local_port": 54321,
        "remote_address": "127.0.0.1" if family == 4 else "::1",
        "remote_port": 54322,
        "state": state,
        "owner_present": True,
        "owner_pid": pid,
    }


def test_three_reader_complete_absence_produces_source_cut_without_silence_substitution():
    x = socket_fixture()
    cut = x.cleanup.collect(deadline_ns=x.now[0] + 10**9, started_ns=x.now[0])
    assert cut["scope"] == SCOPE_HASH
    assert set(cut["readers"]) == set(x.values) and len(x.records) == 3
    assert all(
        r["complete"] and r["owned_endpoints"] == [] for r in cut["readers"].values()
    )


@pytest.mark.parametrize("state", [0, 2, 6, 7, 8, 9, 10, 12, 13])
def test_scoped_active_or_unknown_socket_cannot_pass_cleanup(state):
    x = socket_fixture()
    for v in x.values.values():
        v["rows"] = [tcp(state)]
    with pytest.raises(ValueError):
        x.cleanup.collect(deadline_ns=x.now[0] + 10**9, started_ns=x.now[0])
    assert x.cleanup.failed


@pytest.mark.parametrize(
    "damage",
    [
        "missing_reader",
        "incomplete",
        "error",
        "stale",
        "future",
        "owner",
        "family",
        "conflict",
        "pid0_listen",
        "pid0_state0",
    ],
)
def test_three_reader_missing_stale_or_disagreeing_evidence_is_never_clean(damage):
    x = socket_fixture()
    r = x.values["CIM"]
    if damage == "missing_reader":
        with pytest.raises(ValueError):
            ThreeReaderCleanup(readers={}, port=x.port, output=None, clock_ns=lambda: 0)
        return
    if damage == "incomplete":
        r["complete"] = False
    elif damage == "error":
        r["error"] = "unavailable"
    elif damage == "stale":
        r["started_ns"] = 1
    elif damage == "future":
        r["finished_ns"] += 1
    elif damage == "owner":
        r["rows"] = [{**tcp(), "owner_present": False, "owner_pid": None}]
    elif damage == "family":
        r["rows"] = [{**tcp(), "family": 6}]
    elif damage == "conflict":
        r["rows"] = [tcp(11)]
    else:
        r["rows"] = [tcp(2 if damage == "pid0_listen" else 0, 0)]
    with pytest.raises(ValueError):
        x.cleanup.collect(deadline_ns=x.now[0] + 10**9, started_ns=x.now[0])


@pytest.mark.parametrize("state", [1, 11])
def test_unanimous_terminal_states_keep_exact_endpoint_identity(state):
    x = socket_fixture()
    for v in x.values.values():
        v["rows"] = [tcp(state)]
    assert (
        x.cleanup.collect(deadline_ns=x.now[0] + 10**9, started_ns=x.now[0])["readers"][
            "CIM"
        ]["owned_endpoints"]
        == []
    )


def test_guarded_netstat_requires_real_guarded_query_receipt_no_raw_subprocess_fallback():
    calls = []
    guard = SimpleNamespace(
        clock=lambda: 10**9,
        query=lambda argv, **kw: (
            calls.append((argv, kw))
            or {
                "exit_code": 0,
                "stdout": "TCP 127.0.0.1:54321 127.0.0.1:54322 TIME_WAIT 0\n",
                "stderr": "",
                "identity": {"pid": 20},
                "closed": True,
            }
        ),
    )
    result = GuardedNetstat(guard, [EXE, "-B", r"D:\reviewed\query.py"]).read(
        deadline_ns=2 * 10**9
    )
    assert result["rows"][0]["state"] == 11 and calls and calls[0][1]["timeout"] == 1


def test_socket_cleanup_is_followed_by_current_strict_process_and_original_handle_proofs():
    x = aggregate_fixture()
    x.aggregate.controller["created"] = 134066448000000000
    x.calls.rows[10]["created"] = x.aggregate.controller["created"]
    from scripts.observation_runtime.aip06_windows_cim import filetime

    date = "20261104130000.000000+000"
    x.aggregate.controller["created"] = x.calls.rows[10]["created"] = filetime(date)
    tables = SimpleNamespace(
        read=lambda **kw: {
            "rows": [
                {
                    "ProcessId": 10,
                    "ParentProcessId": 8,
                    "CreationDate": date,
                    "ExecutablePath": EXE,
                    "CommandLine": x.parent["command_line"],
                }
            ],
            "complete": True,
            "error": None,
            "started_ns": x.now[0],
            "finished_ns": x.now[0],
        }
    )
    records = []
    result = StrictProcessCleanup(
        port=x.port,
        tables=tables,
        output=SimpleNamespace(append=records.append),
        clock_ns=lambda: x.now[0],
    ).collect(after_ns=x.now[0], deadline_ns=x.now[0] + 10**9)
    assert result["survivors"] == [] and records[0]["aggregate"]["members"] == [10]


@pytest.mark.parametrize(
    "damage",
    [
        "absent_controller",
        "duplicate_controller",
        "controller_command",
        "controller_image",
        "retained_handle",
        "stale",
        "survivor",
        "process_pid_reuse",
    ],
)
def test_strict_process_cut_refuses_omission_conflicts_survivors_and_unclosed_handles(
    damage,
):
    x = aggregate_fixture()
    from scripts.observation_runtime.aip06_windows_cim import filetime

    date = "20261104130000.000000+000"
    x.aggregate.controller["created"] = x.calls.rows[10]["created"] = filetime(date)
    row = {
        "ProcessId": 10,
        "ParentProcessId": 8,
        "CreationDate": date,
        "ExecutablePath": EXE,
        "CommandLine": x.parent["command_line"],
    }
    raw = {
        "rows": [row],
        "complete": True,
        "error": None,
        "started_ns": x.now[0],
        "finished_ns": x.now[0],
    }
    if damage == "absent_controller":
        raw["rows"] = []
    elif damage == "duplicate_controller":
        raw["rows"].append(copy.deepcopy(row))
    elif damage == "controller_command":
        row["CommandLine"] = "wrong"
    elif damage == "controller_image":
        row["ExecutablePath"] = r"D:\foreign.exe"
    elif damage == "retained_handle":
        x.port.sessions.append(SimpleNamespace(closed=False))
    elif damage == "stale":
        raw["started_ns"] -= 1
    elif damage == "survivor":
        raw["rows"].append({**row, "ProcessId": 20})
    else:
        row["CreationDate"] = "20261104130000.000001+000"
    collector = StrictProcessCleanup(
        port=x.port,
        tables=SimpleNamespace(read=lambda **kw: raw),
        output=SimpleNamespace(append=lambda v: None),
        clock_ns=lambda: x.now[0],
    )
    with pytest.raises(ValueError):
        collector.collect(after_ns=x.now[0], deadline_ns=x.now[0] + 10**9)


def test_controller_binds_actual_cleanup_stop_and_reader_classes_without_querying_or_launching():
    from scripts.observation_runtime.aip06_native_controller import NativeController
    from scripts.observation_runtime.aip06_stop import GuardedStopCollector
    from scripts.observation_runtime.aip06_owned_stop import OwnedStopAssembly

    x = aggregate_fixture()
    controller = NativeController.__new__(NativeController)
    controller.initialized = True
    controller.failed = False
    controller.guard = x.guard
    controller.profile = {
        **x.profile,
        "targets": {**x.targets, "query": r"D:\reviewed\query.py"},
    }
    controller.calls = x.calls
    controller.clock = lambda: x.now[0]
    controller.cim_api = object()
    controller.aggregate = x.aggregate
    controller.process_port = x.port
    controller.process_allocations = x.alloc
    controller.cleanup = None
    controller.io = x.io
    controller.book = SimpleNamespace(live={}, journal_live={})
    fake_get = lambda *a: pytest.fail("Binding must not enumerate Windows")
    collector = controller.bind_cleanup(
        ip_helper_dll=SimpleNamespace(GetExtendedTcpTable=fake_get),
        output=SimpleNamespace(append=lambda v: None),
        query_argv=(EXE, "-B", r"D:\reviewed\query.py"),
    )
    assert type(collector) is GuardedStopCollector
    assert type(x.port.stop_assembly) is OwnedStopAssembly
    assert set(controller.cleanup["sockets"].readers) == {"CIM", "IP_HELPER", "NETSTAT"}
    with pytest.raises(ValueError, match="ONE_AGGREGATE"):
        controller.bind_cleanup(ip_helper_dll=None, output=None, query_argv=[])


def test_query_timeout_is_a_query_bound_not_an_undeclared_child_creation_option():
    from scripts.observation_runtime.aip06_fixture_guard import FixtureGuard

    seen = []
    child = SimpleNamespace(plan={"name": "query"}, close=lambda: seen.append("closed"))
    fake = SimpleNamespace(
        query_active=False,
        spawn=lambda argv, **options: seen.append(options) or child,
        processes=SimpleNamespace(
            query_result=lambda child, **kw: seen.append(kw) or "result"
        ),
    )
    assert (
        FixtureGuard.query(fake, [EXE, "-B", r"D:\reviewed\query.py"], timeout=1)
        == "result"
    )
    assert seen[0] == {} and seen[1]["timeout"] == 1 and seen[-1] == "closed"
    assert not fake.query_active


@pytest.mark.parametrize("timeout", [0, -1, 7, True, None])
def test_query_rejects_invalid_or_expanded_time_bound_before_any_spawn(timeout):
    from scripts.observation_runtime.aip06_fixture_guard import FixtureGuard

    fake = SimpleNamespace(
        query_active=False,
        spawn=lambda *a, **kw: pytest.fail("No launch on invalid bound"),
    )
    with pytest.raises(ValueError):
        FixtureGuard.query(fake, [], timeout=timeout)


def test_native_entry_stays_closed_while_inherited_bootstrap_accounting_is_incomplete():
    from scripts.observation_runtime.aip06_child_bootstrap import main

    with pytest.raises(ValueError, match="NATIVE_CHILD_LAUNCH_PORT_NOT_BOUND"):
        main()


@pytest.mark.parametrize("unit", [512, 65536, None])
def test_controller_refuses_incompatible_or_unavailable_volume_unit_before_fixture_creation(
    unit,
):
    from test_aip06_windows_adapters import controller_fixture

    f = controller_fixture()
    f.controller.files.allocation_unit = lambda: unit
    with pytest.raises(ValueError, match="ALLOCATION_UNIT_MUST_MATCH"):
        f.controller.initialize(
            lambda *a: pytest.fail("No native factory on incompatible geometry")
        )
    assert not f.x.calls.events and f.controller.failed


def test_volume_provider_uses_actual_geometry_values_without_modifying_canonical_rounding():
    from scripts.observation_runtime.aip06_windows_io import WindowsFileCalls

    seen = []

    def get(path, *values):
        seen.append(path)
        for target, value in zip(values, (8, 512, 100, 1000), strict=True):
            target._obj.value = value
        return True

    files = WindowsFileCalls(SimpleNamespace(K=SimpleNamespace(GetDiskFreeSpaceW=get)))
    assert files.allocation_unit() == 4096 and seen == ["D:\\"]


def test_ipc_frame_sent_during_a_receive_wait_is_fresh_without_extending_the_deadline():
    from test_aip06_windows_adapters import channels

    x = channels()
    initial = x.s.now[0]
    read = x.b.read_exact
    sent = []

    def receive_bytes(n, *, deadline_ns):
        if not sent:
            x.s.now[0] += 1
            x.parent.send(
                "ACK", {"receipt": "offline-during-wait"}, deadline_ns=deadline_ns
            )
            sent.append(True)
        return read(n, deadline_ns=deadline_ns)

    x.b.read_exact = receive_bytes
    result = x.child_channel.receive(deadline_ns=initial + 10**9, expected_kind="ACK")
    assert initial < result["sent_ns"] <= x.s.now[0] < initial + 10**9
    assert result["payload"]["receipt"] == "offline-during-wait"


def test_persistent_aggregate_envelope_is_not_silently_exempted_from_complete_stop_release():
    from test_aip06_harness import stop_fixture

    x = stop_fixture()
    x.s.ledger.reserve(
        x.s.controller, "aggregate-envelope-still-retained", "job", cleanup=True
    )
    with pytest.raises(ValueError, match="OWNED_RESOURCE_LEAK_OR_UNVERIFIED_RELEASE"):
        x.stop.finish(**x.args)
    assert x.stop.result is None
