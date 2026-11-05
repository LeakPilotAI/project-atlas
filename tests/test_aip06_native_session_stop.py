"""Injected Windows responses only. No native loaders, children or acceptance."""

import copy
import hashlib
import ntpath
from subprocess import list2cmdline
from types import SimpleNamespace

import pytest

from app.services.paper_financial_replay import digest
from test_aip06_harness import Journal, financial_fixture
from test_aip06_fixture_guard_integration import IO
from test_aip06_windows_adapters import ACCOUNTS
from test_launch_ownership import row
from scripts.observation_runtime.aip06_fixture_guard import FixtureGuard
from scripts.observation_runtime.aip06_harness import (
    BASE,
    ROOTS,
    SCOPE_HASH,
    FixturePaths,
    SharedResources,
    WorkerOwnership,
)
from scripts.observation_runtime.aip06_native_controller import NativeAllocations
from scripts.observation_runtime.aip06_native_session import NativeSessionFactory
from scripts.observation_runtime.aip06_intrinsic_io import IntrinsicJournalIO
from scripts.observation_runtime.aip06_remote_handles import RetainedPeerHandles
from scripts.observation_runtime.aip06_stop import (
    GuardedStopCollector,
    RetainedFinancialReply,
)

IMAGE = b"INJECTED_WINDOWS_IMAGE_NOT_NATIVE_PROOF"
EXE = r"D:\synthetic\python.exe"
PIN = {"file_id": [1, 2, 3], "sha256": hashlib.sha256(IMAGE).hexdigest()}


class NativeResponses:
    def __init__(self, parent):
        self.next = 100
        self.handles = {}
        self.jobs = {}
        self.rows = {10: copy.deepcopy(parent)}
        self.exits = {}
        self.events = []
        self.fail = None

    def allocate(self, kind, value=None):
        self.next += 1
        self.handles[self.next] = (kind, value)
        return self.next

    def current(self):
        return -1

    def duplicate(self, source, h):
        if source != -1:
            error = OSError("injected invalid remote handle")
            error.winerror = 6
            raise error
        assert h == -1
        return self.allocate("parent", 10)

    def native(self, h):
        pid = 10 if h == -1 else self.handles[h][1]
        r = self.rows[pid]
        return {k: r[k] for k in ("pid", "created", "image")}

    def lifecycle(self, h):
        value = self.native(h)
        return {k: value[k] for k in ("pid", "created")} | {
            "exited": value["pid"] in self.exits,
            "exit_code": self.exits.get(value["pid"], 259),
        }

    def create_job(self, name, limits):
        h = self.allocate("job")
        self.jobs[h] = {"limits": copy.deepcopy(limits), "members": set()}
        self.events.append("job")
        return h

    def job_limits(self, h):
        return self.jobs[h]["limits"]

    def members(self, h):
        return self.jobs[h]["members"].copy()

    def assign(self, job, h):
        if self.fail == "assign":
            raise OSError("injected assignment refusal")
        self.jobs[job]["members"].add(self.native(h)["pid"])
        self.events.append("assign")

    def in_job(self, h, job):
        return self.native(h)["pid"] in self.members(job)

    def create_suspended(self, **kw):
        self.events.append("create-suspended")
        if self.fail == "create":
            raise OSError("injected create refusal")
        pid = 20 + len([p for p in self.rows if p != 10]) * 10
        self.rows[pid] = row(pid, 10, image=ntpath.normcase(EXE))
        self.rows[pid].update(
            sha256=PIN["sha256"], command_line=list2cmdline(kw["argv"])
        )
        return self.allocate("process", pid), self.allocate("thread", pid), pid, pid + 1

    def resume(self, h):
        self.events.append("resume")

    def wait(self, h, end):
        if not self.lifecycle(h)["exited"]:
            raise ValueError("injected termination missing")

    def close(self, h):
        assert h in self.handles
        self.events.append("close")
        del self.handles[h]

    def closed(self, h):
        return h not in self.handles

    def terminate_owned_job(self, job):
        for pid in self.members(job):
            self.exits[pid] = 71
        self.jobs[job]["members"].clear()
        self.events.append("terminate-owned-job")

    def terminate_created(self, h, expected):
        assert self.native(h) == expected
        self.exits[expected["pid"]] = 71
        self.events.append("terminate-original-created-handle")

    def finish(self, child):
        pid = self.native(child.launch_handle)["pid"]
        self.exits[pid] = 0
        self.jobs[child.job]["members"].clear()


class Files:
    def __init__(self, calls):
        self.calls = calls

    def open_image(self, path):
        return self.calls.allocate("image", path)

    def describe(self, h):
        return {"id": [1, 2, 3], "kind": "file", "links": 1, "reparse": False}

    def read(self, h, maximum):
        return IMAGE


class Wire:
    def __init__(self, child, accounts):
        self.child = child
        self.accounts = accounts
        self.queue = []
        self.sent = []
        self.binding = {}

    def send(self, kind, payload, *, deadline_ns):
        self.sent.append((kind, copy.deepcopy(payload)))
        if kind == "STOP":
            self.queue = [
                ("ACK", copy.deepcopy(payload)),
                (
                    "DRAIN",
                    {
                        "scope": SCOPE_HASH,
                        "operation_id": payload["request"]["operation_id"],
                        "pending": 0,
                        "unknown": False,
                        "orders": 0,
                    },
                ),
            ]

    def receive(self, *, deadline_ns, expected_kind=None):
        kind, value = self.queue.pop(0)
        assert kind == expected_kind
        return {"kind": kind, "payload": value}


class Protocol:
    resource_kinds = ("pipe", "pipe")

    def __init__(self, calls, clock):
        self.calls, self.clock = calls, clock
        self.damage = None
        self.events = []
        self.financial = None

    def command(self, argv, options, *, nonce):
        return tuple(argv) + ("--bound-nonce", nonce)

    def prepare(self, child, port):
        a, b = port.allocate(
            child,
            ("pipe", "pipe"),
            lambda: (self.calls.allocate("pipe"), self.calls.allocate("pipe")),
        )
        return {
            "environment": {},
            "cwd": ntpath.dirname(ntpath.dirname(BASE)),
            "inherit_handles": [a, b],
            "stdin": a,
            "stdout": b,
            "stderr": b,
        }

    def ready(self, child, observed, **bounds):
        child.channel = Wire(child, copy.deepcopy(ACCOUNTS))
        self.events.append("hello")
        if self.damage == "job":
            self.calls.jobs[child.job]["members"].add(999)
        if self.damage == "command":
            self.calls.rows[observed["pid"]]["command_line"] = "wrong"
        return {
            "pid": observed["pid"],
            "nonce": child.plan["request"].nonce,
            "role": child.plan['request'].role,
        }

    def bind(self, child, *, snapshot, roots, source_pins, target):
        self.events.append("bind")
        child.channel.binding = {
            "child": child.binding.runtime,
            "parent": child.binding.parent,
        }
        result = {
            "scope": SCOPE_HASH,
            "nonce": child.plan["request"].nonce,
            "owner": digest(child.binding.runtime),
            "reservation_head": snapshot["head"],
            "guarded": True,
        }
        if self.damage == "receipt":
            result["owner"] = "wrong"
        return result

    def release(self, child, **payload):
        self.events.append("release")

    def communicate(self, child, value, **limits):
        if self.damage != "missing-exit":
            self.calls.finish(child)
        return "", ""

    def exchange_reader(self, child, value, **limits):
        return {"request": value["request"], "financial": copy.deepcopy(self.financial)}

    def close(self, child, *, deadline_ns):
        self.events.append("close")

    def ack_reader(self, child, request, financial):
        assert self.calls.lifecycle(child.launch_handle)["exited"] is False
        self.events.append("reader-received")


def fixture():
    now = [10**9]
    ledger = SharedResources(Journal(), clock_ns=lambda: now[0])
    parent = row(10, 8, image=ntpath.normcase(EXE))
    parent["sha256"] = PIN["sha256"]
    owner = ledger.register_owner(parent, controller=True)
    calls = NativeResponses(parent)
    files = Files(calls)
    io = IO()
    targets = {
        "financial_worker": r"D:\reviewed\worker.py",
        "readonly_reader": r"D:\reviewed\reader.py",
    }
    profile = {
        "executable": EXE,
        "images": {ntpath.normcase(EXE): PIN},
        "targets": targets,
        "source_pins": {p: "a" * 64 for p in targets.values()},
    }
    controller = SimpleNamespace(
        calls=calls,
        files=files,
        clock=lambda: now[0],
        profile=profile,
        verify_source=lambda p: {
            "path": p,
            "file_id": [1, 2, 3],
            "sha256": "a" * 64,
            "closed": True,
        },
    )

    def query(pid, **kw):
        return {
            k: v for k, v in calls.rows[pid].items() if k not in ("file_id", "sha256")
        }

    cim = SimpleNamespace(process=query)
    alloc = NativeAllocations(ledger, owner)
    protocol = Protocol(calls, lambda: now[0])
    port = NativeSessionFactory(protocol)(controller, ledger, io, cim, alloc)
    roster = WorkerOwnership(ledger, all_members=port.all_members)
    guard = FixtureGuard(
        resources=ledger,
        paths=FixturePaths(io),
        ownership=roster,
        owner=owner,
        io=io,
        processes=port,
        clock_ns=lambda: now[0],
    )
    port.bind_guard(guard)
    return SimpleNamespace(**locals())


def test_actual_native_factory_drives_real_guard_roster_and_release_with_injected_windows():
    x = fixture()
    with x.guard.installed():
        child = x.guard.spawn([EXE, "-B", x.targets["financial_worker"]])
        assert child.child.target_released and x.protocol.events[:3] == [
            "hello",
            "bind",
            "release",
        ]
        assert x.calls.events.index("assign") < x.calls.events.index("resume")
        assert child.identity()["parent_pid"] == 10
        child.communicate()
        assert child.closed and not x.calls.handles and x.port.all_members() == set()
        assert all(r["closed"] for r in x.ledger.state["resources"].values())


@pytest.mark.parametrize("damage", ["job", "command", "receipt", "missing-exit"])
def test_actual_session_factory_refuses_conflicting_release_or_unterminated_worker(
    damage,
):
    x = fixture()
    x.protocol.damage = damage
    with pytest.raises(ValueError), x.guard.installed():
        child = x.guard.spawn([EXE, "-B", x.targets["financial_worker"]])
        child.communicate()
    assert x.guard.failed
    if damage != "missing-exit":
        assert "release" not in x.protocol.events


def test_failed_create_closes_only_retained_session_resources_and_latches_refusal():
    x = fixture()
    x.calls.fail = "create"
    with pytest.raises(OSError), x.guard.installed():
        x.guard.spawn([EXE, "-B", x.targets["financial_worker"]])
    assert not x.calls.handles and x.port.failed


def test_no_reservation_means_no_create_or_job_effect():
    x = fixture()
    plan = x.port.plan((EXE, "-B", x.targets["financial_worker"]), {})
    with pytest.raises(ValueError):
        x.port.create_suspended(
            plan, {}, (EXE, "-B", x.targets["financial_worker"]), {}
        )
    assert not x.calls.events


def test_retained_remote_file_release_uses_original_peer_handle_not_pid_or_declaration():
    x = fixture()
    with x.guard.installed():
        child = x.guard.spawn([EXE, "-B", x.targets["financial_worker"]])
        binding = child.child.binding
        owner = digest(binding.runtime)
        key = "child-owned-file"
        x.ledger.reserve(owner, key, "handle")
        actual_duplicate = x.calls.duplicate
        x.calls.duplicate = lambda source, h: (
            x.calls.allocate("file", h)
            if source == binding.runtime_handle
            else actual_duplicate(source, h)
        )
        files = SimpleNamespace(
            describe=lambda h: {
                "id": [1, 20, 0],
                "kind": "file",
                "links": 1,
                "reparse": False,
            },
            final_path=lambda h: ROOTS["P"] + "\\x",
        )
        peer = RetainedPeerHandles(
            binding=binding,
            resources=x.ledger,
            calls=x.calls,
            files=files,
            allocations=x.alloc,
            allowed_path=x.guard.locate,
        )
        wire = {"child": binding.runtime, "parent": binding.parent}
        peer.bind_native_handle(wire, key, 400)
        with pytest.raises(ValueError, match="LIVE_OR_REUSED"):
            peer.release_observer(
                wire, key, {"owner": owner, "key": key, "handle": 400}
            )
        x.calls.duplicate = actual_duplicate
        assert peer.release_observer(
            wire, key, {"owner": owner, "key": key, "handle": 400}
        ).closed(owner, key)
        x.ledger.close(owner, key, observer=peer)
        child.communicate()
        assert not x.calls.handles


@pytest.mark.parametrize(
    "damage", ["unreserved", "foreign", "wrong-handle", "wrong-owner"]
)
def test_remote_handle_proof_refuses_wrong_owner_key_or_original_handle(damage):
    x = fixture()
    with x.guard.installed():
        child = x.guard.spawn([EXE, "-B", x.targets["financial_worker"]])
        b = child.child.binding
        peer = RetainedPeerHandles(
            binding=b,
            resources=x.ledger,
            calls=x.calls,
            files=None,
            allocations=x.alloc,
            allowed_path=x.guard.locate,
        )
        wire = {"child": b.runtime, "parent": b.parent}
        if damage == "foreign":
            wire["parent"] = row(99, 8)
        with pytest.raises(ValueError):
            if damage in ("wrong-handle", "wrong-owner"):
                peer.release_observer(
                    wire, "missing", {"handle": 400, "owner": "wrong", "key": "missing"}
                )
            else:
                peer.bind_native_handle(wire, "missing", 400)


def test_shared_intrinsic_journal_accounting_never_creates_recursive_event_or_resets():
    now = [100]
    meter = IntrinsicJournalIO(owner="owner", clock_ns=lambda: now[0], started_ns=100)
    for i in range(16):
        meter.acquire(str(i))
        meter.created(str(i), i + 100)
    with pytest.raises(ValueError):
        meter.acquire("overflow")
    with pytest.raises(ValueError):
        meter.quiescent()
    observer = SimpleNamespace(closed=lambda h: True)
    for i in range(16):
        meter.released(str(i), i + 100, observer=observer)
    proof = meter.quiescent()
    assert proof["reserved"] == proof["closed"] == 16
    meter.acquire("next")
    meter.no_allocation("next")
    assert meter.quiescent()["reserved"] == 17


@pytest.mark.parametrize(
    "damage", ["late", "false-close", "wrong-handle", "double-release"]
)
def test_intrinsic_journal_failure_does_not_erase_allocations(damage):
    now = [100]
    meter = IntrinsicJournalIO(owner="owner", clock_ns=lambda: now[0], started_ns=100)
    meter.acquire("h")
    meter.created("h", 100)
    if damage == "late":
        now[0] += 601 * 10**9
    with pytest.raises(ValueError):
        if damage == "late":
            meter.quiescent()
        else:
            meter.released(
                "h",
                101 if damage == "wrong-handle" else 100,
                observer=SimpleNamespace(closed=lambda h: damage != "false-close"),
            )
            meter.released("h", 100, observer=SimpleNamespace(closed=lambda h: True))


@pytest.mark.parametrize(
    "damage", [None, "ack", "drain", "missing-drain", "late", "reader", "late-exit"]
)
def test_collector_drives_actual_factory_two_lifetimes_then_original_financial_stop_verifier(
    damage,
):
    x = fixture()
    financial = financial_fixture()
    x.protocol.financial = financial
    reader = RetainedFinancialReply()
    events = []

    def sockets(**kw):
        events.append("sockets")
        now = x.now[0]
        return {
            "scope": SCOPE_HASH,
            "at_ns": now,
            "readers": {
                k: {
                    "complete": True,
                    "owned_endpoints": [],
                    "unknown": False,
                    "started_ns": now,
                    "finished_ns": now,
                }
                for k in ("CIM", "IP_HELPER", "NETSTAT")
            },
        }

    def processes(**kw):
        events.append("process")
        assert not x.port.all_members()
        now = x.now[0]
        return {
            "scope": SCOPE_HASH,
            "started_ns": now,
            "at_ns": now,
            "survivors": [],
            "unknown": False,
        }

    output = SimpleNamespace(append=lambda value: events.append("output"))
    collector = GuardedStopCollector(
        clock_ns=lambda: x.now[0],
        output=output,
        sockets=SimpleNamespace(collect=sockets),
        processes=SimpleNamespace(collect=processes),
        close_io=lambda: x.ledger.usage(memory={x.owner: 1000}, cpu_ns=1000),
    )
    with x.guard.installed():
        child = x.guard.spawn([EXE, "-B", x.targets["financial_worker"]])
        expected = {
            k: {f: v[f] for f in ("account_id", "manifest", "native_source")}
            for k, v in financial["accounts"].items()
        }
        req = x.guard.begin_stop(
            reader=reader,
            expected_accounts=expected,
            nonce=child.plan["request"].nonce,
            worker=child.identity(),
            operation_id="OFFLINE-STOP",
        )
        collector.send(child, req, revision=3)
        if damage == "ack":
            child.child.channel.queue[0][1]["revision"] = 2
        elif damage == "drain":
            child.child.channel.queue[1][1]["unknown"] = True
        elif damage == "missing-drain":
            child.child.channel.queue.pop()
        elif damage == "late":
            x.now[0] += 9 * 10**9
        elif damage == "reader":
            x.protocol.financial = None
        elif damage == "late-exit":
            original = x.protocol.communicate

            def late(*args, **kwargs):
                result = original(*args, **kwargs)
                x.now[0] += 9 * 10**9
                return result

            x.protocol.communicate = late
        if damage is not None:
            with pytest.raises((ValueError, IndexError)):
                collector.collect(
                    child,
                    x.guard,
                    req,
                    deadline_ns=x.guard.stop.started + 8 * 10**9,
                    reader_argv=[EXE, "-B", x.targets["readonly_reader"]],
                    reader_options={},
                    reader_input={"request": req},
                    reader=reader,
                )
            assert (
                collector.failed
                and x.guard.failed
                and x.ledger.state["stops"][req["operation_id"]]["state"] == "FAILED"
            )
            assert not x.calls.handles
            return
        evidence = collector.collect(
            child,
            x.guard,
            req,
            deadline_ns=x.guard.stop.started + 8 * 10**9,
            reader_argv=[EXE, "-B", x.targets["readonly_reader"]],
            reader_options={},
            reader_input={"request": req},
            reader=reader,
        )
        result = x.guard.finish_stop(**evidence)
        assert result["source_contract_passed"] and not result["native_acceptance"]
        assert events == ["sockets", "process", "output"] and not x.calls.handles


def test_actual_shared_native_journal_records_every_intrinsic_handle_lifetime():
    from test_aip06_windows_adapters import io_fixture
    from scripts.observation_runtime.aip06_fixture_guard import CreateNewJournal
    from scripts.observation_runtime.aip06_windows_io import NativeJournalIO

    x = io_fixture()
    with x.guard.installed():
        x.guard.mkdir(ROOTS["E"])
        x.guard.mkdir(ROOTS["E"] + "\\journal")
        identity = x.io.inspect(ROOTS["E"] + "\\journal")["id"]
        x.io.close_cache()
        meter = IntrinsicJournalIO(
            owner=x.s.controller, clock_ns=lambda: x.s.now[0], started_ns=x.s.now[0]
        )
        x.book.intrinsic = meter
        journal = CreateNewJournal(NativeJournalIO(x.io, identity), identity)
        shared = SharedResources(
            journal, clock_ns=lambda: x.s.now[0], intrinsic_io=meter
        )
        owner = copy.deepcopy(x.s.ledger.state["owners"][x.s.controller])
        owner["file_id"] = tuple(owner["file_id"])
        shared.register_owner(owner, controller=True)
        x.book.resources = shared
        before = meter.quiescent()["reserved"]
        shared.read()
        proof = meter.quiescent()
        assert (
            proof["reserved"] > before
            and proof["reserved"] == proof["closed"]
            and not x.calls.handles
        )


@pytest.mark.parametrize(
    "when,outcome,element",
    [
        ("setup", "skipped", "skipped"),
        ("setup", "failed", "error"),
        ("call", "failed", "failure"),
        ("call", "passed", None),
    ],
)
def test_native_junit_preserves_real_report_outcomes_and_uses_guarded_write(
    when, outcome, element
):
    import xml.etree.ElementTree as ET
    from scripts.observation_runtime.aip06_test_driver import GuardedJUnit

    x = fixture()
    path = ROOTS["E"] + "\\fixture.xml"
    with x.guard.installed():
        x.guard.mkdir(ROOTS["E"])
        writer = GuardedJUnit(x.guard, path)

        def report(phase, result):
            return SimpleNamespace(
                when=phase,
                outcome=result,
                nodeid="tests/test_example.py::test_case",
                duration=0.01,
                failed=result == "failed",
                skipped=result == "skipped",
                longrepr="injected test report",
            )

        writer.pytest_runtest_logreport(report(when, outcome))
        writer.pytest_runtest_logreport(report("teardown", "passed"))
        writer.pytest_sessionfinish(None, 0 if outcome == "passed" else 1)
        root = ET.fromstring(x.io.read_bytes(path))
        case = root.find(".//testcase")
        assert case is not None and (
            list(case) == [] if element is None else case.find(element) is not None
        )
        with pytest.raises(ValueError):
            writer.pytest_sessionfinish(None, 0)


def test_native_pytest_driver_uses_reviewed_modules_guarded_temps_and_outputs_only(
    monkeypatch,
):
    from scripts.observation_runtime.aip06_test_driver import run_reviewed_tests

    x = fixture()
    seen = []
    monkeypatch.setenv("PYTEST_DISABLE_PLUGIN_AUTOLOAD", "1")
    monkeypatch.setenv("PYTHONDONTWRITEBYTECODE", "1")
    x.port.verify_test_source = lambda path: seen.append(path)

    def pytest_main(args, plugins):
        assert (
            "--capture=sys" in args
            and "no:cacheprovider" in args
            and "no:faulthandler" in args
        )
        writer = plugins[1]
        for when in ("setup", "call", "teardown"):
            writer.pytest_runtest_logreport(
                SimpleNamespace(
                    nodeid="tests/test_qd_unified_shutdown.py::example",
                    when=when,
                    outcome="passed",
                    failed=False,
                    skipped=False,
                    duration=0.01,
                    longrepr="",
                )
            )
        writer.pytest_sessionfinish(None, 0)
        return 0

    with x.guard.installed():
        x.guard.mkdir(ROOTS["E"])
        result = run_reviewed_tests(
            modules=["tests/test_qd_unified_shutdown.py"],
            junit_leaf="qd.xml",
            pytest_main=pytest_main,
        )
        assert (
            result["cases"] == 1
            and result["exit_code"] == 0
            and not result["native_acceptance"]
        )
        assert seen == ["tests/test_qd_unified_shutdown.py"]
        with pytest.raises(ValueError):
            run_reviewed_tests(
                modules=["app/main.py"], junit_leaf="bad.xml", pytest_main=pytest_main
            )


def test_parent_frames_records_output_and_never_accepts_it_as_acknowledgement():
    from test_aip06_windows_adapters import channels, Output
    from scripts.observation_runtime.aip06_session_io import ParentFrames

    x = channels()
    output = Output()
    parent = ParentFrames(x.parent, broker=None, output=output)
    x.child_channel.send(
        "OUTPUT", {"text": "ACK is only text"}, deadline_ns=x.s.now[0] + 10**9
    )
    x.child_channel.send("ACK", {"actual": "frame"}, deadline_ns=x.s.now[0] + 10**9)
    result = parent.receive(deadline_ns=x.s.now[0] + 10**9, expected_kind="ACK")
    assert result["payload"] == {"actual": "frame"} and len(output.records) == 1


@pytest.mark.parametrize("damage", ["wrong-frame", "rpc-before-bind", "output-failure"])
def test_parent_frame_servicing_is_fail_closed(damage):
    from test_aip06_windows_adapters import channels, Output
    from scripts.observation_runtime.aip06_session_io import ParentFrames

    x = channels()
    output = Output()
    output.fail = damage == "output-failure"
    parent = ParentFrames(x.parent, broker=None, output=output)
    x.child_channel.send(
        "REQUEST"
        if damage == "rpc-before-bind"
        else "OUTPUT"
        if damage == "output-failure"
        else "DRAIN",
        {},
        deadline_ns=x.s.now[0] + 10**9,
    )
    with pytest.raises((ValueError, OSError)):
        parent.receive(deadline_ns=x.s.now[0] + 10**9, expected_kind="ACK")
    assert parent.failed


def test_queued_stop_is_reverified_and_cannot_be_reused_after_freshness_limit():
    from test_aip06_windows_adapters import channels
    from scripts.observation_runtime.aip06_windows_pump import Mailbox

    x = channels()
    mailbox = Mailbox(x.child_channel)
    x.parent.send("STOP", {"not_yet_consumed": True}, deadline_ns=x.s.now[0] + 10**9)
    x.parent.send("REPLY", {}, deadline_ns=x.s.now[0] + 10**9)
    mailbox.receive("REPLY", deadline_ns=x.s.now[0] + 10**9)
    x.s.now[0] += 7 * 10**9
    with pytest.raises(ValueError, match="STALE_QUEUED"):
        mailbox.receive("STOP", deadline_ns=x.s.now[0] + 10**9)


def test_unattributed_low_level_createprocess_audit_is_refused_without_launch():
    import sys

    x = fixture()
    with x.guard.installed(), pytest.raises(ValueError, match="UNOWNED_PROCESS"):
        sys.audit("_winapi.CreateProcess", "source-only-negative-test")


@pytest.mark.parametrize("damage", [None, "source", "identity", "account", "manifest"])
def test_owned_stop_assembly_fills_native_identity_only_from_current_verified_ready(
    damage,
):
    from scripts.observation_runtime.aip06_owned_stop import OwnedStopAssembly

    x = fixture()
    financial = financial_fixture()["accounts"]["QUALITY_DIPS"]
    assembly = OwnedStopAssembly(
        x.port,
        None,
        fixture_parameters=lambda: {
            k: copy.deepcopy(financial[k]) for k in ("account_id", "manifest")
        },
    )
    spec = assembly.spec(1, ROOTS["S1"], "1" * 32, r"D:\Work\Project Atlas")
    assert spec["expected_accounts"]["QUALITY_DIPS"]["native_source"] is None
    resources = {}
    for role in ("source", "projection", "report", "coordination"):
        path = ROOTS["S1"] + "\\account\\" + role
        x.io.add(path, "directory")
        resources[role] = {"path": path, "native_id": x.io.rows[path]["id"]}
    with x.guard.installed():
        child = x.guard.spawn(spec["argv"], **spec["options"])
        owner = child.identity()
        message = {
            "phase": "READY",
            "timing_channel": "1" * 32,
            "identity": {
                "pid": owner["pid"],
                "creation_filetime": owner["created"],
                "image": owner["image"],
            },
            "value": {
                "native": {
                    "account_id": financial["account_id"],
                    "epoch": financial["manifest"]["epoch"],
                    "resources": resources,
                },
                "manifest": copy.deepcopy(financial["manifest"]),
                "source_revision": 2,
            },
        }
        if damage == "source":
            message["value"]["native"]["resources"]["source"]["native_id"] = [
                99,
                99,
                99,
            ]
        elif damage == "identity":
            message["identity"]["creation_filetime"] += 1
        elif damage == "account":
            message["value"]["native"]["account_id"] = "foreign"
        elif damage == "manifest":
            message["value"]["manifest"]["epoch"] = "foreign"
        x.protocol.financial_ready = lambda *a, **kw: message
        if damage:
            with pytest.raises(ValueError):
                assembly.ready(child, timeout=40)
        else:
            assembly.ready(child, timeout=40)
            assert (
                spec["expected_accounts"]["QUALITY_DIPS"]["native_source"]
                == resources["source"]["native_id"]
            )
        child.communicate()


@pytest.mark.parametrize(
    "damage",
    [None, "projection", "revision", "currency", "pending", "hash-change", "rebind"],
)
def test_personal_financial_readback_preserves_existing_custody_checks_and_raw_events(
    damage,
):
    from test_aip06_windows_adapters import io_fixture
    from scripts.observation_runtime.aip06_stop import personal_financial_reply

    x = io_fixture()
    account = financial_fixture()["accounts"]["QUALITY_DIPS"]
    raw = {
        "schema": "QD_AUTO_OP_READ_V1",
        "manifest": account["manifest"],
        "rows": account["events"],
        "state": account["snapshot"],
        "head": account["source_head"],
        "source_pin": {"CURRENT": "INJECTED_OFFLINE_SOURCE"},
    }
    cut = {
        "source": raw["source_pin"],
        "state_digest": digest(raw["state"]),
        "source_revision": len(raw["rows"]),
    }
    native = {
        "account_id": account["account_id"],
        "epoch": account["manifest"]["epoch"],
        "resources": {"source": {"native_id": account["native_source"]}},
    }
    publication = {"status": "ACKNOWLEDGED"}
    proof = {"verified": damage != "projection"}
    if damage == "revision":
        cut["source_revision"] += 1
    elif damage == "currency":
        account["manifest"]["currency"] = "USDC"
        raw["manifest"] = account["manifest"]
    elif damage == "pending":
        publication["status"] = "UNKNOWN"

    def capture(now):
        if damage == "hash-change" and hasattr(capture, "called"):
            x.calls.raw[ROOTS["N"] + "\\cut.json"] = b"changed"
        capture.called = True
        return copy.deepcopy(cut), 1, copy.deepcopy(publication)

    selected = SimpleNamespace(
        read_committed=lambda *a: {"state": raw["state"]}, verify=lambda *a, **k: proof
    )
    with x.guard.installed():
        x.guard.mkdir(ROOTS["N"])
        x.guard.write(ROOTS["N"] + "\\cut.json", b"original")
        kwargs = {
            "guard": x.guard,
            "root": ROOTS["N"],
            "native": native,
            "manifest": account["manifest"],
            "native_reader": SimpleNamespace(read_committed=lambda: copy.deepcopy(raw)),
            "selected_reader": selected,
            "current": SimpleNamespace(_capture=capture),
            "clock": lambda: 1,
            "writer_rebind_refused": damage != "rebind",
        }
        if damage is None:
            result = personal_financial_reply(**kwargs)
            assert result["accounts"]["QUALITY_DIPS"]["events"] == account["events"]
            assert (
                result["before_hashes"] == result["after_hashes"]
                and len(result["acknowledgements"]["QUALITY_DIPS"]) == 4
            )
        else:
            with pytest.raises(ValueError):
                personal_financial_reply(**kwargs)
        x.io.close_cache()


def test_child_streams_keep_failed_output_and_never_allow_raw_file_descriptor():
    from scripts.observation_runtime.aip06_session_io import ChildText

    values = []
    port = SimpleNamespace(
        emit_output=values.append, guard=SimpleNamespace(owner="INJECTED_CHILD")
    )
    stream = ChildText(port, "stdout")
    stream.write('{"source":"OFFLINE"}\n')
    assert (
        values[0]["value"] == {"source": "OFFLINE"}
        and values[0]["text"] == '{"source":"OFFLINE"}'
    )
    failed = ChildText(
        SimpleNamespace(
            guard=port.guard,
            emit_output=lambda value: (_ for _ in ()).throw(
                OSError("injected delivery loss")
            ),
        ),
        "stderr",
    )
    with pytest.raises(OSError):
        failed.write("retain me\n")
    assert failed.buffer == "retain me\n"
    with pytest.raises(ValueError):
        failed.flush()
    with pytest.raises(ValueError):
        stream.fileno()


def test_assignment_failure_uses_original_creation_handle_for_cleanup_never_pid_adoption():
    x = fixture()
    x.calls.fail = "assign"
    with pytest.raises(OSError), x.guard.installed():
        x.guard.spawn([EXE, "-B", x.targets["financial_worker"]])
    assert not x.calls.handles and "terminate-original-created-handle" in x.calls.events


@pytest.mark.parametrize("event", ["socket.bind", "socket.connect"])
def test_native_fixture_audit_refuses_network_before_any_socket_operation(event):
    import sys

    x = fixture()
    with x.guard.installed(), pytest.raises(ValueError, match="NO_NETWORK"):
        sys.audit(event, "injected-socket", ("127.0.0.1", 1))


def test_remote_parent_duplicates_release_only_after_original_peer_exit():
    x = fixture()
    with x.guard.installed():
        child = x.guard.spawn([EXE, "-B", x.targets["financial_worker"]])
        b = child.child.binding
        owner = digest(b.runtime)
        x.ledger.reserve(owner, "remote-file", "handle")
        duplicate = x.calls.duplicate
        x.calls.duplicate = lambda source, h: (
            x.calls.allocate("remote-file", h)
            if source == b.runtime_handle
            else duplicate(source, h)
        )
        files = SimpleNamespace(
            describe=lambda h: {
                "id": [1, 20, 0],
                "kind": "file",
                "links": 1,
                "reparse": False,
            },
            final_path=lambda h: ROOTS["P"] + "\\file",
        )
        peer = RetainedPeerHandles(
            binding=b,
            resources=x.ledger,
            calls=x.calls,
            files=files,
            allocations=x.alloc,
            allowed_path=x.guard.locate,
        )
        peer.bind_native_handle(
            {"child": b.runtime, "parent": b.parent}, "remote-file", 20000
        )
        with pytest.raises(ValueError):
            peer.dispose_after_exit(deadline_ns=x.now[0] + 10**9)
        x.calls.finish(child.child)
        proof = peer.dispose_after_exit(deadline_ns=x.now[0] + 10**9)
        assert (
            proof["release_only"]
            and not proof["financial_ack"]
            and peer.closed(owner, "remote-file")
        )
        child.communicate()
        assert not x.calls.handles


@pytest.mark.parametrize("damage", [None, "request", "financial", "reader", "verified"])
def test_reader_waits_for_exact_transport_receipt_and_never_calls_it_financial_verification(
    damage,
):
    from scripts.observation_runtime.aip06_session_io import ChildSessionIO

    response = {
        "request": {"scope": SCOPE_HASH, "operation_id": "OFFLINE"},
        "financial": {"OFFLINE_ONLY": True},
    }
    receipt = {
        "schema": "AIP06_READER_RECEIVED_V1",
        "request": digest(response["request"]),
        "financial": digest(response["financial"]),
        "reader": "INJECTED-READER",
        "financial_verified": False,
    }
    if damage:
        receipt[{"verified": "financial_verified"}.get(damage, damage)] = (
            True if damage == "verified" else "wrong"
        )
    port = object.__new__(ChildSessionIO)
    port.reader_acked = False
    port.guard = SimpleNamespace(owner="INJECTED-READER")
    port.clock = lambda: 100
    port.channel = SimpleNamespace(receive=lambda **kw: {"payload": receipt})
    if damage:
        with pytest.raises(ValueError):
            port.wait_readonly_ack(response)
        assert not port.reader_acked
    else:
        port.wait_readonly_ack(response)
        assert port.reader_acked and receipt["financial_verified"] is False
        with pytest.raises(ValueError):
            port.wait_readonly_ack(response)


def test_successive_reader_lifetimes_bind_the_new_plan_without_losing_history_or_budget():
    x = fixture()
    argv = [EXE, "-B", x.targets["readonly_reader"]]
    with x.guard.installed():
        first = x.guard.spawn(argv)
        first.communicate()
        head = x.ledger.head
        # Same roster rotation as the existing three-sample guard, preserving
        # its one ledger, cumulative charges and original session capabilities.
        x.guard.ownership = WorkerOwnership(x.ledger, all_members=x.port.all_members)
        second = x.guard.spawn(argv)
        second.communicate()
        assert first.plan["request"].nonce != second.plan["request"].nonce
        assert (
            len(x.port.sessions) == 2 and x.ledger.head != head and not x.calls.handles
        )


def test_an_old_unallocated_plan_cannot_take_reservations_from_a_new_plan():
    x = fixture()
    old = x.port.plan((EXE, "-B", x.targets["readonly_reader"]), {})
    x.port.plan((EXE, "-B", x.targets["financial_worker"]), {})
    with pytest.raises(ValueError):
        x.port.preallocate(old, [])


def test_failed_stop_preserves_reserved_cleanup_time_without_creating_a_passing_stop():
    from test_aip06_harness import stop_fixture

    x = stop_fixture()
    started = x.s.ledger.state["started_ns"]
    meter = IntrinsicJournalIO(
        owner=x.s.controller, clock_ns=lambda: x.s.now[0], started_ns=started
    )
    meter.bind(x.s.ledger)
    x.s.ledger.intrinsic_io = meter
    x.s.now[0] = started + 541 * 10**9
    x.s.ledger.resolve_stop(x.request, "FAILED")
    assert x.s.ledger.state["mode"] == "STOP"
    assert meter.quiescent()["live"] == 0 and x.stop.result is None
    with pytest.raises(ValueError):
        x.s.ledger.reserve(x.s.controller, "new-work", "handle")
