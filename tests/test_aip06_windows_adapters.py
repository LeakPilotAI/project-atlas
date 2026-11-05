"""Offline injected Windows responses only; no WinDLL load or native worker."""

import copy
import ntpath
from types import SimpleNamespace

import pytest
from app.services.paper_financial_replay import digest, strict
from test_aip06_harness import Files, resources
from test_launch_ownership import row

from scripts.observation_runtime import aip06_fixture_guard as guards
from scripts.observation_runtime.aip06_harness import (
    ROOTS,
    SCOPE_HASH,
    FixturePaths,
    SharedResources,
    WorkerOwnership,
    path_for,
)
from scripts.observation_runtime.aip06_ipc import (
    Broker,
    Channel,
    RemoteResources,
    StopMessages,
    encode,
)
from scripts.observation_runtime.aip06_native_controller import (
    BootstrapBudget,
    NativeAllocations,
    NativeController,
)
from scripts.observation_runtime.aip06_outputs import (
    BoundedOutput,
    EvidenceOutput,
    LegacyProbeAdapter,
)
from scripts.observation_runtime.aip06_windows_cim import CimProcessQuery, filetime
from scripts.observation_runtime.aip06_windows_io import (
    AllocationBook,
    NativeIO,
    NativeJournalIO,
    NativeOpenFailed,
)
from scripts.observation_runtime.aip06_windows_process import NativeProcessObserver
from scripts.observation_runtime.aip06_child_bootstrap import (
    ChildBootstrap,
    InheritedIdentity,
)
from scripts.observation_runtime.aip06_pipe_transport import CreditedPipeEndpoint


ACCOUNTS = {
    "QUALITY_DIPS": {
        "account_id": "SYNTHETIC-QD",
        "epoch": "SYNTHETIC-USD",
        "currency": "USD",
    },
    "HYPERLIQUID": {
        "account_id": "SYNTHETIC-HL",
        "epoch": "SYNTHETIC-USDC",
        "currency": "USDC",
    },
}


class FileResponses(Files):
    def __init__(self):
        super().__init__()
        self.rows = {r["path"]: r for r in self.chain_rows}
        self.handles = {}
        self.raw = {}
        self.next_handle = 100
        self.next_file = 1000
        self.events = []
        self.deny = None
        self.fail_close = False

    def allocate(self, path):
        self.next_handle += 1
        self.handles[self.next_handle] = path
        self.events.append(("open", path))
        return self.next_handle

    def open_drive(self):
        return self.allocate("D:\\")

    def relative(
        self,
        parent,
        leaf,
        *,
        directory=None,
        create=False,
        write=False,
        delete=False,
        sid=None,
    ):
        path = ntpath.join(self.handles[parent], leaf)
        if path == self.deny:
            raise NativeOpenFailed(5)
        if create:
            if path in self.rows:
                raise NativeOpenFailed(183)
            self.next_file += 1
            self.rows[path] = {
                "path": path,
                "id": [1, self.next_file, 0],
                "parent_id": self.rows[self.handles[parent]]["id"],
                "kind": "directory" if directory else "file",
                "reparse": False,
                "links": 1,
            }
            self.raw[path] = b""
            self.events.append(("create", path))
        if path not in self.rows:
            raise NativeOpenFailed(2)
        return self.allocate(path)

    def describe(self, h):
        r = copy.deepcopy(self.rows[self.handles[h]])
        r.pop("path")
        r.pop("parent_id")
        r["bytes"] = len(self.raw.get(self.handles[h], b""))
        return r

    def final_path(self, h):
        return self.handles[h]

    def acl(self, h, sid):
        assert sid == "owner"

    def close(self, h):
        if self.fail_close:
            raise OSError("offline close failure")
        assert h in self.handles
        self.events.append(("close", self.handles.pop(h)))

    def closed(self, h):
        return h not in self.handles

    def read(self, h, limit):
        value = self.raw[self.handles[h]]
        if len(value) > limit:
            raise ValueError("offline read capacity")
        return value

    def write(self, h, raw):
        self.raw[self.handles[h]] = raw
        self.events.append(("write", self.handles[h]))

    def flush(self, h):
        self.events.append(("flush", self.handles[h]))

    def rename(self, h, parent, leaf):
        source = self.handles[h]
        target = ntpath.join(self.handles[parent], leaf)
        self.rows[target] = self.rows.pop(source)
        self.rows[target]["path"] = target
        self.raw[target] = self.raw.pop(source)
        self.handles[h] = target

    def names(self, h, maximum):
        names = sorted(
            ntpath.basename(p)
            for p in self.rows
            if ntpath.dirname(p) == self.handles[h]
        )
        assert len(names) <= maximum
        return names

    def token_identity(self, h):
        return {"sid": "owner", "type": 1}

    def current_process_native(self):
        return {"pid": 10, "created": 10000}


def io_fixture():
    s = resources()
    calls = FileResponses()
    book = AllocationBook(s.ledger, s.controller, calls, lambda: s.now[0])
    io = NativeIO(calls=calls, book=book, sid="owner", clock_ns=lambda: s.now[0])
    paths = FixturePaths(io)
    processes = SimpleNamespace(executable=r"D:\synthetic\python.exe")
    ownership = WorkerOwnership(s.ledger, all_members=lambda: set())
    guard = guards.FixtureGuard(
        resources=s.ledger,
        paths=paths,
        ownership=ownership,
        owner=s.controller,
        io=io,
        processes=processes,
        clock_ns=lambda: s.now[0],
    )
    return SimpleNamespace(**locals())


def test_concrete_io_actual_guard_path_create_write_flush_readback_and_close():
    x = io_fixture()
    with x.guard.installed():
        guards.mkdir(ROOTS["P"])
        guards.write_bytes(path_for("P", "pin.json"), b'{"revision":0}')
        assert guards.read_bytes(path_for("P", "pin.json")) == b'{"revision":0}'
        guards.rewrite_text(path_for("P", "pin.json"), '{"revision":1}')
        assert strict(guards.read_bytes(path_for("P", "pin.json")).decode()) == {
            "revision": 1
        }
        x.io.close_cache()
    assert not x.calls.handles and not x.book.live
    assert all(r["closed"] for r in x.s.ledger.state["resources"].values())
    assert ("flush", path_for("P", "pin.json")) in x.calls.events


@pytest.mark.parametrize(
    "path",
    [r"D:\AtlasRuntime\x", r"C:\temp\x", ROOTS["P"] + r"\..\x", ROOTS["P"] + ":ads"],
)
def test_concrete_io_scope_refuses_before_any_native_creation(path):
    x = io_fixture()
    with x.guard.installed(), pytest.raises(ValueError):
        guards.write_bytes(path, b"x")
    assert not x.calls.events


@pytest.mark.parametrize(
    "damage", ["junction", "link", "identity", "access", "close", "budget"]
)
def test_concrete_io_injected_native_refusals_preserve_unknown(damage):
    x = io_fixture()
    if damage == "budget":
        x.s.now[0] += 601 * 10**9
        with pytest.raises(ValueError):
            x.io.inspect(ROOTS["P"])
        assert not x.calls.events
        return
    with x.guard.installed():
        guards.mkdir(ROOTS["P"])
        if damage == "junction":
            x.calls.rows[ROOTS["P"]]["reparse"] = True
        elif damage == "link":
            x.calls.rows[ROOTS["P"]]["links"] = 2
        elif damage == "identity":
            x.calls.rows[ROOTS["P"]]["id"] = [9, 9, 9]
        elif damage == "access":
            x.calls.deny = path_for("P", "x")
        else:
            x.calls.fail_close = True
        with pytest.raises((ValueError, OSError)):
            guards.write_bytes(path_for("P", "x"), b"x")
        if damage == "close":
            assert x.book.live
        else:
            # Only original handles are closed; original failing rows remain.
            x.calls.rows[ROOTS["P"]]["reparse"] = False
            x.calls.rows[ROOTS["P"]]["links"] = 1
            x.io.close_cache()


def test_missing_leaf_closes_the_prospective_native_handle_reservation():
    x = io_fixture()
    assert x.io.inspect(ROOTS["P"]) is None
    x.io.close_cache()
    assert not x.book.live and all(
        r["closed"] for r in x.s.ledger.state["resources"].values()
    )


def test_concrete_native_journal_creates_flushes_reads_and_verifies_closed_batches():
    x = io_fixture()
    with x.guard.installed():
        guards.mkdir(ROOTS["E"])
        guards.mkdir(path_for("E", "journal"))
        io = NativeJournalIO(x.io, x.io.inspect(path_for("E", "journal"))["id"])
        journal = guards.CreateNewJournal(io, io.identity)
        ledger = SharedResources(journal, clock_ns=lambda: x.s.now[0])
        owner = ledger.register_owner(row(10, 8), controller=True)
        ledger.reserve(owner, "fixture", "file", entries=1, size=10)
        assert journal.receipt()["head"] == ledger.head and not x.book.journal_live
        assert len(journal.read()) == 2
        x.io.close_cache()
    assert not x.calls.handles


class MemoryEndpoint:
    def __init__(self):
        self.buffer = bytearray()
        self.peer = None
        self.after_write = None
        self.checks = 0
        self.fail = False

    def verify_peer(self, binding):
        self.checks += 1
        if self.fail:
            raise ValueError("offline peer mismatch")

    def write_all(self, raw, *, deadline_ns):
        self.peer.buffer.extend(raw)
        if self.after_write:
            self.after_write()

    def read_exact(self, n, *, deadline_ns):
        value = bytes(self.buffer[:n])
        del self.buffer[:n]
        return value


def channels():
    s = resources()
    child = row(20, 10)
    owner = s.ledger.register_owner(child)
    binding = {
        "scope": SCOPE_HASH,
        "session": "a" * 32,
        "nonce": "b" * 32,
        "parent": row(10, 8),
        "child": child,
        "job": {"name": "Local\\AIP06-explicit"},
        "launch": {"command": "exact command"},
    }
    a, b = MemoryEndpoint(), MemoryEndpoint()
    a.peer = b
    b.peer = a
    parent = Channel(
        a,
        binding=binding,
        clock_ns=lambda: s.now[0],
        account_scope=ACCOUNTS,
        role="PARENT",
    )
    child_channel = Channel(
        b,
        binding=binding,
        clock_ns=lambda: s.now[0],
        account_scope=ACCOUNTS,
        role="CHILD",
    )
    return SimpleNamespace(**locals())


def test_ipc_actual_encoding_peer_binding_version_and_round_trip():
    x = channels()
    x.parent.send("STOP", {"operation": "SYNTHETIC"}, deadline_ns=x.s.now[0] + 10**9)
    message = x.child_channel.receive(
        deadline_ns=x.s.now[0] + 10**9, expected_kind="STOP"
    )
    assert message["payload"] == {"operation": "SYNTHETIC"} and x.b.checks >= 2
    x.child_channel.send(
        "ACK", {"receipt": "not-a-financial-ack"}, deadline_ns=x.s.now[0] + 10**9
    )
    assert x.parent.receive(deadline_ns=x.s.now[0] + 10**9)["kind"] == "ACK"


@pytest.mark.parametrize(
    "damage",
    [
        "length",
        "truncated",
        "version",
        "sequence",
        "direction",
        "binding",
        "account",
        "parent",
        "stale",
        "peer",
    ],
)
def test_ipc_framing_identity_revision_and_freshness_fail_closed(damage):
    x = channels()
    x.parent.send("ACK", {"id": "synthetic"}, deadline_ns=x.s.now[0] + 10**9)
    raw = bytes(x.b.buffer)
    value = strict(raw[4:].decode())
    if damage == "length":
        x.b.buffer = bytearray(b"\xff\xff\xff\xff")
    elif damage == "truncated":
        x.b.buffer = x.b.buffer[:-1]
    elif damage == "stale":
        x.s.now[0] += 7 * 10**9
    elif damage == "peer":
        x.b.fail = True
    else:
        field = {
            "version": "schema",
            "sequence": "sequence",
            "direction": "direction",
            "binding": "binding",
            "account": "accounts",
            "parent": "parent",
        }[damage]
        value[field] = True if damage == "sequence" else "wrong"
        x.b.buffer = bytearray(encode(value))
    with pytest.raises(ValueError):
        x.child_channel.receive(deadline_ns=x.s.now[0] + 10**9)
    assert x.child_channel.failed
    with pytest.raises(ValueError):
        x.child_channel.send("ACK", {}, deadline_ns=x.s.now[0] + 10**9)


def test_duplicate_pipe_frame_is_not_a_second_acknowledgement():
    x = channels()
    x.parent.send("ACK", {}, deadline_ns=x.s.now[0] + 10**9)
    raw = bytes(x.b.buffer)
    x.child_channel.receive(deadline_ns=x.s.now[0] + 10**9)
    x.b.buffer.extend(raw)
    with pytest.raises(ValueError):
        x.child_channel.receive(deadline_ns=x.s.now[0] + 10**9)


class Output:
    def __init__(self):
        self.records = []
        self.fail = False

    def append(self, value):
        if self.fail:
            raise OSError("offline durable output refusal")
        self.records.append(copy.deepcopy(value))


def rpc_fixture():
    x = channels()
    output = Output()
    verifier = SimpleNamespace(
        verify_peer=lambda binding: None,
        release_observer=lambda *a: SimpleNamespace(closed=lambda *a: True),
    )
    broker = Broker(
        resources=x.s.ledger,
        channel=x.parent,
        peer_owner=x.owner,
        verifier=verifier,
        output=output,
        clock_ns=lambda: x.s.now[0],
    )
    x.b.after_write = lambda: broker.serve_once(deadline_ns=x.s.now[0] + 6 * 10**9)
    remote = RemoteResources(
        x.child_channel,
        owner=x.owner,
        initial=x.s.ledger.read(),
        clock_ns=lambda: x.s.now[0],
        proofs=SimpleNamespace(
            release=lambda *a: {"source": "OFFLINE_INJECTED_RELEASE"}
        ),
    )
    return SimpleNamespace(**locals())


def test_shared_child_resources_mutate_parent_ledger_without_a_second_journal():
    f = rpc_fixture()
    f.remote.reserve(f.x.owner, "child-file", "file", entries=1, size=10)
    assert f.x.s.ledger.state["resources"]["child-file"]["owner"] == f.x.owner
    assert f.remote.state == f.x.s.ledger.state and f.remote.revision == 1
    f.remote.close(
        f.x.owner, "child-file", observer=SimpleNamespace(closed=lambda *a: True)
    )
    assert f.x.s.ledger.state["resources"]["child-file"]["closed"]
    assert [r["schema"] for r in f.output.records] == [
        "AIP06_RPC_INTENT_V1",
        "AIP06_RPC_RESULT_V1",
    ] * 2


@pytest.mark.parametrize(
    "damage", ["foreign", "capacity", "output", "closed-proof", "lost-result"]
)
def test_rpc_rejects_unauthorized_or_uncertain_mutations(damage):
    f = rpc_fixture()
    before = f.x.s.ledger.state
    if damage == "output":
        f.output.fail = True
    if damage == "foreign":
        owner = "unknown"
    else:
        owner = f.x.owner
    if damage == "lost-result":
        original = f.output.append

        def fail_result(value):
            if value["schema"] == "AIP06_RPC_RESULT_V1":
                raise OSError("offline result loss")
            return original(value)

        f.output.append = fail_result
    with pytest.raises((ValueError, OSError)):
        if damage == "closed-proof":
            f.remote.reserve(owner, "a", "file")
            f.remote.close(
                owner, "a", observer=SimpleNamespace(closed=lambda *a: False)
            )
        else:
            f.remote.reserve(
                owner,
                "a",
                "file",
                entries=1,
                size=1024**2 + 1 if damage == "capacity" else 1,
            )
    if damage in ("foreign", "capacity", "output"):
        assert f.x.s.ledger.state == before
    if damage == "lost-result":
        assert f.broker.unknown and f.remote.uncertain


def test_broker_recovery_reports_uncertain_tail_without_replaying_it():
    f = rpc_fixture()
    f.remote.reserve(f.x.owner, "a", "file")
    records = f.output.records
    other = Broker(
        resources=f.x.s.ledger,
        channel=f.x.parent,
        peer_owner=f.x.owner,
        verifier=f.verifier,
        output=Output(),
        clock_ns=lambda: f.x.s.now[0],
    )
    result = other.recover(records[:-1], expected_head=f.x.s.ledger.head)
    assert result["pending"] and not result["resumption_authorized"]
    with pytest.raises(ValueError):
        other.serve_once(deadline_ns=f.x.s.now[0] + 10**9)


@pytest.mark.parametrize(
    "damage",
    [
        "duplicate",
        "wrong-request",
        "revision",
        "currency",
        "pending",
        "unknown",
        "orders",
    ],
)
def test_stop_messages_require_real_correlated_ack_and_complete_typed_drain(damage):
    x = channels()
    request = {
        "scope": SCOPE_HASH,
        "nonce": "b" * 32,
        "worker": x.parent.binding["child"],
        "operation_id": "synthetic-stop",
    }
    port = StopMessages(x.parent, request, revision=3, accounts=ACCOUNTS)
    ack = {
        "request": copy.deepcopy(request),
        "revision": 3,
        "accounts": copy.deepcopy(ACCOUNTS),
    }
    drain = {
        "scope": SCOPE_HASH,
        "operation_id": "synthetic-stop",
        "pending": 0,
        "unknown": False,
        "orders": 0,
    }
    if damage == "wrong-request":
        ack["request"]["operation_id"] = "other"
    elif damage == "revision":
        ack["revision"] = True
    elif damage == "currency":
        ack["accounts"]["HYPERLIQUID"]["currency"] = "USD"
    if damage in ("wrong-request", "revision", "currency"):
        with pytest.raises(ValueError):
            port.acknowledge(ack)
    else:
        port.acknowledge(ack)
        if damage == "duplicate":
            with pytest.raises(ValueError):
                port.acknowledge(ack)
        else:
            drain[damage] = True if damage == "unknown" else 1
            with pytest.raises(ValueError):
                port.drain(drain)


class CimResponses:
    def __init__(self):
        self.events = []
        self.fail = None

    def initialize(self):
        self.events.append("initialize")

    def uninitialize(self):
        self.events.append("uninitialize")

    def locator(self):
        return "locator"

    def bstr(self, text):
        return text

    def free(self, text):
        self.events.append("free")

    def connect(self, *args):
        return "service"

    def query(self, *args):
        return "enum"

    def next(self, enum, timeout):
        assert 0 < timeout <= 2000
        if self.fail == "enumeration":
            raise OSError("offline CIM timeout")
        return "object"

    def property(self, obj, name):
        value = {
            "ProcessId": 20,
            "ParentProcessId": 10,
            "CreationDate": "20261104070000.000000-360",
            "ExecutablePath": r"D:\runtime\python.exe",
            "CommandLine": "exact command",
        }[name]
        if self.fail == name:
            return None
        return value

    def release(self, obj):
        self.events.append("release")


def test_concrete_cim_adapter_uses_direct_query_and_closes_native_references():
    s = resources()
    api = CimResponses()
    allocations = NativeAllocations(s.ledger, s.controller)
    query = CimProcessQuery(api=api, allocations=allocations, clock_ns=lambda: s.now[0])
    value = query.process(20, deadline_ns=s.now[0] + 5 * 10**9)
    assert value["created"] == filetime("20261104130000.000000+000")
    assert value["parent_pid"] == 10 and not allocations.live
    assert api.events.count("release") == 4 and api.events[-1] == "uninitialize"


@pytest.mark.parametrize(
    "failure",
    [
        "enumeration",
        "ProcessId",
        "ParentProcessId",
        "CreationDate",
        "ExecutablePath",
        "CommandLine",
    ],
)
def test_cim_errors_or_incomplete_fields_never_become_a_native_identity(failure):
    s = resources()
    api = CimResponses()
    api.fail = failure
    alloc = NativeAllocations(s.ledger, s.controller)
    q = CimProcessQuery(api=api, allocations=alloc, clock_ns=lambda: s.now[0])
    with pytest.raises((ValueError, OSError)):
        q.process(20, deadline_ns=s.now[0] + 5 * 10**9)
    assert api.events[-1] == "uninitialize"


@pytest.mark.parametrize(
    "damage", ["created", "parent", "image", "job", "exit", "unretained"]
)
def test_concrete_process_observer_refuses_injected_native_cim_disagreement(damage):
    s = resources()
    born = filetime("20261104130000.000000+000")
    native = {"pid": 20, "created": born, "image": r"d:\runtime\python.exe"}
    row = {**native, "parent_pid": 10, "command_line": "exact command"}
    if damage == "created":
        row["created"] += 100
    if damage == "parent":
        row["parent_pid"] = False
    if damage == "image":
        row["image"] = r"d:\foreign.exe"
    calls = SimpleNamespace(
        native=lambda h: native,
        lifecycle=lambda h: {"exited": damage == "exit"},
        in_job=lambda *a: damage != "job",
    )
    cim = SimpleNamespace(process=lambda *a, **kw: row)
    images = {
        ntpath.normcase(native["image"]): {"file_id": [1, 2, 3], "sha256": "a" * 64}
    }
    observer = NativeProcessObserver(
        calls=calls, cim=cim, images=images, clock_ns=lambda: s.now[0]
    )
    observer.job = 100
    observer.parent = 200
    if damage == "unretained":
        observer.job = None
    with pytest.raises(ValueError):
        observer.observe(300)


def test_bootstrap_escrow_is_not_a_durable_ack_and_is_charged_in_first_real_event():
    s = resources()
    boot = BootstrapBudget(lambda: s.now[0])
    owner = row(10, 8)
    boot.reserve(boot.owner, "root", "directory", entries=1)
    boot.reserve(boot.owner, "retained", "handle")
    key = boot.bind_owner(owner)
    reservation = boot.seal(owner)
    with pytest.raises(ValueError):
        boot.read()
    from test_aip06_harness import Journal

    ledger = SharedResources(
        Journal(), clock_ns=lambda: s.now[0], bootstrap=reservation
    )
    ledger.register_owner(owner, controller=True)
    assert (
        ledger.state["entries"] > reservation.entries
        and ledger.state["charged_bytes"] > reservation.charged_bytes
    )
    assert ledger.state["resources"]["retained"] == {
        "owner": key,
        "kind": "handle",
        "closed": False,
    }
    with pytest.raises(ValueError):
        SharedResources(
            ledger.journal,
            clock_ns=lambda: s.now[0],
            expected_head=ledger.head,
            bootstrap=reservation,
        )


def test_native_output_chunks_and_source_provenance_use_actual_guarded_io():
    x = io_fixture()
    with x.guard.installed():
        guards.mkdir(ROOTS["E"])
        directory = path_for("E", "outputs")
        guards.mkdir(directory)
        producer = {
            "session": "a" * 32,
            "owner": x.s.controller,
            "role": "OFFLINE_SOURCE_TEST",
            "source_pins": {"source.py": "a" * 64},
        }
        output = EvidenceOutput(x.guard, directory=directory, producer=producer)
        stream = BoundedOutput(
            output, stream="stdout", maximum_bytes=64, chunk_bytes=16
        )
        stream.write("genuine fixture output")
        stream.close()
        assert output.sequence == 2
        with pytest.raises(ValueError):
            stream.fileno()
        original = EvidenceOutput(x.guard, directory=directory, producer=producer)
        assert len(original.recover(expected_head=output.head)) == 2
        with pytest.raises(ValueError):
            original.recover(expected_head="f" * 64)
        x.io.close_cache()


@pytest.mark.parametrize("damage", ["currency", "session", "cleanup", "missing"])
def test_legacy_output_does_not_manufacture_native_acceptance(damage):
    output = Output()
    output.producer = {"session": "a" * 32}
    result = {
        "case": "direct-worker",
        "ready": {"pid": 20, "nonce": "b" * 32},
        "claims": [],
        "exit": {"normal_exit": True, "job_empty": True},
        "cleanup": {"handles_closed": True, "job_members": []},
        "refusal": None,
        "source": {"scope": SCOPE_HASH, "session": "a" * 32},
    }
    if damage == "session":
        result["source"]["session"] = "other"
    if damage == "missing":
        del result["source"]

    def verify(value):
        if damage in ("currency", "cleanup"):
            raise ValueError("offline independent refusal")

    controller = SimpleNamespace(
        clock=lambda: 1, probe_case=lambda name: result, verify_probe_result=verify
    )
    with pytest.raises((ValueError, KeyError)):
        LegacyProbeAdapter(controller, output).run(ROOTS["L"], ["direct-worker"])
    assert not output.records


def bootstrap_fixture(damage=None, role='acceptance_worker'):
    x = channels()
    output = Output()
    events = []
    target = r"D:\reviewed\child.py"
    if role == 'acceptance_supervisor':
        from scripts.observation_runtime.aip06_harness import BASE
        target = ntpath.join(ntpath.dirname(ntpath.dirname(BASE)), 'scripts',
                             'observation_runtime', 'aip06_legacy_entry.py')
    pins = {target: "a" * 64}
    verifier = SimpleNamespace(verify_peer=lambda binding: None)
    broker = Broker(
        resources=x.s.ledger,
        channel=x.parent,
        peer_owner=x.owner,
        verifier=verifier,
        output=output,
        clock_ns=lambda: x.s.now[0],
    )
    observer = SimpleNamespace(
        job=300,
        parent=200,
        members=lambda: {20},
        observe=lambda h: copy.deepcopy(
            x.parent.binding["child" if h == 100 else "parent"]
        ),
    )
    identity = InheritedIdentity(
        observer=observer, current_handle=100, parent_handle=200, job_handle=300
    )
    if damage == "ancestry":
        observer.observe = lambda h: row(20, 9) if h == 100 else row(10, 8)
    if damage == "job":
        observer.members = lambda: {20, 99}

    def parent_dispatch():
        incoming = x.parent.receive(deadline_ns=x.s.now[0] + 6 * 10**9)
        events.append(incoming["kind"])
        if incoming["kind"] == "HELLO":
            assert incoming['payload']['role'] == role
            bind = {
                "snapshot": x.s.ledger.read(),
                "roots": dict(ROOTS),
                "source_pins": pins.copy(),
                "target": target,
                "nonce": "b" * 32,
            }
            if damage == "roots":
                bind["roots"]["P"] = r"D:\AtlasRuntime"
            if damage == "ledger":
                bind["snapshot"]["state"]["controller"] = "foreign"
            x.parent.send("BIND", bind, deadline_ns=x.s.now[0] + 6 * 10**9)
        elif incoming["kind"] == "REQUEST":
            broker.serve_message(incoming, deadline_ns=x.s.now[0] + 6 * 10**9)
        elif incoming['kind']=='BOOTSTRAP':
            value=incoming['payload']
            assert value['schema']=='AIP06_BOOTSTRAP_OBJECT_CUT_V1' and value['scope']==SCOPE_HASH
            assert value['owner']==x.owner and value['parent_reservations_released'] is False
            assert value['financial_ack'] is False and value['sequence']>0
            x.bootstrap_cut=value  # injected receiver, not native object authority
        elif incoming["kind"] == "ACK":
            release = {
                "receipt": digest(incoming["payload"]),
                "target": target,
                "sha256": pins[target],
            }
            if damage == "release":
                release["receipt"] = "f" * 64
            x.parent.send("RELEASE", release, deadline_ns=x.s.now[0] + 6 * 10**9)
        elif incoming["kind"] != "EXIT":
            raise AssertionError(incoming["kind"])

    x.b.after_write = parent_dispatch

    def factory(**kw):
        if damage == "factory":
            return object()
        remote = RemoteResources(
            kw["channel"],
            owner=kw["owner"],
            initial=kw["initial"],
            clock_ns=lambda: x.s.now[0],
            proofs=None,
        )
        calls = FileResponses()
        book = AllocationBook(remote, x.owner, calls, lambda: x.s.now[0])
        io = NativeIO(calls=calls, book=book, sid="owner", clock_ns=lambda: x.s.now[0])
        return guards.FixtureGuard(
            resources=remote,
            paths=FixturePaths(io),
            ownership=WorkerOwnership(remote, all_members=lambda: set()),
            owner=x.owner,
            io=io,
            processes=SimpleNamespace(),
            clock_ns=lambda: x.s.now[0],
        )

    def source(path):
        return {
            "path": path,
            "file_id": [1, 2, 3],
            "sha256": "wrong" if damage == "source" else pins[path],
            "closed": damage != "source-close",
        }

    boot = ChildBootstrap(
        channel=x.child_channel,
        identity=identity,
        target=target,
        source_pins=pins,
        verify_source=source,
        guard_factory=factory,
        clock_ns=lambda: x.s.now[0],
        role=role,
    )
    return SimpleNamespace(**locals())


def test_child_bootstrap_installs_real_shared_guard_before_running_pinned_target():
    f = bootstrap_fixture()
    executed = []
    with pytest.raises(ValueError):
        f.boot.run(lambda target: executed.append(target))
    assert not executed
    receipt = f.boot.prepare()
    assert receipt["guarded"] and f.events[:3] == ["HELLO", "REQUEST", "ACK"]

    def target(path):
        executed.append(path)
        assert guards.require_fixture("offline-child") is f.boot.guard
        return {"domain": "DISPOSABLE_SOURCE_ONLY", "native_acceptance": False}

    assert not f.boot.run(target)["native_acceptance"]
    assert executed == [f.target] and f.events[-1] == "EXIT"
    with pytest.raises(ValueError):
        f.boot.prepare()
    with pytest.raises(ValueError):
        f.boot.run(target)


@pytest.mark.parametrize(
    "damage",
    [
        "ancestry",
        "job",
        "roots",
        "ledger",
        "factory",
        "source",
        "source-close",
        "release",
    ],
)
def test_child_bootstrap_never_releases_unbound_or_contradictory_target(damage):
    f = bootstrap_fixture(damage)
    executed = []
    with pytest.raises(ValueError):
        f.boot.prepare()
        f.boot.run(lambda target: executed.append(target))
    assert not executed and f.boot.failed


def test_ipc_rejects_unrecognized_kind_even_without_expected_kind_filter():
    x = channels()
    x.parent.send("ACK", {}, deadline_ns=x.s.now[0] + 10**9)
    value = strict(bytes(x.b.buffer)[4:].decode())
    value["kind"] = "UNKNOWN"
    x.b.buffer = bytearray(encode(value))
    with pytest.raises(ValueError):
        x.child_channel.receive(deadline_ns=x.s.now[0] + 10**9)
    assert x.child_channel.failed


def test_broker_refuses_raw_request_not_received_through_bound_channel():
    f = rpc_fixture()
    with pytest.raises(ValueError):
        f.broker.serve_message(
            {"kind": "REQUEST", "payload": {}}, deadline_ns=f.x.s.now[0] + 10**9
        )
    assert not f.output.records


class PipeResponses:
    def __init__(self):
        self.buffers = {1: bytearray(), 2: bytearray(), 3: bytearray(), 4: bytearray()}
        self.now = 1
        self.on_pause = None
        self.maximum = 0

    def available(self, h):
        return len(self.buffers[h])

    def read(self, h, n):
        assert 0 < n <= len(self.buffers[h])
        raw = bytes(self.buffers[h][:n])
        del self.buffers[h][:n]
        return raw

    def write(self, h, raw):
        assert len(self.buffers[h]) + len(raw) <= 4096
        self.buffers[h].extend(raw)
        self.maximum = max(self.maximum, len(self.buffers[h]))
        return len(raw)

    def pause(self):
        self.now += 1000
        if self.on_pause:
            self.on_pause()


def pipe_pair():
    api = PipeResponses()
    kw = {
        "api": api,
        "clock_ns": lambda: api.now,
        "verify_peer": lambda b: None,
        "session_tag": b"x" * 16,
        "capacities": {"data": 4096, "credit": 4096},
    }
    a = CreditedPipeEndpoint(
        read_handle=1, write_handle=2, credit_read=3, credit_write=4, **kw
    )
    b = CreditedPipeEndpoint(
        read_handle=2, write_handle=1, credit_read=4, credit_write=3, **kw
    )
    return api, a, b


def test_credited_transport_streams_larger_than_pipe_capacity_without_new_thread():
    api, a, b = pipe_pair()
    raw = b"1234567" * 3000
    received = []

    def drain():
        if api.available(2):
            received.append(b.read_exact(api.available(2), deadline_ns=10**9))

    api.on_pause = drain
    a.write_all(raw, deadline_ns=10**9)
    drain()
    a._credits()
    assert b"".join(received) == raw and a.outstanding == 0 and api.maximum <= 4096


@pytest.mark.parametrize("damage", ["tag", "sequence", "count"])
def test_credited_transport_rejects_replay_and_impossible_byte_credits(damage):
    import struct

    api, a, b = pipe_pair()
    a.write_all(b"payload", deadline_ns=10**9)
    credit = [b"x" * 16, 1, 7]
    credit[{"tag": 0, "sequence": 1, "count": 2}[damage]] = {
        "tag": b"z" * 16,
        "sequence": 2,
        "count": 8,
    }[damage]
    api.write(3, struct.pack("!16sQQ", *credit))
    with pytest.raises(ValueError):
        a.write_all(b"more", deadline_ns=10**9)
    assert a.failed


def test_credited_transport_missing_bytes_timeout_remains_unknown():
    api, a, b = pipe_pair()
    with pytest.raises(ValueError):
        b.read_exact(1, deadline_ns=2000)
    assert b.failed


def test_journal_write_error_closes_retained_native_handles_without_receipt():
    x = io_fixture()
    with x.guard.installed():
        guards.mkdir(ROOTS["E"])
        guards.mkdir(path_for("E", "journal"))
        directory = x.io.inspect(path_for("E", "journal"))["id"]
        native = NativeJournalIO(x.io, directory)
        h = native.create_new(
            path_for("E", "journal", "record-00000001.json"), directory
        )
        x.calls.write = lambda *a: (_ for _ in ()).throw(
            OSError("offline interrupted write")
        )
        with pytest.raises(OSError):
            native.write_exact(h, b"partial")
        assert (
            not native.open_files
            and not x.book.journal_live
            and not x.book.journal_batch
        )
        x.io.close_cache()
    assert not x.calls.handles


def test_output_write_failure_retains_unacknowledged_chunk_bytes():
    output = Output()
    output.fail = True
    stream = BoundedOutput(output, stream="stdout", maximum_bytes=64, chunk_bytes=16)
    with pytest.raises(OSError):
        stream.write("a" * 16)
    assert bytes(stream.buffer) == b"a" * 16 and not output.records


def controller_fixture():
    x = io_fixture()
    path = path_for("E", "reviewed.py")
    x.calls.rows[path] = {
        "id": [1, 300, 0],
        "kind": "file",
        "links": 1,
        "reparse": False,
        "path": path,
        "parent_id": [1, 2, 3],
    }
    x.calls.raw[path] = b"original source"
    import hashlib

    profile = {
        "session": "a" * 32,
        "executable": r"D:\reviewed\python.exe",
        "images": {"pinned": {}},
        "source_pins": {path: hashlib.sha256(x.calls.raw[path]).hexdigest()},
        "accounts": ACCOUNTS,
        "targets": {"financial_worker": path},
    }
    x.calls.open_image = x.calls.allocate
    controller = NativeController(
        files=x.calls,
        process_calls=None,
        cim_api=None,
        clock_ns=lambda: x.s.now[0],
        profile=profile,
    )
    controller.book = x.book
    return SimpleNamespace(**locals())


def test_controller_constructor_and_missing_process_factory_are_inert():
    f = controller_fixture()
    assert not f.x.calls.events and not f.controller.initialized
    with pytest.raises(ValueError, match="FACTORY_REQUIRED"):
        f.controller.initialize(None)
    assert not f.x.calls.events


@pytest.mark.parametrize(
    "damage", ["hash", "path", "hardlink", "reparse", "read", "close"]
)
def test_original_handle_source_pins_refuse_invalid_or_incompletely_closed_files(
    damage,
):
    f = controller_fixture()
    if damage == "hash":
        f.x.calls.raw[f.path] = b"changed"
    elif damage == "hardlink":
        f.x.calls.rows[f.path]["links"] = 2
    elif damage == "reparse":
        f.x.calls.rows[f.path]["reparse"] = True
    elif damage == "read":
        f.x.calls.read = lambda *a: (_ for _ in ()).throw(OSError("offline read error"))
    elif damage == "close":
        f.x.calls.fail_close = True
    with pytest.raises((ValueError, OSError)):
        f.controller.verify_source(r"D:\unreviewed.py" if damage == "path" else f.path)
    if damage != "close":
        assert not f.x.calls.handles
    else:
        assert f.x.book.live


def test_original_handle_source_verification_returns_actual_identity_and_closed_proof():
    f = controller_fixture()
    proof = f.controller.verify_source(f.path)
    assert proof == {
        "path": f.path,
        "file_id": [1, 300, 0],
        "sha256": f.profile["source_pins"][f.path],
        "closed": True,
    }
    assert not f.x.book.live and not f.x.calls.handles


def test_bootstrap_reservation_cannot_be_modified_after_ledger_construction():
    from test_aip06_harness import Journal

    s = resources()
    boot = BootstrapBudget(lambda: s.now[0])
    owner = row(10, 8)
    key = boot.bind_owner(owner)
    boot.reserve(key, "h", "handle")
    snapshot = boot.seal(owner)
    ledger = SharedResources(Journal(), clock_ns=lambda: s.now[0], bootstrap=snapshot)
    snapshot.resources.clear()
    snapshot.owner.clear()
    ledger.register_owner(owner, controller=True)
    assert ledger.state["resources"]["h"]["owner"] == key


@pytest.mark.parametrize("closed", [True, False])
def test_sqlite_release_requires_closed_database_not_an_arbitrary_programming_error(
    closed,
):
    import sqlite3

    x = io_fixture()
    key = "sqlite-proof"
    x.s.ledger.reserve(x.s.controller, key, "handle")
    x.io.begin(x.s.controller, key, "handle", None)
    if closed:
        db = sqlite3.connect(":memory:")
        db.close()
        x.io.note_closed(x.s.controller, key, db)
        assert x.io.closed(x.s.controller, key)
    else:
        db = SimpleNamespace(
            execute=lambda *a: (_ for _ in ()).throw(
                sqlite3.ProgrammingError(
                    "SQLite objects created in a thread can only be used in that same thread."
                )
            )
        )
        with pytest.raises(ValueError):
            x.io.note_closed(x.s.controller, key, db)
        assert not x.io.closed(x.s.controller, key)


def test_controller_never_accepts_legacy_cleanup_booleans_as_independent_proof():
    f = controller_fixture()
    f.controller.guard = f.x.guard
    f.controller.initialized = True
    with pytest.raises(ValueError, match="RETAINED_EXIT_AND_RELEASE_PORT_NOT_BOUND"):
        f.controller.verify_probe_result(
            {"cleanup": {"handles_closed": True, "job_members": []}}
        )
