"""Actual source entry points with inert interfaces; never a Windows worker.

AST extraction avoids importing native WinDLL modules. Executed bodies are
compiled from their actual repository files, not replicas of those functions.
"""

import ast
import copy
import hashlib
import json
import ntpath
import os
import sqlite3
import sys
from dataclasses import replace
from pathlib import Path
from subprocess import list2cmdline
from types import SimpleNamespace

import pytest
from app.services.paper_financial_replay import body, digest, replay_verified_events
from test_aip06_harness import Files, financial_fixture, resources, seeded, stop_fixture
from test_launch_ownership import setup as launch_fixture

from scripts.observation_runtime import aip06_fixture_guard as g
from scripts.observation_runtime.aip06_harness import (
    LIMITS,
    ROOTS,
    SCOPE_HASH,
    FixturePaths,
    SharedResources,
    WorkerOwnership,
    path_for,
)


class IO(Files):
    def __init__(self):
        super().__init__()
        self.data, self.effects, self.closed_handles = {}, [], set()
        self.next_id = 500
        self.release_ok = True

    def add(self, path, kind):
        self.next_id += 1
        parent = self.rows.get(ntpath.dirname(path), self.chain_rows[-1])
        self.rows[path] = {
            "path": path,
            "id": [1, self.next_id, 0],
            "parent_id": parent["id"],
            "kind": kind,
            "reparse": False,
            "links": 1,
        }

    def mkdir(self, path):
        assert path not in self.rows
        self.effects.append(("mkdir", path))
        self.add(path, "directory")

    def write_new(self, path, raw):
        assert path not in self.rows
        self.effects.append(("write", path))
        self.add(path, "file")
        self.data[path] = raw

    def readback(self, path):
        raw = self.data[path]
        return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}

    def read_bytes(self, path):
        return self.data[path]

    def replace_owned(self, source, target):
        self.effects.append(("replace", source, target))
        self.data[target] = self.data.pop(source)
        self.rows[target] = self.rows.pop(source)
        self.rows[target]["path"] = target

    def closed(self, owner, key):
        return self.release_ok

    def note_closed(self, owner, key, handle):
        self.closed_handles.add(key)

    def ancestors(self):
        return {r["path"] for r in self.chain_rows}

    def verify_handle(self, handle, path, module):
        assert type(handle) is g.OwnedNativeHandle
        assert path in self.ancestors() or path in self.rows

    def verify_mutex(self, handle, name, module):
        assert name.startswith("Global\\Atlas-Isolated-Fence-")

    def verify_token(self, handle, owner):
        assert type(handle) is g.OwnedNativeHandle and owner["pid"] == 10

    def verify_image(self, handle, path, pin):
        assert type(handle) is g.OwnedNativeHandle and len(pin["sha256"]) == 64

    def sqlite_open(self, path, **options):
        # Real SQLite in pytest's disposable directory; fake Windows namespace
        # metadata is explicitly NOT NTFS acceptance or native-root creation.
        value = str(path)
        if value.startswith("file:"):
            value = value.split("?", 1)[0][5:].lstrip("/").replace("/", "\\")
        if value not in self.rows:
            self.add(value, "file")
        target = self.database_root / (
            hashlib.sha256(value.encode()).hexdigest() + ".sqlite"
        )
        if options.get("uri"):
            target = target.as_uri() + (
                "?mode=ro" if "mode=ro" in str(path) else "?mode=rw"
            )
        return sqlite3.connect(target, **options)


@pytest.fixture(autouse=True)
def sqlite_fixture_path(tmp_path, monkeypatch):
    monkeypatch.setattr(IO, "database_root", tmp_path, raising=False)


class Processes:
    executable = r"D:\synthetic\python.exe"

    def __init__(self, s):
        self.s, self.children, self.events = s, [], []
        self.pinned_images = {
            ntpath.normcase(self.executable): {"file_id": [1, 2, 3], "sha256": "a" * 64}
        }
        self.damage, self.exit_code = None, 0

    def members(self):
        return set().union(*(c.api.pids for c in self.children))

    def plan(self, argv, options):
        self.events.append("plan")
        api, req, ready = launch_fixture()
        pid = 20 + len(self.children) * 10
        command = list2cmdline(list(argv))
        api.rows["launch"].update(pid=pid, created=pid * 1000, command_line=command)
        api.pids = {pid}
        name = options.get("fixture_role", "financial_worker")
        req = replace(
            req,
            role="acceptance_worker",
            nonce=f"{pid:032x}",
            launch_command=command,
            runtime_command=command,
        )
        ready.update(pid=pid, nonce=req.nonce, role=req.role)
        self.pending = SimpleNamespace(api=api, ready=ready)
        limits = {
            k: LIMITS[k]
            for k in ("processes", "private_bytes", "child_private_bytes", "cpu_ns")
        }
        limits["kill_on_close"] = True
        if self.damage == "limits":
            limits["kill_on_close"] = False
        return {
            "name": name,
            "request": req,
            "parent_owner": self.s.controller,
            "api": api,
            "parent_handle": "parent",
            "job_limits": limits,
            "resource_kinds": ("job", "thread", "image", "pipe"),
        }

    def create_suspended(self, plan, permit, argv, options):
        self.events.append("create")
        assert all(k in self.s.ledger.state["resources"] for k in permit["slots"])
        assert (
            sum(r["kind"] == "job" for r in self.s.ledger.state["resources"].values())
            >= 1
        )
        c = self.pending
        c.launch_handle = None if self.damage == "handle" else "launch"
        c.runtime_handle = "launch"
        self.children.append(c)
        return c

    def verify_suspended_job(self, child, plan):
        self.events.append("suspended-job")
        return {
            "limits": plan["job_limits"],
            "members": sorted(child.api.members()),
            "suspended": True,
            "handle": 300,
        }

    def resume(self, child):
        self.events.append("resume")

    def ready(self, child, **limits):
        self.events.append("ready")
        assert limits == {"timeout": 8, "maximum_bytes": 65536}
        if self.damage == "job":
            child.api.pids.add(99)
        if self.damage == "identity":
            child.api.rows["launch"]["sha256"] = "f" * 64
        if self.damage == "command":
            child.api.rows["launch"]["command_line"] = "foreign"
        if self.damage == "parent":
            child.api.rows["launch"]["parent_pid"] = 999
        return child.ready

    def attach_guards(self, child, guard, name, keys):
        self.events.append("attach")
        child.allocations = {
            key: {
                "kind": guard.resources.state["resources"][key]["kind"],
                "handle": i + 100,
            }
            for i, key in enumerate(keys)
        }
        child.allocations[keys[0]]["handle"] = 300
        child.receipt = {
            "scope": SCOPE_HASH,
            "nonce": guard.ownership.bindings[name].request.nonce,
            "owner": digest(guard.ownership.bindings[name].runtime),
            "reservation_head": guard.resources.head,
            "guarded": True,
        }

    def guard_receipt(self, child):
        if self.damage == "receipt":
            return {}
        return child.receipt

    def allocations(self, child):
        if self.damage == "job-handle":
            child.allocations[next(iter(child.allocations))]["handle"] = 301
        return child.allocations

    def release_target(self, child):
        self.events.append("target")

    def returncode(self, child):
        return child.api.exit_codes.get("launch")

    def communicate(self, child, value, **limits):
        self.events.append("communicate")
        child.api.exit_codes["launch"] = self.exit_code
        child.api.pids.clear()
        return "out", "err"

    def close_owned_handles(self, child, keys):
        self.events.append("close-handles")

    def closed(self, owner, key):
        return self.damage != "cleanup"

    def resources_closed(self, child, keys):
        return self.damage != "cleanup"

    def query_result(self, child, **limits):
        self.communicate(child.child, None)
        return SimpleNamespace(returncode=0, stdout=b"{}", stderr=b"")


def fixture(s=None):
    s = s or resources()
    io = IO()
    paths = FixturePaths(io)
    processes = Processes(s)
    ownership = WorkerOwnership(s.ledger, all_members=processes.members)
    guard = g.FixtureGuard(
        resources=s.ledger,
        paths=paths,
        ownership=ownership,
        owner=s.controller,
        io=io,
        processes=processes,
        clock_ns=lambda: s.now[0],
    )
    return SimpleNamespace(s=s, io=io, paths=paths, processes=processes, guard=guard)


def actual(file, name, namespace):
    """Compile the repository's actual function or class, without native imports."""
    tree = ast.parse(Path(file).read_text(encoding="utf8"), filename=file)
    node = next(
        n
        for n in tree.body
        if isinstance(n, (ast.FunctionDef, ast.ClassDef)) and n.name == name
    )
    if isinstance(node, ast.FunctionDef):
        node.decorator_list = []
    exec(compile(ast.Module(body=[node], type_ignores=[]), file, "exec"), namespace)  # noqa: S102 -- actual pinned source, no native imports
    return namespace[name]


@pytest.mark.parametrize(
    "file,name",
    [
        ("tests/perp_order_native_fixture.py", "build"),
        ("tests/unified_actual_lanes_fixture.py", "build"),
        ("tests/qd_autonomous_binding_fixture.py", "build"),
        ("tests/qd_autonomous_native_fixture.py", "build"),
        ("tests/qd_autonomous_runtime_fixture.py", "compose"),
        ("tests/test_personal_native_pipeline_capacity.py", "run_native_pipeline"),
        ("tests/test_perp_order_crash_race_native.py", "start"),
        ("tests/test_unified_actual_native_lanes.py", "system"),
        ("tests/test_unified_native_writer.py", "bundle"),
        ("tests/test_qd_unified_shutdown.py", "system"),
        ("tests/personal_owned_stop_child.py", "main"),
        ("tests/personal_readonly_restart_child.py", "main"),
        ("tests/perp_order_crash_child.py", "main"),
    ],
)
def test_actual_entry_point_refuses_before_any_native_or_environment_access(file, name):
    ns = {"guarded": g, "STAMP": 1}
    fn = actual(file, name, ns)
    import inspect

    args = [
        None
        for p in inspect.signature(fn).parameters.values()
        if p.default is inspect.Parameter.empty
        and p.kind is not inspect.Parameter.KEYWORD_ONLY
    ]
    kwargs = {
        p.name: None
        for p in inspect.signature(fn).parameters.values()
        if p.default is inspect.Parameter.empty
        and p.kind is inspect.Parameter.KEYWORD_ONLY
    }
    with pytest.raises(ValueError, match="AIP06_GUARDED_SESSION_REQUIRED"):
        value = fn(*args, **kwargs)
        if inspect.isgenerator(value):
            next(value)


def test_actual_durable_pins_use_reserved_write_cas_and_identity_readback():
    x = fixture()
    cls = actual(
        "tests/perp_order_native_fixture.py",
        "DurableTestPins",
        {"guarded": g, "Path": Path, "json": json, "body": body},
    )
    with x.guard.installed():
        g.mkdir(ROOTS["P"])
        pins = cls(path_for("P", "pins.json"), lambda: 1, {"revision": 0})
        assert pins.current() == {"revision": 0}
        pins.advance({"revision": 0}, {"revision": 1})
        assert pins.current() == {"revision": 1}
        before = copy.deepcopy(x.io.effects)
        with pytest.raises(ValueError, match="CAS"):
            pins.advance({"revision": 0}, {"revision": 2})
        assert x.io.effects == before
        x.io.rows[str(pins.path)]["id"] = [9, 9, 9]
        with pytest.raises(ValueError, match="REPLACED"):
            pins.current()
    assert all(r["closed"] for r in x.s.ledger.state["resources"].values())


@pytest.mark.parametrize(
    "path",
    [
        r"D:\AtlasRuntime\x",
        path_for("P", "..", "x") if False else ROOTS["P"] + r"\..\x",
        r"C:\temp\x",
        ROOTS["P"] + ":stream",
    ],
)
def test_actual_write_boundary_rejects_escape_before_io(path):
    x = fixture()
    with x.guard.installed(), pytest.raises(ValueError):
        g.write_bytes(path, b"x")
    assert x.io.effects == []


def test_reservation_exhaustion_prevents_actual_callback():
    x = fixture(seeded(size=LIMITS["bytes"] - LIMITS["stop_bytes"]))
    with x.guard.installed(), pytest.raises(ValueError):
        g.mkdir(ROOTS["P"])
    assert x.io.effects == []


@pytest.mark.parametrize("damage", ["junction", "hardlink", "parent", "replacement"])
def test_actual_write_path_retains_root_and_namespace_checks(damage):
    x = fixture()
    with x.guard.installed():
        g.mkdir(ROOTS["P"])
        row = x.io.rows[ROOTS["P"]]
        if damage == "junction":
            row["reparse"] = True
        elif damage == "hardlink":
            row["links"] = 2
        elif damage == "parent":
            row["parent_id"] = [9, 9, 9]
        else:
            row["id"] = [9, 9, 9]
        before = len(x.io.effects)
        with pytest.raises(ValueError):
            g.write_bytes(path_for("P", "x"), b"x")
        assert len(x.io.effects) == before


@pytest.mark.parametrize(
    "event,args",
    [
        ("open", (path_for("P", "raw"), "w", os.O_WRONLY | os.O_CREAT)),
        ("os.mkdir", (ROOTS["P"], 0o700, -1)),
        ("os.rename", (path_for("P", "x"), path_for("Q", "x"), -1, -1)),
        ("subprocess.Popen", ("python", ["python"], None, None)),
        ("sqlite3.connect", (path_for("P", "raw.sqlite"),)),
    ],
)
def test_bypass_audit_refuses_unattributed_effects(event, args):
    x = fixture()
    with x.guard.installed(), pytest.raises(ValueError):
        g.audit(event, args)
    assert x.io.effects == []


def test_raw_python_open_is_intercepted_before_creating_any_file():
    x = fixture()
    with (
        x.guard.installed(),
        pytest.raises(ValueError, match="UNATTRIBUTED_PYTHON_WRITE"),
        open(path_for("P", "never-created"), "wb"),
    ):
        pytest.fail("raw write bypassed the guard")


def native_module(x):
    ns = {
        "sys": sys,
        "SimpleNamespace": SimpleNamespace,
        "WRITE": 2,
        "DELETE": 4,
        "READ_CONTROL": 8,
        "ATTR": 16,
        "info": None,
        "validate_acl": None,
    }
    count = [100]

    def create(*args):
        count[0] += 1
        return count[0]

    def relative(parent, leaf, sid, directory, create_new, access):
        parent_path = x.guard.handles[parent.token]["path"]
        path = ntpath.join(parent_path, leaf)
        if create_new:
            x.io.add(path, "directory" if directory else "file")
        return create()

    ns.update(
        _raw_create_file=create,
        _raw_close_handle=lambda h: 1,
        _raw_write_file=lambda *a: 1,
        _relative_open=relative,
    )
    file = "scripts/volume_inspector/windows_output.py"
    for name in (
        "_fixture_call",
        "create_file",
        "relative_open",
        "write_file",
        "close_handle",
        "guarded_mutex",
    ):
        actual(file, name, ns)
    return SimpleNamespace(**ns)


def test_actual_native_open_write_close_wrappers_reserve_before_effect_and_release_exact_lifetime():
    x = fixture()
    w = native_module(x)
    with x.guard.installed():
        parent = w.create_file(x.io.chain_rows[-1]["path"], 1, 0, None, 3, 0, None)
        root = w.relative_open(parent, ntpath.basename(ROOTS["P"]), "sid", True, True)
        handle = w.relative_open(root, "data.bin", "sid", False, True, 2)
        before = x.s.ledger.state["charged_bytes"]
        assert w.write_file(handle, b"data", 4, None, None) == 1
        assert x.s.ledger.state["charged_bytes"] > before
        for h in (handle, root, parent):
            w.close_handle(h)
        assert not x.guard.handles
        with pytest.raises(ValueError, match="STALE"):
            w.close_handle(handle)
    assert all(r["closed"] for r in x.s.ledger.state["resources"].values())


@pytest.mark.parametrize(
    "damage",
    ["unretained", "existing-write", "wrong-count", "close-failure", "foreign-mutex"],
)
def test_actual_native_wrappers_fail_closed(damage):
    x = fixture()
    w = native_module(x)
    with x.guard.installed():
        if damage == "unretained":
            with pytest.raises(ValueError):
                w.relative_open(42, "x", "sid", False, True, 2)
            return
        if damage == "foreign-mutex":
            with pytest.raises(ValueError):
                w.guarded_mutex(lambda *a: 100, None, False, "Global\\foreign")
            return
        parent = w.create_file(x.io.chain_rows[-1]["path"], 1, 0, None, 3, 0, None)
        root = w.relative_open(parent, ntpath.basename(ROOTS["P"]), "sid", True, True)
        file = w.relative_open(root, "x", "sid", False, True, 2)
        if damage == "existing-write":
            with pytest.raises(ValueError):
                w.relative_open(root, "x", "sid", False, False, 2)
        elif damage == "wrong-count":
            with pytest.raises(ValueError):
                w.write_file(file, b"x", 2, None, None)
        else:
            with pytest.raises(ValueError):
                x.guard.native("close", lambda *a: 0, (file,), module=w)
            assert file.token in x.guard.handles
        for h in (file, root, parent):
            w.close_handle(h)


def test_actual_crash_launch_uses_guard_and_child_binding_before_target_release():
    x = fixture()
    fn = actual(
        "tests/test_perp_order_crash_race_native.py",
        "start",
        {
            "guarded": g,
            "os": os,
            "Path": Path,
            "sys": sys,
            "CHILD": Path("D:/Work/Project Atlas/tests/perp_order_crash_child.py"),
            "subprocess": SimpleNamespace(PIPE=-1, CREATE_NO_WINDOW=0),
        },
    )
    with x.guard.installed():
        child = fn(path_for("P", "config.json"), "after_pin")
        assert x.processes.events == [
            "plan",
            "create",
            "suspended-job",
            "resume",
            "ready",
            "attach",
            "target",
        ]
        x.processes.exit_code = 71
        child.communicate(timeout=12)
        assert child.closed and x.guard.ownership.finished == {"financial_worker"}
        child.close()  # Verified idempotence, no second CloseHandle call.
        assert x.processes.events.count("close-handles") == 1


@pytest.mark.parametrize(
    "damage",
    [
        "limits",
        "handle",
        "job",
        "receipt",
        "cleanup",
        "identity",
        "command",
        "parent",
        "job-handle",
    ],
)
def test_actual_launch_rejects_missing_binding_and_cleanup_evidence(damage):
    x = fixture()
    x.processes.damage = damage
    with x.guard.installed(), pytest.raises(ValueError):
        child = g.popen([x.processes.executable, "-B", "worker.py"])
        child.communicate()
    if damage == "limits":
        assert "create" not in x.processes.events
    if damage in (
        "handle",
        "job",
        "receipt",
        "identity",
        "command",
        "parent",
        "job-handle",
    ):
        assert "target" not in x.processes.events
    if damage == "cleanup":
        assert any(not r["closed"] for r in x.s.ledger.state["resources"].values())


def test_query_helpers_are_guarded_and_repeated_queries_cannot_reset_accounting():
    x = fixture()
    with x.guard.installed():
        for _ in range(2):
            result = g.query(
                [x.processes.executable, "-B", "query.py"], fixture_role="query"
            )
            assert result.returncode == 0
        assert len(x.guard.launch_nonces) == 2
        assert (
            sum(r["kind"] == "process" for r in x.s.ledger.state["resources"].values())
            == 2
        )
        assert all(r["closed"] for r in x.s.ledger.state["resources"].values())
        x.guard.query_active = True
        with pytest.raises(ValueError, match="RECURSIVE"):
            g.query(["query"])


@pytest.mark.parametrize(
    "sql",
    [
        "ATTACH DATABASE ':memory:' AS other",
        "PRAGMA journal_mode=WAL",
        "PRAGMA temp_store=FILE",
        "PRAGMA max_page_count=999999",
        "PRAGMA query_only=OFF",
    ],
)
def test_real_sqlite_engine_refuses_side_channel_and_capacity_reconfiguration(sql):
    x = fixture()
    with x.guard.installed():
        g.mkdir(ROOTS["P"])
        with (
            g.sqlite_connect(path_for("P", "writers.sqlite")) as db,
            pytest.raises(sqlite3.DatabaseError),
        ):
            db.execute(sql)
    assert all(r["closed"] for r in x.s.ledger.state["resources"].values())


def test_real_sqlite_engine_guarded_schema_transaction_cursor_and_release():
    x = fixture()
    with x.guard.installed():
        g.mkdir(ROOTS["P"])
        with g.sqlite_connect(path_for("P", "writers.sqlite")) as db:
            db.execute("CREATE TABLE control(stopped INTEGER)")
            db.cursor().execute("INSERT INTO control VALUES(?)", (0,))
            db.commit()
            assert db.execute("SELECT * FROM control").fetchone() == (0,)
            assert db.cursor().connection is db
        assert all(v["connections"] == 0 for v in x.guard.databases.values())
    assert all(r["closed"] for r in x.s.ledger.state["resources"].values())


@pytest.mark.parametrize(
    "damage", ["ack", "drain", "cleanup", "deadline", "restart", "cross-account"]
)
def test_wired_stop_verifier_preserves_missing_evidence_and_recovery_refusals(damage):
    x = stop_fixture()
    f = fixture(x.s)
    f.guard.ownership = x.w.ownership
    f.guard.stop = x.stop
    if damage == "ack":
        x.args["acknowledgement"] = {}
    elif damage == "drain":
        x.args["drain"]["pending"] = 1
    elif damage == "cleanup":
        x.args["socket_cut"]["readers"]["NETSTAT"]["unknown"] = True
    elif damage == "deadline":
        x.s.now[0] += 8 * 10**9
    elif damage == "cross-account":
        x.data["accounts"]["HYPERLIQUID"]["manifest"]["currency"] = "USD"
    else:
        f.guard.resources = SharedResources(
            x.s.journal, clock_ns=lambda: x.s.now[0], expected_head=x.s.ledger.head
        )
        with pytest.raises(ValueError):
            f.guard.resources.reserve_stop_request(x.request)
        return
    with f.guard.installed(), pytest.raises(ValueError):
        f.guard.finish_stop(**x.args)
    assert x.stop.result is None and x.stop.failure


@pytest.mark.parametrize(
    "lanes", [("QUALITY_DIPS",), ("HYPERLIQUID",), ("QUALITY_DIPS", "HYPERLIQUID")]
)
def test_wired_stop_replays_exact_declared_accounts_without_fabricating_counterpart(
    lanes,
):
    x = stop_fixture()
    f = fixture(x.s)
    f.guard.ownership = x.w.ownership
    f.guard.stop = x.stop
    x.stop.accounts = {k: v for k, v in x.expected.items() if k in lanes}
    for key in ("accounts", "acknowledgements"):
        x.data[key] = {k: v for k, v in x.data[key].items() if k in lanes}
    with f.guard.installed():
        result = f.guard.finish_stop(**x.args)
    assert set(result["cuts"]) == set(lanes)
    assert result["source_contract_passed"] and result["native_acceptance"] is False


def test_full_scope_stop_cannot_silently_drop_an_account():
    x = stop_fixture()
    del x.data["accounts"]["HYPERLIQUID"]
    with pytest.raises(ValueError):
        x.stop.finish(**x.args)


class JournalIO:
    def __init__(self):
        self.files = {}
        self.bad_close = False

    def verify_directory(self, path, identity):
        assert path == path_for("E", "journal") and identity == [1, 2, 3]

    def names(self):
        return sorted(ntpath.basename(k) for k in self.files)

    def read_exact(self, path, **kwargs):
        return self.files[path]

    def create_new(self, path, parent):
        if path in self.files:
            raise FileExistsError(path)
        self.files[path] = b""
        return path

    def write_exact(self, handle, raw):
        self.files[handle] = raw

    def flush_close(self, handle):
        return {
            "closed": not self.bad_close,
            "flushed": True,
            "path": handle,
            "sha256": hashlib.sha256(self.files[handle]).hexdigest(),
        }


def test_concrete_journal_algorithm_publishes_cas_flush_closed_ack_and_recovery():
    io = JournalIO()
    journal = g.CreateNewJournal(io, [1, 2, 3])
    now = lambda: 10**9
    ledger = SharedResources(journal, clock_ns=now)
    from test_launch_ownership import row

    owner = ledger.register_owner(row(10, 8), controller=True)
    ledger.reserve(owner, "file", "file", entries=1, size=1)
    assert journal.receipt()["head"] == ledger.head
    recovered = SharedResources(journal, clock_ns=now, expected_head=ledger.head)
    assert recovered.read() == ledger.read()
    with pytest.raises(ValueError):
        recovered.reserve(owner, "new", "file")
    io.bad_close = True
    with pytest.raises(ValueError):
        ledger.reserve(owner, "unknown", "file")
    assert ledger.uncertain
    with pytest.raises(ValueError):
        journal.receipt()


def test_concrete_journal_missing_sequence_and_foreign_append_refuse():
    io = JournalIO()
    journal = g.CreateNewJournal(io, [1, 2, 3])
    io.files[path_for("E", "journal", "record-00000002.json")] = b"{}"
    with pytest.raises(ValueError):
        journal.read()
    io.files.clear()
    with pytest.raises(ValueError):
        journal.append(
            "f" * 64, {"parent": SCOPE_HASH, "sequence": 1, "scope": SCOPE_HASH}
        )


def test_actual_stop_timing_entrypoint_has_no_raw_launch_or_random_sample_root():
    source = Path("tests/test_personal_owned_stop_timing.py").read_text(encoding="utf8")
    assert "guard.run_owned_stop_sample(sample" in source
    tree = ast.parse(source)
    names = [
        n
        for n in tree.body
        if isinstance(n, ast.FunctionDef) and n.name.startswith("test_")
    ]
    assert len(names) == 1
    assert not any(
        isinstance(n, ast.Call)
        and isinstance(n.func, ast.Attribute)
        and n.func.attr in {"Popen", "uuid4"}
        for n in ast.walk(names[0])
    )


def test_actual_owned_stop_entrypoint_drives_real_guards_replay_reopen_and_release(
    tmp_path, monkeypatch
):
    from test_composed_accounting_risk_recovery import verified
    from test_quality_dips_autonomous_paper import candidate, entry, monitor, setup

    q = setup(tmp_path)
    assert entry(q)["filled"]
    assert monitor(q, candidate(q), "partial", "110", {"fundamentals_score": 60})[
        "filled"
    ]
    assert monitor(
        q, candidate(q), "final", "120", {"classification": "THESIS_BROKEN"}
    )["filled"]
    cut = verified(q.ledger)
    data = financial_fixture()
    row = data["accounts"]["QUALITY_DIPS"]
    pure, _, _ = replay_verified_events(q.m, cut["rows"])
    row.update(manifest=q.m, events=cut["rows"], snapshot=pure, source_head=cut["head"])
    data["accounts"] = {"QUALITY_DIPS": row}
    ack = {
        "account_id": row["account_id"],
        "epoch": q.m["epoch"],
        "currency": "USD",
        "revision": 3,
        "head": cut["head"],
        "state_digest": digest(pure),
        "native_source": row["native_source"],
    }
    data["acknowledgements"] = {
        "QUALITY_DIPS": {
            stage: copy.deepcopy(ack)
            for stage in ("source", "projection", "report", "global")
        }
    }
    expected = {
        "QUALITY_DIPS": {
            k: copy.deepcopy(row[k])
            for k in ("account_id", "manifest", "native_source")
        }
    }
    reader = SimpleNamespace(
        read_committed=lambda request: copy.deepcopy(data), observer_identity=None
    )
    x = fixture()
    p = x.processes
    p.owned_stop_spec = lambda sample, root, nonce, repo: {
        "argv": [p.executable, "-B", repo + "\\tests\\personal_owned_stop_child.py"],
        "options": {},
        "expected_accounts": expected,
        "reader": reader,
        "operation_id": f"sample-{sample}",
    }
    p.financial_ready = lambda child, **limits: None

    def send(child, request):
        assert request == x.guard.stop.request
        assert body(request["worker"]) == body(
            x.guard.ownership.bindings["financial_worker"].runtime
        )

    p.send_stop = send

    def collect(child, guard, request, deadline_ns):
        assert deadline_ns == guard.stop.started + 8 * 10**9
        child.communicate()
        cold = guard.spawn(
            [p.executable, "-B", "readonly.py"], fixture_role="readonly_reader"
        )
        reader.observer_identity = cold.identity()
        cold.communicate()
        guard.ledger("usage", memory={x.s.controller: 0}, cpu_ns=0)
        x.s.now[0] += 10**9
        return {
            "acknowledgement": request,
            "drain": {
                "scope": SCOPE_HASH,
                "operation_id": request["operation_id"],
                "pending": 0,
                "orders": 0,
                "unknown": False,
            },
            "socket_cut": {
                "scope": SCOPE_HASH,
                "at_ns": x.s.now[0],
                "readers": {
                    name: {
                        "complete": True,
                        "owned_endpoints": [],
                        "unknown": False,
                        "started_ns": x.s.now[0],
                        "finished_ns": x.s.now[0],
                    }
                    for name in ("CIM", "IP_HELPER", "NETSTAT")
                },
            },
            "process_cut": {
                "scope": SCOPE_HASH,
                "started_ns": x.s.now[0],
                "at_ns": x.s.now[0],
                "survivors": [],
                "unknown": False,
            },
            "release_observer": p,
        }

    p.collect_stop = collect
    fn = actual(
        "tests/test_personal_owned_stop_timing.py",
        "test_three_owned_native_shutdowns_include_exit_and_post_exit_readback",
        {
            "guarded": g,
            "os": os,
            "Path": Path,
            "__file__": str(
                Path("tests/test_personal_owned_stop_timing.py").absolute()
            ),
        },
    )
    monkeypatch.setenv("ATLAS_OWNED_STOP_TIMING_PARENT", ROOTS["T"])
    monkeypatch.setenv("ATLAS_OWNED_STOP_READER_MODE", "COLD")
    with x.guard.installed():
        g.mkdir(ROOTS["T"])
        for sample in (1, 2, 3):
            fn(sample)
            assert x.guard.stop.result["cash_by_lane"] == {"QUALITY_DIPS": "1015.9136"}
            assert x.guard.stop.result["native_acceptance"] is False
        assert len(x.guard.case_results) == 2 and x.paths.slots == {1, 2, 3}
        assert all(r["closed"] for r in x.s.ledger.state["resources"].values())
        with pytest.raises(ValueError):
            x.guard.run_owned_stop_sample(4, Path("."))
    assert not p.members() and not x.guard.handles


def test_actual_query_observer_selects_guarded_query_and_sqlite_fixture_routes_guarded_connection():
    source = Path("scripts/observation_runtime/launch_ownership_windows.py").read_text(
        encoding="utf8"
    )
    assert "subprocess.run if guarded.current() is None else guarded.query" in source
    for file in (
        "tests/test_unified_native_writer.py",
        "tests/test_qd_unified_shutdown.py",
        "backend/app/services/paper_epoch_fixture.py",
        "backend/app/services/paper_writer_fixture.py",
    ):
        source = Path(file).read_text(encoding="utf8")
        assert "sqlite_connect" in source


def test_actual_native_token_allocation_is_reserved_and_closed_without_foreign_handle_adoption():
    x = fixture()
    w = native_module(x)
    with x.guard.installed():
        token = x.guard.native("token", lambda: 50, (), module=w)
        assert x.s.ledger.state["resources"][token.token]["kind"] == "handle"
        w.close_handle(token)
        with pytest.raises(ValueError):
            w.close_handle(50)


@pytest.mark.parametrize(
    "damage", ["nonce", "operation", "worker", "current-process", "closed", "missing"]
)
def test_worker_stop_command_is_bound_to_durable_parent_request_not_port_boolean(
    damage,
):
    x = stop_fixture()
    f = fixture(x.s)
    row = x.w.ownership.bindings["financial_worker"].runtime
    f.guard.owner = digest(row)
    identity = {
        "pid": row["pid"],
        "creation_filetime": row["created"],
        "image": row["image"],
    }
    command = copy.deepcopy(x.request)
    assert f.guard.verify_received_stop(command, command["nonce"], identity) == command
    if damage == "nonce":
        command["nonce"] = "f" * 32
    elif damage == "operation":
        command["operation_id"] = "different"
    elif damage == "worker":
        command["worker"]["created"] += 1
    elif damage == "current-process":
        identity["creation_filetime"] += 1
    elif damage == "missing":
        del command["scope"]
    else:
        x.s.ledger.resolve_stop(x.request, "CLOSED")
    with pytest.raises(ValueError):
        f.guard.verify_received_stop(command, x.request["nonce"], identity)


@pytest.mark.parametrize("bad", ["late", "empty", "oversized", "nul"])
def test_child_input_uses_real_bounded_read_guard(bad):
    x = fixture()

    def read(**limits):
        assert limits == {"timeout": 2, "maximum_bytes": 64}
        if bad == "late":
            x.s.now[0] += 3 * 10**9
        return {"late": b"{}", "empty": b"", "oversized": b"x" * 65, "nul": b"\x00"}[
            bad
        ]

    x.processes.read_input = read
    with x.guard.installed(), pytest.raises(ValueError):
        x.guard.read_input(maximum_bytes=64, timeout=2)


def test_closed_sqlite_capacity_is_not_an_open_handle_or_a_budget_refund():
    x = fixture()
    with x.guard.installed():
        g.mkdir(ROOTS["P"])
        path = path_for("P", "db.sqlite")
        with g.sqlite_connect(path) as db:
            db.execute("CREATE TABLE x(v)")
        after = x.s.ledger.state["charged_bytes"]
        with g.sqlite_connect(
            "file:///" + path.replace("\\", "/") + "?mode=ro", uri=True
        ) as db:
            db.execute("BEGIN")
            with pytest.raises(ValueError):
                db.execute("CREATE TABLE y(v)")
        assert x.s.ledger.state["charged_bytes"] > after
        assert all(r["closed"] for r in x.s.ledger.state["resources"].values())


@pytest.mark.parametrize("damage", [None, "identity", "release"])
def test_child_watchdog_is_reserved_before_creation_and_closed_with_proof(damage):
    x = fixture()
    calls = []

    def start(**plan):
        assert all(k in x.s.ledger.state["resources"] for k in plan["keys"])
        calls.append("start")
        return {
            "owner": x.s.controller if damage != "identity" else "foreign",
            "thread": 123,
            "handle": 456,
            "created": 789,
        }

    x.processes.start_watchdog = start
    x.processes.cancel_watchdog = lambda timer: calls.append("cancel")
    if damage == "release":
        x.processes.damage = "cleanup"
    with x.guard.installed():
        if damage:
            with pytest.raises(ValueError), g.watchdog(seconds=30, exit_code=70):
                pass
        else:
            with g.watchdog(seconds=30, exit_code=70):
                calls.append("body")
            assert calls == ["start", "body", "cancel"]
            assert all(r["closed"] for r in x.s.ledger.state["resources"].values())


def test_failed_sqlite_configuration_closes_owned_driver_without_accepting_it():
    x = fixture()

    class BadDatabase:
        closed = False

        def execute(self, sql):
            raise sqlite3.DatabaseError("offline denied configuration")

        def close(self):
            self.closed = True

    db = BadDatabase()
    x.io.sqlite_open = lambda *a, **kw: db
    with x.guard.installed():
        g.mkdir(ROOTS["P"])
        with pytest.raises(sqlite3.DatabaseError):
            g.sqlite_connect(path_for("P", "bad.sqlite"))
    assert db.closed and all(
        r["closed"] for r in x.s.ledger.state["resources"].values()
    )


def test_replace_cannot_cross_accounts_or_adopt_existing_private_artifacts():
    x = fixture()
    with x.guard.installed():
        for root in ("P", "Q"):
            g.mkdir(ROOTS[root])
        g.write_bytes(path_for("P", "a"), b"a")
        g.write_bytes(path_for("Q", "b"), b"b")
        with pytest.raises(ValueError, match="CROSS_ACCOUNT"):
            g.replace(path_for("P", "a"), path_for("Q", "b"))
        x.io.add(path_for("P", "foreign"), "file")
        with pytest.raises(ValueError, match="OWNED_REPLACEMENT"):
            g.replace(path_for("P", "a"), path_for("P", "foreign"))


def test_actual_image_lease_close_and_open_use_reserved_pinned_lifetime():
    x = fixture()
    called = []

    def create(*args):
        assert any(r["kind"] == "image" for r in x.s.ledger.state["resources"].values())
        called.append("open")
        return 1234

    api = SimpleNamespace(
        k=SimpleNamespace(
            CreateFileW=create, CloseHandle=lambda h: called.append("close") or 1
        ),
        check=lambda x: None,
    )
    cls = actual(
        "scripts/observation_runtime/launch_ownership_windows.py",
        "ImageLease",
        {"guarded": g},
    )
    with x.guard.installed():
        image = g.image_open(api, x.processes.executable)
        lease = object.__new__(cls)
        lease.api = api
        lease.handle = image
        lease.close()
        assert lease.handle is None and called == ["open", "close"]
        with pytest.raises(ValueError, match="IMAGE_PIN"):
            g.image_open(api, r"C:\private\foreign.exe")
        assert called == ["open", "close"]
    assert all(r["closed"] for r in x.s.ledger.state["resources"].values())


def test_actual_legacy_probe_is_explicitly_blocked_before_its_unbound_native_controller():
    fn = actual(
        "tests/run_launch_ownership_native.py",
        "main",
        {"guarded": g, "OwnershipRefused": ValueError},
    )
    with pytest.raises(ValueError, match="GUARDED_SESSION_REQUIRED"):
        fn()
    x = fixture()
    with (
        x.guard.installed(),
        pytest.raises(ValueError, match="CONTROLLER_PORT_NOT_BOUND"),
    ):
        fn()
    assert not x.io.effects and not x.processes.events


@pytest.mark.parametrize(
    "key",
    [
        "ATLAS_PERSONAL_NATIVE_TEST_APPROVAL",
        "ATLAS_SYNTHETIC_INSTALL_SCOPE",
        "ATLAS_SYNTHETIC_INSTALL_SCOPE_SHA256",
    ],
)
def test_active_guard_cannot_reuse_legacy_grants_or_installed_source_scope(
    monkeypatch, key
):
    x = fixture()
    monkeypatch.setenv(key, "unapproved-prior-value")
    with x.guard.installed(), pytest.raises(ValueError, match="NO_LEGACY_GRANT"):
        g.mkdir(ROOTS["P"])
    assert x.io.effects == []
