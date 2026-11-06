"""Offline mocks only: no native API, process, fixture roots or financial worker."""

import copy
import json
import ntpath
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest
from app.services.paper_financial_replay import digest, replay_verified_events
from continuation_fixture import manifests, records
from test_launch_ownership import row
from test_launch_ownership import setup as launch_fixture

from scripts.observation_runtime.aip06_harness import (
    BASE,
    LIMITS,
    ROOTS,
    SCOPE_HASH,
    FixturePaths,
    ReservedFixtureEffects,
    SharedResources,
    StopVerification,
    WorkerOwnership,
    bounded_line,
    path_for,
)


class Journal:
    """Canonical JSON roundtrip catches tuple/boolean/mutable fixture mistakes."""

    def __init__(self):
        self.rows, self.fail, self.receipt_valid = [], None, True

    def read(self):
        return json.loads(json.dumps(self.rows))

    def append(self, head, event):
        assert head == (digest(self.rows[-1]) if self.rows else SCOPE_HASH)
        if self.fail == "before":
            raise OSError("synthetic failed reservation append")
        self.rows.append(json.loads(json.dumps(event)))
        if self.fail == "after":
            raise OSError("synthetic lost ACK")

    def receipt(self):
        r = self.rows[-1]
        return {
            "head": digest(r),
            "owner": r["state"]["controller"],
            "closed": self.receipt_valid,
        }


def resources():
    now = [10**9]
    journal = Journal()
    ledger = SharedResources(journal, clock_ns=lambda: now[0])
    controller = ledger.register_owner(row(10, 8), controller=True)
    return SimpleNamespace(**locals())


def seeded(*, entries=0, size=0):
    s = resources()
    # Explicit synthetic already-charged prefix for numerical boundary tests.
    s.journal.rows[-1]["state"].update(entries=entries, charged_bytes=size)
    # Model an uncrashed controller after earlier charges, not permission to
    # resume a reconstructed native session. Only this numerical fake is seeded.
    s.ledger._rows = s.journal.read()
    s.ledger._state = copy.deepcopy(s.journal.rows[-1]["state"])
    return s


def test_parent_child_and_journal_charges_survive_restart_without_refunds():
    s = resources()
    child = s.ledger.register_owner(row(20, 10))
    s.ledger.reserve(child, "child", "process")
    before = s.ledger.read()
    s.ledger.reserve(child, "file", "file", entries=1, size=4097)
    s.ledger.charge_write(child, "file", size=10)
    after = s.ledger.read()
    assert (
        after["state"]["entries"] > before["state"]["entries"] + 1
    )  # Journals count too.
    assert after["state"]["charged_bytes"] > before["state"]["charged_bytes"] + 4097
    reopened = SharedResources(
        s.journal, clock_ns=lambda: s.now[0], expected_head=after["head"]
    )
    assert reopened.read() == after
    observer = SimpleNamespace(closed=lambda owner, key: owner == child)
    for key in ("file", "child"):
        reopened.close(child, key, observer=observer)
    closed = reopened.read()
    assert closed["state"]["entries"] >= after["state"]["entries"]
    assert closed["state"]["charged_bytes"] >= after["state"]["charged_bytes"]
    head = reopened.close(child, "child", observer=observer)
    assert head == closed["head"]
    with pytest.raises(ValueError):
        reopened.close(
            child, "child", observer=SimpleNamespace(closed=lambda *a: False)
        )


@pytest.mark.parametrize(
    "damage", ["owner", "duplicate", "kind", "bool-entry", "negative", "too-large"]
)
def test_invalid_resource_reservation_has_no_effect(damage):
    s = resources()
    s.ledger.reserve(s.controller, "prior", "file", entries=1)
    before = s.ledger.read()
    owner, key, kind, entries, size = s.controller, "new", "file", 1, 1
    if damage == "owner":
        owner = "foreign"
    elif damage == "duplicate":
        key = "prior"
    elif damage == "kind":
        kind = "operational-account"
    elif damage == "bool-entry":
        entries = True
    elif damage == "negative":
        size = -1
    else:
        size = 1024**2 + 1
    with pytest.raises(ValueError):
        s.ledger.reserve(owner, key, kind, entries=entries, size=size)
    assert s.ledger.read() == before


def test_work_cannot_spend_cleanup_entries_but_stop_can_use_reserved_capacity():
    s = seeded(entries=LIMITS["entries"] - LIMITS["stop_entries"])
    with pytest.raises(ValueError):
        s.ledger.reserve(s.controller, "work", "file", entries=1)
    s.ledger.begin_stop()
    s.ledger.reserve(s.controller, "cleanup", "file", entries=1, cleanup=True)
    assert (
        s.ledger.read()["state"]["entries"] > LIMITS["entries"] - LIMITS["stop_entries"]
    )


def test_work_cannot_spend_cleanup_bytes_and_global_limit_still_refuses_stop():
    s = seeded(size=LIMITS["bytes"] - LIMITS["stop_bytes"])
    with pytest.raises(ValueError):
        s.ledger.reserve(s.controller, "work", "file", entries=1)
    s.ledger.begin_stop()
    s.ledger.reserve(s.controller, "cleanup", "file", entries=1, cleanup=True)
    full = seeded(size=LIMITS["bytes"])
    with pytest.raises(ValueError):
        full.ledger.begin_stop()


def test_serial_stop_requests_keep_global_counters_and_cannot_reset_failed_request():
    s = resources()
    worker = row(20, 10)
    owner = s.ledger.register_owner(worker)
    s.ledger.reserve(owner, "worker", "process")
    first = {
        "scope": SCOPE_HASH,
        "nonce": "a" * 32,
        "worker": worker,
        "operation_id": "first",
    }
    s.ledger.reserve_stop_request(first)
    charged = s.ledger.read()["state"]["charged_bytes"]
    with pytest.raises(ValueError):
        s.ledger.reserve_stop_request(first)
    s.ledger.resolve_stop(first, "CLOSED")
    second = {**first, "operation_id": "second"}
    s.ledger.reserve_stop_request(second)
    assert s.ledger.read()["state"]["charged_bytes"] > charged
    assert s.ledger.read()["state"]["mode"] == "WORK"
    s.ledger.resolve_stop(second, "FAILED")
    with pytest.raises(ValueError):
        s.ledger.reserve_stop_request({**first, "operation_id": "third"})
    with pytest.raises(ValueError):
        s.ledger.resolve_stop(second, "CLOSED")


def test_global_cleanup_cannot_reopen_normal_work():
    s = resources()
    s.ledger.begin_stop()
    with pytest.raises(ValueError):
        s.ledger.reserve(s.controller, "normal", "process")
    s.ledger.reserve(s.controller, "evidence", "file", entries=1, cleanup=True)


@pytest.mark.parametrize("phase", ["before", "after", "receipt"])
def test_failed_or_unacknowledged_reservation_latches_no_further_effect(phase):
    s = resources()
    s.journal.fail = phase if phase != "receipt" else None
    s.journal.receipt_valid = phase != "receipt"
    with pytest.raises((ValueError, OSError)):
        s.ledger.reserve(s.controller, "file", "file", entries=1)
    assert s.ledger.uncertain
    with pytest.raises(ValueError):
        s.ledger.reserve(s.controller, "retry", "file", entries=1)


def test_allocation_failure_keeps_charge_and_unreleased_resource():
    s = resources()
    s.ledger.reserve(s.controller, "attempted-file", "file", entries=1, size=4096)
    before = s.ledger.read()
    with pytest.raises(ValueError):
        s.ledger.close(
            s.controller,
            "attempted-file",
            observer=SimpleNamespace(closed=lambda *a: False),
        )
    assert s.ledger.read() == before


@pytest.mark.parametrize(
    "damage", ["head", "sequence", "scope", "owner", "negative", "bool", "missing"]
)
def test_corrupt_or_conflicting_recovery_fails_closed(damage):
    s = resources()
    expected = s.ledger.head
    value = s.journal.rows[-1]
    if damage == "head":
        value["parent"] = "wrong"
    elif damage == "sequence":
        value["sequence"] = 2
    elif damage == "scope":
        value["scope"] = "foreign"
    elif damage == "owner":
        value["state"]["owners"] = {}
    elif damage == "negative":
        value["state"]["charged_bytes"] = -1
    elif damage == "bool":
        value["state"]["entries"] = True
    else:
        s.journal.rows.clear()
    with pytest.raises(ValueError):
        SharedResources(s.journal, clock_ns=lambda: s.now[0], expected_head=expected)


def test_no_unpinned_restart_or_pid_reuse():
    s = resources()
    with pytest.raises(ValueError):
        SharedResources(s.journal, clock_ns=lambda: s.now[0])
    with pytest.raises(ValueError):
        s.ledger.register_owner(row(10, 8, created=999999))
    assert s.ledger.register_owner(row(10, 8)) == s.controller


def test_recovery_never_resumes_work_even_with_a_valid_previous_head():
    s = resources()
    restored = SharedResources(
        s.journal, clock_ns=lambda: s.now[0], expected_head=s.ledger.head
    )
    before = restored.read()
    with pytest.raises(ValueError):
        restored.reserve(s.controller, "resumed", "pipe")
    with pytest.raises(ValueError):
        restored.register_owner(row(40, 10))
    assert restored.read() == before
    restored.begin_stop()
    restored.reserve(s.controller, "cleanup-evidence", "file", entries=1, cleanup=True)


def test_recovered_closed_stop_record_does_not_grant_a_second_session():
    x = stop_fixture()
    x.stop.finish(**x.args)
    restored = SharedResources(
        x.s.journal, clock_ns=lambda: x.s.now[0], expected_head=x.s.ledger.head
    )
    with pytest.raises(ValueError):
        restored.reserve_stop_request({**x.request, "operation_id": "another"})


def test_shared_concurrent_reservation_cannot_double_allocate():
    s = resources()

    def reserve(_):
        try:
            s.ledger.reserve(s.controller, "one", "file", entries=1)
            return "RESERVED"
        except ValueError:
            return "REFUSED"

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(reserve, range(8)))
    assert results.count("RESERVED") == 1
    assert len(s.ledger.read()["state"]["resources"]) == 1


def test_parent_child_process_memory_cpu_and_wall_limits():
    s = resources()
    owners = [s.controller]
    for i in range(7):
        owner = s.ledger.register_owner(row(20 + i, 10))
        owners.append(owner)
        s.ledger.reserve(owner, f"process-{i}", "process")
    last = s.ledger.register_owner(row(40, 10))
    with pytest.raises(ValueError):
        s.ledger.reserve(last, "ninth", "process")
    memory = dict.fromkeys(owners, 0)
    s.ledger.usage(memory=memory, cpu_ns=120 * 10**9)
    with pytest.raises(ValueError):
        s.ledger.usage(memory=memory, cpu_ns=120 * 10**9 + 1)
    with pytest.raises(ValueError):
        s.ledger.usage(memory={s.controller: 0}, cpu_ns=120 * 10**9)
    bad = dict(memory)
    bad[owners[1]] = 256 * 1024**2 + 1
    with pytest.raises(ValueError):
        s.ledger.usage(memory=bad, cpu_ns=120 * 10**9)
    bad = dict(memory)
    bad.update({key: 100 * 1024**2 for key in owners})
    with pytest.raises(ValueError):
        s.ledger.usage(memory=bad, cpu_ns=120 * 10**9)
    s.now[0] += 540 * 10**9 + 1
    with pytest.raises(ValueError):
        s.ledger.reserve(s.controller, "late", "pipe")
    s.ledger.begin_stop()
    s.now[0] += 60 * 10**9
    with pytest.raises(ValueError):
        s.ledger.read()


class Files:
    def __init__(self):
        self.rows, self.chain_rows = {}, []
        path = "D:\\"
        for i, component in enumerate([None, *BASE[3:].split("\\")]):
            if component is not None:
                path = ntpath.join(path, component)
            row_ = {
                "path": path,
                "id": [1, i + 1, 0],
                "parent_id": None if i == 0 else [1, i, 0],
                "kind": "directory",
                "reparse": False,
                "links": 1,
            }
            self.chain_rows.append(row_)

    def chain(self, path):
        assert path == BASE
        return copy.deepcopy(self.chain_rows)

    def inspect(self, path):
        return copy.deepcopy(self.rows.get(path))

    def create(self, intent):
        self.rows[intent["path"]] = {
            "path": intent["path"],
            "id": [1, len(self.rows) + 100, 0],
            "parent_id": intent["parent"][-1]["id"],
            "kind": "directory",
            "reparse": False,
            "links": 1,
        }


@pytest.mark.parametrize(
    "bad",
    [
        "..",
        "D:\\AtlasRuntime",
        "x/y",
        "x\\y",
        "x:ads",
        "CON",
        "lpt1.txt",
        "trailing.",
        "trailing ",
        "",
        "\x00",
    ],
)
def test_fixture_paths_reject_escape_and_windows_aliases(bad):
    with pytest.raises(ValueError):
        path_for("E", bad)


def test_exact_reviewed_roots_fixed_slots_and_no_real_directories_created():
    fs = Files()
    paths = FixturePaths(fs)
    for sample in (1, 2, 3):
        intent = paths.stop_slot(sample)
        assert intent["path"] == ROOTS[f"S{sample}"]
        fs.create(intent)
        paths.bind_created(intent)
        account = path_for(f"S{sample}", "account")
        fs.rows[account] = {
            "path": account,
            "id": [1, 500 + sample, 0],
            "parent_id": fs.rows[intent["path"]]["id"],
            "kind": "directory",
            "reparse": False,
            "links": 1,
        }
        assert paths.verify(f"S{sample}", "account", "evidence.json").startswith(
            ROOTS[f"S{sample}"]
        )
        with pytest.raises(ValueError):
            paths.stop_slot(sample)
    with pytest.raises(ValueError):
        paths.stop_slot(4)
    with pytest.raises(TypeError):
        ROOTS["E"] = r"D:\AtlasRuntime"
    review = Path(
        "docs/AIP_06_NATIVE_ACCEPTANCE_READINESS_REVIEW_2026-11-04.md"
    ).read_text(encoding="utf8")
    assert all(value in review for value in ROOTS.values())


@pytest.mark.parametrize(
    "damage",
    [
        "parent",
        "junction",
        "symlink",
        "hardlink",
        "replacement",
        "existing",
        "ancestry",
    ],
)
def test_native_path_identity_conflicts_refuse(damage):
    fs = Files()
    paths = FixturePaths(fs)
    intent = paths.prepare("E")
    fs.create(intent)
    if damage == "existing":
        with pytest.raises(ValueError):
            paths.prepare("E")
        return
    if damage == "parent":
        fs.rows[ROOTS["E"]]["parent_id"] = [9, 9, 9]
    elif damage in ("junction", "symlink"):
        fs.rows[ROOTS["E"]]["reparse"] = True
    elif damage == "hardlink":
        fs.rows[ROOTS["E"]]["links"] = 2
    elif damage == "ancestry":
        fs.chain_rows[-1]["parent_id"] = [9, 9, 9]
    if damage == "replacement":
        paths.bind_created(intent)
        fs.rows[ROOTS["E"]]["id"] = [9, 9, 9]
        with pytest.raises(ValueError):
            paths.verify("E", "new.json")
    else:
        with pytest.raises(ValueError):
            paths.bind_created(intent)


@pytest.mark.parametrize(
    "damage", ["junction", "hardlink", "owner", "unbound", "missing"]
)
def test_leaf_path_never_adopts_existing_or_linked_artifact(damage):
    fs = Files()
    paths = FixturePaths(fs)
    intent = paths.prepare("E")
    fs.create(intent)
    paths.bind_created(intent)
    path = path_for("E", "receipt.json")
    row_ = {
        "path": path,
        "id": [1, 999, 0],
        "parent_id": fs.rows[ROOTS["E"]]["id"],
        "kind": "file",
        "reparse": False,
        "links": 1,
    }
    fs.rows[path] = row_
    ident = copy.deepcopy(row_["id"])
    if damage == "junction":
        row_["reparse"] = True
    elif damage == "hardlink":
        row_["links"] = 2
    elif damage == "owner":
        row_["parent_id"] = [9, 9, 9]
    elif damage == "unbound":
        ident = None
    else:
        fs.rows.clear()
    with pytest.raises(ValueError):
        paths.verify("E", "receipt.json", existing_id=ident)


def test_mutations_are_reserved_and_attributed_before_injected_effect():
    s = resources()
    fs = Files()
    paths = FixturePaths(fs)
    effects = ReservedFixtureEffects(s.ledger, paths)

    def root_creator(intent):
        assert s.ledger.read()["state"]["resources"]["root:E"]["owner"] == s.controller
        fs.create(intent)

    effects.create_root("E", s.controller, creator=root_creator)

    def writer(path, data):
        assert data == b"immutable evidence"
        assert s.ledger.read()["state"]["resources"]["receipt"]["closed"] is False
        fs.rows[path] = {
            "path": path,
            "id": [1, 999, 0],
            "parent_id": fs.rows[ROOTS["E"]]["id"],
            "kind": "file",
            "links": 1,
            "reparse": False,
        }
        return [1, 999, 0]

    result = effects.create_file(
        "E",
        ("receipt.json",),
        s.controller,
        "receipt",
        data=b"immutable evidence",
        writer=writer,
    )
    assert result["native_id"] == [1, 999, 0]
    assert not s.ledger.read()["state"]["resources"]["receipt"]["closed"]
    with pytest.raises(ValueError):
        effects.create_file(
            "E", ("receipt.json",), s.controller, "duplicate", data=b"x", writer=writer
        )


def test_reservation_failure_prevents_creator_and_partial_failure_is_not_retried():
    s = seeded(entries=LIMITS["entries"] - LIMITS["stop_entries"])
    effects = ReservedFixtureEffects(s.ledger, FixturePaths(Files()))
    calls = []
    with pytest.raises(ValueError):
        effects.create_root("E", s.controller, creator=lambda *a: calls.append(a))
    assert not calls
    s = resources()
    effects = ReservedFixtureEffects(s.ledger, FixturePaths(Files()))

    def failed(intent):
        calls.append(intent)
        raise OSError("synthetic partial allocation")

    with pytest.raises(OSError):
        effects.create_root("E", s.controller, creator=failed)
    with pytest.raises(ValueError):
        effects.create_root("E", s.controller, creator=failed)
    assert (
        len(calls) == 1
        and not s.ledger.read()["state"]["resources"]["root:E"]["closed"]
    )


@pytest.mark.parametrize(
    "damage", [None, "late", "rollback", "empty", "oversize", "unterminated", "nul"]
)
def test_pipe_reads_have_explicit_deadline_size_and_refuse_bad_results(damage):
    now = [100]

    def read_line(*, timeout, limit):
        assert timeout == 1 and limit == 8
        if damage == "late":
            now[0] += 10**9 + 1
        if damage == "rollback":
            now[0] -= 1
        return {
            "empty": b"",
            "oversize": b"12345678\n",
            "unterminated": b"x",
            "nul": b"\x00\n",
        }.get(damage, b"ready\n")

    port = SimpleNamespace(read_line=read_line)
    if damage is None:
        assert (
            bounded_line(
                port, deadline_ns=100 + 10**9, clock_ns=lambda: now[0], maximum_bytes=8
            )
            == b"ready\n"
        )
    else:
        with pytest.raises(ValueError):
            bounded_line(
                port, deadline_ns=100 + 10**9, clock_ns=lambda: now[0], maximum_bytes=8
            )


def owned(s, *, redirect=False):
    api, req, ready = launch_fixture(redirect)
    req = replace(req, role="acceptance_worker")
    ready["role"] = req.role
    ownership = WorkerOwnership(s.ledger, all_members=lambda: api.pids.copy())
    ownership.prepare("financial_worker", req)
    ownership.bind(
        "financial_worker",
        api=api,
        request=req,
        parent_handle="parent",
        launch_handle="launch",
        runtime_handle="runtime" if redirect else "launch",
        ready=ready,
    )
    return SimpleNamespace(**locals())


@pytest.mark.parametrize("redirect", [False, True])
def test_actual_role_reuses_exact_retained_launch_binding(redirect):
    s = resources()
    w = owned(s, redirect=redirect)
    assert {p["pid"] for p in w.ownership.verify()} == w.api.pids
    assert w.ownership.bindings["financial_worker"].request.role == "acceptance_worker"


def test_ownership_without_prelaunch_reservation_never_adopts_process():
    s = resources()
    api, req, ready = launch_fixture()
    req = replace(req, role="acceptance_worker")
    ready["role"] = req.role
    roster = WorkerOwnership(s.ledger, all_members=lambda: api.pids.copy())
    with pytest.raises(ValueError, match="PRELAUNCH"):
        roster.bind(
            "financial_worker",
            api=api,
            request=req,
            parent_handle="parent",
            launch_handle="launch",
            runtime_handle="launch",
            ready=ready,
        )
    assert roster.refused and not roster.bindings


def test_process_capacity_is_reserved_before_launcher_can_run():
    s = resources()
    api, req, _ = launch_fixture()
    req = replace(
        req,
        role="acceptance_worker",
        topology="one_redirector",
        runtime_image=("d:/synthetic/base.exe", (1, 2, 3), "a" * 64),
    )
    for i in range(6):
        s.ledger.reserve(s.controller, f"prior-{i}", "launch")
    roster = WorkerOwnership(s.ledger, all_members=lambda: api.pids.copy())
    with pytest.raises(ValueError):
        roster.prepare("financial_worker", req)
    assert roster.refused  # First reserved slot retained; no native launcher called.


def test_mutating_a_read_view_cannot_reset_budget():
    s = resources()
    before = s.ledger.read()
    view = s.ledger.state
    view["charged_bytes"] = 0
    view["owners"].clear()
    assert s.ledger.read() == before


def test_unexpected_global_job_member_refusal_cannot_be_cleared_by_later_cleanup():
    s = resources()
    w = owned(s)
    w.ownership.all_members = lambda: {20, 99}
    with pytest.raises(ValueError):
        w.ownership.verify()
    w.ownership.all_members = lambda: {20}
    with pytest.raises(ValueError):
        w.ownership.verify()


def test_clock_rollback_and_foreign_durable_append_prevent_new_effect():
    s = resources()
    prior = copy.deepcopy(s.journal.rows)
    s.now[0] -= 1
    with pytest.raises(ValueError):
        s.ledger.reserve(s.controller, "late", "pipe")
    assert s.journal.rows == prior
    s.now[0] += 1
    s.journal.rows[-1]["at_ns"] += 1
    with pytest.raises(ValueError):
        s.ledger.read()


@pytest.mark.parametrize(
    "damage",
    [
        "parent",
        "command",
        "image",
        "creation",
        "launch-handle",
        "runtime-handle",
        "job",
        "ready",
    ],
)
def test_worker_identity_or_job_conflicts_fail_closed(damage):
    s = resources()
    api, req, ready = launch_fixture()
    req = replace(req, role="acceptance_worker")
    ready["role"] = req.role
    parent, launch, runtime = "parent", "launch", "launch"
    if damage == "parent":
        api.rows["launch"]["parent_pid"] = 9
    elif damage == "command":
        api.rows["launch"]["command_line"] = "foreign"
    elif damage == "image":
        api.rows["launch"]["sha256"] = "f" * 64
    elif damage == "creation":
        api.rows["launch"]["created"] = 1
    elif damage == "launch-handle":
        launch = None
    elif damage == "runtime-handle":
        runtime = None
    elif damage == "job":
        api.pids.add(99)
    else:
        ready["nonce"] = "wrong"
    ownership = WorkerOwnership(s.ledger, all_members=lambda: api.pids.copy())
    ownership.prepare("financial_worker", req)
    with pytest.raises(ValueError):
        ownership.bind(
            "financial_worker",
            api=api,
            request=req,
            parent_handle=parent,
            launch_handle=launch,
            runtime_handle=runtime,
            ready=ready,
        )
    assert ownership.refused
    with pytest.raises(ValueError):
        ownership.verify()


def financial_fixture():
    ms = manifests()
    rows = records()
    golden = json.loads(
        Path("tests/fixtures/fs1/legacy-synthetic-golden.json").read_text(
            encoding="utf8"
        )
    )["cases"][0]
    from test_fs1_financial_replay import records as golden_records

    rows["QUALITY_DIPS"] = golden_records(golden)
    accounts, cuts = {}, {}
    for index, lane in enumerate(ms):
        state, head, _ = replay_verified_events(ms[lane], rows[lane])
        accounts[lane] = {
            "account_id": "SYNTHETIC-" + lane,
            "manifest": ms[lane],
            "events": rows[lane],
            "snapshot": state,
            "native_source": [1, index + 100, 0],
            "source_head": head,
        }
        cuts[lane] = {
            "account_id": accounts[lane]["account_id"],
            "epoch": ms[lane]["epoch"],
            "currency": ms[lane]["currency"],
            "revision": state["revision"],
            "head": head,
            "state_digest": digest(state),
            "native_source": accounts[lane]["native_source"],
        }
    return {
        "accounts": accounts,
        "acknowledgements": {
            k: {
                stage: copy.deepcopy(v)
                for stage in ("source", "projection", "report", "global")
            }
            for k, v in cuts.items()
        },
        "before_hashes": {"source.bin": "a" * 64},
        "after_hashes": {"source.bin": "a" * 64},
        "writer_rebind_refused": True,
    }


def stop_fixture():
    s = resources()
    w = owned(s)
    data = financial_fixture()
    reader = SimpleNamespace(
        read_committed=lambda request: copy.deepcopy(data), observer_identity=None
    )
    expected = {
        k: {f: copy.deepcopy(v[f]) for f in ("account_id", "manifest", "native_source")}
        for k, v in data["accounts"].items()
    }
    stop = StopVerification(
        s.ledger,
        w.ownership,
        clock_ns=lambda: s.now[0],
        financial_reader=reader,
        expected_accounts=expected,
    )
    request = stop.begin(
        nonce="d" * 32,
        worker=w.ownership.bindings["financial_worker"].runtime,
        operation_id="SYNTHETIC-STOP",
    )
    w.api.exit_codes["launch"] = 0
    w.api.pids.clear()
    w.ownership.exit("financial_worker")
    api2, req2, ready2 = launch_fixture()
    api2.rows["launch"].update(pid=40, created=40000)
    api2.pids = {40}
    req2 = replace(req2, role="acceptance_worker")
    ready2.update(role=req2.role, pid=40)
    w.ownership.all_members = lambda: api2.pids.copy()
    w.ownership.prepare("readonly_reader", req2)
    w.ownership.bind(
        "readonly_reader",
        api=api2,
        request=req2,
        parent_handle="parent",
        launch_handle="launch",
        runtime_handle="launch",
        ready=ready2,
    )
    reader.observer_identity = copy.deepcopy(api2.rows["launch"])
    api2.exit_codes["launch"] = 0
    api2.pids.clear()
    w.ownership.exit("readonly_reader")
    release = SimpleNamespace(closed=lambda *args: True)
    for key, r in s.ledger.read()["state"]["resources"].items():
        s.ledger.close(r["owner"], key, observer=release)
    s.ledger.usage(memory={s.controller: 0}, cpu_ns=0)
    s.now[0] += 10**9
    args = {
        "acknowledgement": request,
        "drain": {
            "scope": SCOPE_HASH,
            "operation_id": request["operation_id"],
            "pending": 0,
            "unknown": False,
            "orders": 0,
        },
        "socket_cut": {
            "scope": SCOPE_HASH,
            "at_ns": s.now[0],
            "readers": {
                k: {
                    "complete": True,
                    "owned_endpoints": [],
                    "unknown": False,
                    "started_ns": s.now[0],
                    "finished_ns": s.now[0],
                }
                for k in ("CIM", "IP_HELPER", "NETSTAT")
            },
        },
        "process_cut": {
            "scope": SCOPE_HASH,
            "started_ns": s.now[0],
            "at_ns": s.now[0],
            "survivors": [],
            "unknown": False,
        },
        "release_observer": release,
    }
    return SimpleNamespace(**locals())


def test_source_only_complete_stop_includes_independent_account_replay_and_no_native_claim():
    x = stop_fixture()
    result = x.stop.finish(**x.args)
    assert result["source_contract_passed"] and result["elapsed_ns"] == 10**9
    assert not result["native_acceptance"] and not result["startup_authorized"]
    assert result["cuts"]["QUALITY_DIPS"]["currency"] == "USD"
    assert result["cuts"]["HYPERLIQUID"]["currency"] == "USDC"
    with pytest.raises(ValueError):
        x.stop.finish(**x.args)


def test_exact_eight_seconds_is_accepted_with_fresh_final_observations():
    x = stop_fixture()
    x.s.now[0] = x.stop.started + 8 * 10**9
    x.args["socket_cut"]["at_ns"] = x.s.now[0]
    for r in x.args["socket_cut"]["readers"].values():
        r.update(started_ns=x.s.now[0], finished_ns=x.s.now[0])
    x.args["process_cut"].update(started_ns=x.s.now[0], at_ns=x.s.now[0])
    assert x.stop.finish(**x.args)["elapsed_ns"] == 8 * 10**9


def test_final_journal_publication_time_is_inside_stop_and_overrun_stays_failed():
    x = stop_fixture()
    original = x.s.journal.append

    def delayed(head, event):
        original(head, event)
        if event["state"]["stops"][x.request["operation_id"]]["state"] == "CLOSED":
            x.s.now[0] += 8 * 10**9

    x.s.journal.append = delayed
    with pytest.raises(ValueError):
        x.stop.finish(**x.args)
    assert x.stop.failure and x.stop.result is None
    assert (
        x.s.ledger.read()["state"]["stops"][x.request["operation_id"]]["state"]
        == "FAILED"
    )


def test_new_stop_object_cannot_adopt_an_already_exited_worker():
    x = stop_fixture()
    another = StopVerification(
        x.s.ledger,
        x.w.ownership,
        clock_ns=lambda: x.s.now[0],
        financial_reader=x.reader,
        expected_accounts=x.expected,
    )
    with pytest.raises(ValueError):
        another.begin(
            nonce="c" * 32,
            worker=x.w.ownership.bindings["financial_worker"].runtime,
            operation_id="another",
        )


@pytest.mark.parametrize(
    "damage",
    [
        "ack",
        "drain",
        "bool-drain",
        "orphan",
        "job",
        "handles",
        "reader",
        "missing-reader",
        "state-zero",
        "pid-zero-listener",
        "reader-conflict",
        "stale",
        "process-order",
        "deadline",
        "cash",
        "account",
        "hashes",
        "global-ack",
        "bool-ack",
        "rebind",
    ],
)
def test_incomplete_stop_is_latched_and_never_relabelled_success(damage):
    x = stop_fixture()
    if damage == "ack":
        x.args["acknowledgement"] = {**x.request, "nonce": "wrong"}
    elif damage == "drain":
        x.args["drain"]["pending"] = 1
    elif damage == "bool-drain":
        x.args["drain"]["pending"] = False
    elif damage == "orphan":
        x.args["process_cut"]["survivors"] = [40]
    elif damage == "job":
        x.w.ownership.all_members = lambda: {99}
    elif damage == "handles":
        x.args["release_observer"] = SimpleNamespace(closed=lambda *args: False)
    elif damage == "reader":
        x.reader.observer_identity = x.w.api.rows["launch"]
    elif damage == "missing-reader":
        x.w.ownership.finished.remove("readonly_reader")
    elif damage in ("state-zero", "pid-zero-listener"):
        x.args["socket_cut"]["readers"]["IP_HELPER"]["owned_endpoints"] = [
            {"state": 0 if damage == "state-zero" else "LISTENING", "pid": 0}
        ]
    elif damage == "reader-conflict":
        x.args["socket_cut"]["readers"].pop("NETSTAT")
    elif damage == "stale":
        x.s.now[0] += 3 * 10**9
    elif damage == "process-order":
        x.args["process_cut"]["at_ns"] -= 1
    elif damage == "deadline":
        x.s.now[0] = x.stop.started + 8 * 10**9 + 1
        x.args["socket_cut"]["at_ns"] = x.s.now[0]
        x.args["process_cut"]["at_ns"] = x.s.now[0]
    elif damage == "cash":
        x.data["accounts"]["QUALITY_DIPS"]["snapshot"]["cash"] = "9999"
    elif damage == "account":
        x.data["accounts"]["QUALITY_DIPS"]["account_id"] = "foreign"
    elif damage == "hashes":
        x.data["after_hashes"]["source.bin"] = "b" * 64
    elif damage == "global-ack":
        x.data["acknowledgements"]["HYPERLIQUID"].pop("global")
    elif damage == "bool-ack":
        x.data["acknowledgements"]["QUALITY_DIPS"]["source"]["revision"] = True
    else:
        x.data["writer_rebind_refused"] = False
    with pytest.raises(ValueError):
        x.stop.finish(**x.args)
    assert x.stop.failure is not None and x.stop.result is None
    with pytest.raises(ValueError):
        x.stop.finish(**x.args)


def test_module_has_no_native_process_or_runtime_entrypoint():
    import ast

    tree = ast.parse(
        Path("scripts/observation_runtime/aip06_harness.py").read_text(encoding="utf8")
    )
    modules = [n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)]
    modules += [
        v.name for n in ast.walk(tree) if isinstance(n, ast.Import) for v in n.names
    ]
    assert not any(
        any(
            s in m
            for s in (
                "subprocess",
                "personal_paper_runtime",
                "socket",
                "ctypes",
                "windows_clock",
            )
        )
        for m in modules
        if m
    )


@pytest.mark.parametrize('role,accepted', [
    ('acceptance_supervisor', True), ('acceptance_worker', False),
])
def test_case_host_roster_requires_supervisor_role_and_original_binding(role, accepted):
    s = resources()
    api, request, ready = launch_fixture()
    request = replace(request, role=role)
    ready['role'] = role
    roster = WorkerOwnership(s.ledger, all_members=lambda: api.pids.copy())
    if not accepted:
        with pytest.raises(ValueError, match='DECLARED_PRELAUNCH_REQUIRED'):
            roster.prepare('case_host', request)
        assert 'case_host' not in roster.prepared
        return
    roster.prepare('case_host', request)
    roster.bind('case_host', api=api, request=request,
                parent_handle='parent', launch_handle='launch',
                runtime_handle='launch', ready=ready)
    assert roster.bindings['case_host'].request is request
    assert {row['pid'] for row in roster.verify()} == api.pids
