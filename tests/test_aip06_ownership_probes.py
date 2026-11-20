"""Actual probe/endpoint providers, injected Windows responses; no native launch."""

import copy
from types import SimpleNamespace

import pytest

from app.services.paper_financial_replay import digest
from scripts.observation_runtime.aip06_ownership_probes import OwnershipProbes
from scripts.observation_runtime.aip06_remote_handles import RetainedPeerHandles
from scripts.observation_runtime.aip06_windows_endpoints import WindowsChildEndpoints
from test_aip06_physical_path import probe_fixture, _dmtf
from test_aip06_native_session_stop import EXE
from test_aip06_windows_adapters import ACCOUNTS


def fixture(child=False):
    x = probe_fixture()
    x.c.profile["accounts"] = copy.deepcopy(ACCOUNTS)
    x.endpoints = WindowsChildEndpoints(
        pipe_calls=None, clock_ns=lambda: x.now[0], output=x.c.legacy_probes.output
    )
    x.protocol.endpoints = x.endpoints
    x.child = None
    if child:
        x.child = x.guard.spawn([EXE, "-B", x.targets["financial_worker"]])
        s = x.child.child
        x.peer = RetainedPeerHandles(
            binding=s.binding,
            resources=x.ledger,
            calls=x.calls,
            files=x.files,
            allocations=x.alloc,
            allowed_path=None,
            objects=SimpleNamespace(),
        )
        x.endpoints.state[s.plan["request"].nonce] = {
            "child": s,
            "port": x.port,
            "closed": False,
            "verifier": x.peer,
        }
    x.cuts = []

    def read(**kw):
        rows = []
        for row in x.calls.rows.values():
            if row["pid"] in x.calls.exits:
                continue
            rows.append(
                {
                    "ProcessId": row["pid"],
                    "ParentProcessId": row["parent_pid"],
                    "CreationDate": _dmtf(row["created"]),
                    "ExecutablePath": row["image"],
                    "CommandLine": row["command_line"],
                }
            )
        result = {
            "rows": rows,
            "complete": True,
            "error": None,
            "started_ns": x.now[0],
            "finished_ns": x.now[0],
        }
        x.cuts.append((kw, copy.deepcopy(result)))
        return x.damage(result)

    x.damage = lambda result: result
    x.tables = SimpleNamespace(read=read)
    x.probes = OwnershipProbes(x.port, x.tables, x.c.legacy_probes.output)
    x.port.ownership_probes = x.probes
    x.run = lambda case="supervisor": x.port.ownership_probe(
        case, deadline_ns=x.now[0] + 5 * 10**9
    )
    return x


@pytest.mark.parametrize("case", ["supervisor", "unexpected-child"])
@pytest.mark.parametrize("child", [False, True])
def test_current_original_supervisor_and_complete_child_cut(case, child):
    x = fixture(child)
    before = set(x.calls.handles)
    value = x.run(case)
    assert value["supervisor"] == x.parent and len(value["descendants"]) == int(child)
    assert (
        value["domain"] == "DISPOSABLE"
        and not value["financial_ack"]
        and not value["native_acceptance"]
    )
    assert value["accounts"] == digest(ACCOUNTS) and x.probes.verify(value) == value
    assert x.cuts[0][0]["deadline_ns"] == value["started_ns"] + 5 * 10**9
    assert set(x.calls.handles) == before
    if child:
        x.calls.finish(x.child.child)
        x.child.close()
        assert not x.port.all_members()


@pytest.mark.parametrize(
    "damage",
    [
        "stale-supervisor",
        "wrong-job",
        "missing-supervisor",
        "unexpected",
        "missing-child",
        "conflict",
        "incomplete",
        "stale-cut",
        "timeout",
        "resource-owner",
        "account",
        "parent",
        "command",
        "birth",
        "image",
        "cycle",
        "missing-peer",
        "foreign-ledger",
        "opaque-native",
        "missing-object",
    ],
)
def test_probe_fails_closed_on_missing_or_contradictory_evidence(damage):
    x = fixture(True)
    pid = x.child.pid
    if damage == "stale-supervisor":
        x.calls.rows[10]["created"] += 1
    elif damage == "wrong-job":
        x.calls.jobs[x.aggregate.job]["members"].discard(10)
    elif damage == "resource-owner":
        x.ledger.reserve(x.owner, "unbound", "launch")
    elif damage == "account":
        x.port.guard.owner = "f" * 64
    elif damage == "cycle":
        x.child.child.binding.runtime["parent_pid"] = pid
    elif damage == "missing-peer":
        x.endpoints.state.clear()
    elif damage == "foreign-ledger":
        x.peer.resources = SimpleNamespace()
    elif damage == "opaque-native":
        x.peer.objects = None
    elif damage == "missing-object":
        x.ledger.reserve(x.peer.owner, "unproved", "pipe")

    def mutate(cut):
        if damage == "missing-supervisor":
            cut["rows"] = [r for r in cut["rows"] if r["ProcessId"] != 10]
        elif damage == "unexpected":
            extra = copy.deepcopy(cut["rows"][-1])
            extra["ProcessId"] = 777
            cut["rows"].append(extra)
        elif damage == "missing-child":
            cut["rows"] = [r for r in cut["rows"] if r["ProcessId"] != pid]
        elif damage == "conflict":
            cut["rows"].append(copy.deepcopy(cut["rows"][-1]))
        elif damage == "incomplete":
            cut["complete"] = False
        elif damage == "stale-cut":
            cut["started_ns"] -= 1
        elif damage == "timeout":
            x.now[0] += 5 * 10**9
        elif damage == "parent":
            cut["rows"][-1]["ParentProcessId"] = 888
        elif damage == "command":
            cut["rows"][-1]["CommandLine"] += " changed"
        elif damage == "birth":
            cut["rows"][-1]["CreationDate"] = _dmtf(x.parent["created"] + 100)
        elif damage == "image":
            cut["rows"][-1]["ExecutablePath"] = r"D:\foreign.exe"
        return cut

    x.damage = mutate
    with pytest.raises((ValueError, KeyError)):
        x.run("unexpected-child")
    assert x.probes.failed and x.guard.failed and x.port.failed
    with pytest.raises(ValueError):
        x.run()
    assert not x.probes.retained


@pytest.mark.parametrize("damage", ["result", "account", "head", "stale", "foreign"])
def test_retained_probe_receipt_cannot_cross_revision_account_or_lifetime(damage):
    x = fixture()
    value = x.run()
    if damage == "result":
        value["supervisor"]["created"] += 1
    elif damage == "account":
        x.c.profile["accounts"] = {}
    elif damage == "head":
        x.ledger.reserve(x.owner, "after-probe", "handle")
    elif damage == "stale":
        x.now[0] += 5 * 10**9
    else:
        x.probes = OwnershipProbes(x.port, x.tables, x.c.legacy_probes.output)
    with pytest.raises(ValueError):
        x.probes.verify(value)
    assert x.probes.failed


@pytest.mark.parametrize(
    "damage", [None, "reused", "kind", "birth", "close", "missing", "timeout"]
)
def test_complete_native_object_inspection_uses_original_peer_and_reserves_before_duplicate(
    damage,
):
    x = fixture(True)
    key = "remote-thread"
    x.ledger.reserve(x.peer.owner, key, "thread")
    ticket = x.alloc.reserve("retained-object", "handle")
    x.peer.live[key] = {
        "remote": 900,
        "local": 901,
        "ticket": ticket,
        "verified": True,
        "identity": {"type": "Thread", "pid": x.child.pid, "created": 50},
    }
    held, closed = [], []

    def duplicate(source, remote):
        assert source == x.peer.binding.runtime_handle and remote == 900
        assert any("probe-object:" in k for k in x.alloc.live)
        held.append(902)
        return 902

    original_duplicate, original_close = x.calls.duplicate, x.calls.close
    x.calls.duplicate = duplicate

    def close(handle):
        if handle == 902:
            closed.append(handle)
            return
        return original_close(handle)

    x.calls.close = close
    original_closed = x.calls.closed
    x.calls.closed = lambda h: (
        (h in closed and damage != "close") if h == 902 else original_closed(h)
    )
    native = dict(x.peer.live[key]["identity"])
    if damage == "kind":
        native["type"] = "Process"
    if damage == "birth":
        native["created"] += 1
    if damage == "missing":
        x.peer.live.clear()
    if damage == "timeout":
        x.now[0] += 6 * 10**9
    x.peer.objects = SimpleNamespace(
        same=lambda a, b: damage != "reused", observe=lambda h: native
    )
    deadline = x.now[0] + (0 if damage == "timeout" else 5 * 10**9)
    if damage:
        with pytest.raises(ValueError):
            x.peer.probe_native_objects(deadline_ns=deadline)
    else:
        assert x.peer.probe_native_objects(deadline_ns=deadline)[0]["key"] == key
    if held:
        assert closed == [902]
        assert any("probe-object:" in k for k in x.alloc.live) == (damage == "close")
    x.calls.duplicate = original_duplicate


def test_controller_entry_points_use_one_current_collector_and_original_deadline():
    x = fixture()
    first = x.c.probe_supervisor(deadline_ns=x.now[0] + 10**9)
    second = x.c.probe_unexpected_children(deadline_ns=x.now[0] + 10**9)
    assert first["case"] == "supervisor" and second["case"] == "unexpected-child"
    assert len(x.probes.retained) == 2 and len(x.records) == 2


@pytest.mark.parametrize(
    "damage",
    [
        "original-handle",
        "handle-ticket",
        "account-scope",
        "missing-root",
        "bad-deadline",
    ],
)
def test_no_root_handle_or_account_substitution(damage):
    x = fixture()
    if damage == "original-handle":
        x.aggregate.controller_handle = x.calls.duplicate(-1, -1)
    elif damage == "handle-ticket":
        x.aggregate.held.pop(0)
    elif damage == "account-scope":
        x.c.profile["accounts"] = {}
    elif damage == "missing-root":
        x.port.aggregate = None
    with pytest.raises(ValueError):
        x.probes.collect(
            "supervisor",
            deadline_ns=None if damage == "bad-deadline" else x.now[0] + 10**9,
        )
    assert x.probes.failed and x.guard.failed


def test_real_factory_connects_guarded_cim_table_and_allocation_provider(monkeypatch):
    from scripts.observation_runtime.aip06_cleanup_providers import CimTables
    from scripts.observation_runtime.aip06_windows_process import CancellableCalls
    from test_aip06_physical_native_proofs import TableResponses

    x = fixture()
    x.c.cim_api = TableResponses(x.tables.read()["rows"])
    x.port.ownership_probes = None
    original = CancellableCalls.run
    observed = []

    def run(self, callback, **kw):
        assert self.allocations is x.alloc and self.calls is x.calls
        observed.append(kw["deadline_ns"])
        return callback()  # injected Windows worker boundary, no native thread

    monkeypatch.setattr(CancellableCalls, "run", run)
    result = x.c.probe_supervisor(deadline_ns=x.now[0] + 10**9)
    assert type(x.port.ownership_probes.tables) is CimTables and len(observed) == 1
    assert result["case"] == "supervisor" and not x.alloc.live - {
        k for k, _ in x.aggregate.held
    }
    assert x.c.cim_api.events[-1] == "uninitialize"
    assert original is not CancellableCalls.run


def test_recursive_retained_queries_share_absolute_deadline_and_restore_context():
    from scripts.observation_runtime.aip06_windows_process import NativeProcessObserver

    x = fixture(True)
    original = x.cim.process
    bounds = []

    def process(pid, *, deadline_ns):
        bounds.append(deadline_ns)
        x.now[0] += 10**8
        return original(pid, deadline_ns=deadline_ns)

    x.cim.process = process
    start = x.now[0]
    with pytest.raises(ValueError):
        x.probes.collect("unexpected-child", deadline_ns=start + 5 * 10**8)
    assert bounds and all(t <= start + 5 * 10**8 for t in bounds) and x.probes.failed
    # The failed probe cannot leak a short deadline into unrelated observers.
    api = NativeProcessObserver(
        calls=x.calls, cim=x.cim, images=x.port.pinned_images, clock_ns=lambda: x.now[0]
    )
    api.parent = x.aggregate.controller_handle
    api.observe(api.parent)
    assert bounds[-1] > start + 5 * 10**8


def test_provenance_output_failure_is_latched_without_an_ack():
    x = fixture()

    class BrokenOutput:
        def append(self, record):
            raise OSError("injected output failure")

    x.probes.output = BrokenOutput()
    with pytest.raises(OSError):
        x.run()
    assert (
        x.probes.failed and not x.probes.retained and x.probes.failure["output_failed"]
    )


def test_new_native_object_without_ledger_reservation_cannot_be_adopted():
    x = fixture(True)
    x.peer.live["undeclared"] = {"remote": 777, "local": 888, "verified": True}
    with pytest.raises(ValueError, match="INCOMPLETE"):
        x.run("unexpected-child")
    assert x.probes.failed


def test_real_evidence_output_receipt_binds_post_publication_journal_cut():
    from scripts.observation_runtime.aip06_outputs import EvidenceOutput
    from scripts.observation_runtime.aip06_harness import ROOTS, path_for

    x = fixture()
    with x.guard.installed():
        x.guard.mkdir(ROOTS["E"])
        directory = path_for("E", "probe-output")
        x.guard.mkdir(directory)
        output = EvidenceOutput(
            x.guard,
            directory=directory,
            producer={
                "session": x.c.profile["session"],
                "owner": x.owner,
                "role": "OFFLINE_SOURCE_TEST",
                "source_pins": x.c.profile["source_pins"],
            },
        )
        x.probes.output = output
        value = x.run()
        publication = x.probes.publications[value["nonce"]]
        assert value["head"] != x.ledger.head == publication["head"]
        assert publication["receipt"]["head"] == output.head
        assert x.probes.verify(value) == value
        raw = x.io.read_bytes(publication["receipt"]["path"])
        assert raw and output.sequence == 1


def test_late_publication_does_not_create_retained_passing_receipt():
    x = fixture()
    records = []

    def append(value):
        records.append(value)
        x.now[0] += 5 * 10**9

    x.probes.output = SimpleNamespace(append=append)
    with pytest.raises(ValueError, match="PUBLICATION_LATE"):
        x.run()
    assert x.probes.failed and not x.probes.retained and not x.probes.publications
    assert records[-1]["schema"] == "AIP06_OWNERSHIP_PROBE_FAILURE_V1"


@pytest.mark.parametrize("damage", [None, "path"])
def test_retained_native_file_is_included_in_complete_object_inventory(damage):
    x = fixture(True)
    key = "bound-source-file"
    x.ledger.reserve(x.peer.owner, key, "file", entries=1, size=1)
    original = {
        "type": "File",
        "path": r"D:\reviewed\source.py",
        "native": {"id": [1, 2, 3], "reparse": False, "links": 1, "kind": "file"},
    }
    x.peer.live[key] = {
        "remote": 900,
        "local": 901,
        "verified": True,
        "identity": copy.deepcopy(original),
    }
    current = copy.deepcopy(original)
    if damage:
        current["path"] = r"D:\foreign\source.py"
    observed = []
    x.peer.allowed_path = observed.append
    duplicate, close, closed = x.calls.duplicate, x.calls.close, x.calls.closed
    x.calls.duplicate = lambda peer, h: 902
    x.calls.close = lambda h: None if h == 902 else close(h)
    x.calls.closed = lambda h: True if h == 902 else closed(h)
    x.peer.objects = SimpleNamespace(
        same=lambda a, b: a == 901 and b == 902, observe=lambda h: current
    )
    if damage:
        with pytest.raises(ValueError, match="FILE_CHANGED"):
            x.peer.probe_native_objects(deadline_ns=x.now[0] + 10**9)
    else:
        assert (
            x.peer.probe_native_objects(deadline_ns=x.now[0] + 10**9)[0]["key"] == key
        )
        assert observed == [original["path"]]
    x.calls.duplicate = duplicate
