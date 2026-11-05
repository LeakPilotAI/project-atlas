"""Actual suspended registry/graph logic over injected kernel/CIM responses."""

import copy
import ntpath
from types import SimpleNamespace
import pytest
from app.services.paper_financial_replay import digest
from scripts.observation_runtime.aip06_harness import LIMITS
from scripts.observation_runtime.aip06_native_controller import NativeAllocations
from scripts.observation_runtime.aip06_native_objects import DeclaredDescendants
from scripts.observation_runtime.aip06_windows_process import (
    NativeProcessObserver,
    Win32ProcessCalls,
)
from scripts.observation_runtime.launch_ownership import LaunchRequest
from test_aip06_native_session_stop import EXE, PIN
from test_aip06_physical_native_proofs import aggregate_fixture


def staged_fixture():
    x = aggregate_fixture()
    peer_process = x.guard.spawn([EXE, "-B", x.targets["financial_worker"]])
    peer = peer_process.child.binding
    owner = digest(peer.runtime)
    slot = "prior-descendant-launch"
    x.ledger.reserve(owner, slot, "launch")
    command = EXE + " -B D:\\reviewed\\child.py"
    image = (ntpath.normcase(EXE), tuple(PIN["file_id"]), PIN["sha256"])
    request = LaunchRequest(
        "acceptance_worker", "d" * 32, "direct", image, image, command, command
    )
    original_duplicate = x.calls.duplicate

    def duplicate(source, handle, *a, **kw):
        if source != peer.runtime_handle:
            return original_duplicate(source, handle, *a, **kw)
        kind, value = x.calls.handles[handle]
        local = x.calls.allocate(kind, value)
        if kind == "job":
            x.calls.jobs[local] = x.calls.jobs[handle]
        return local

    x.calls.duplicate = duplicate
    x.files.final_path = lambda h: x.calls.handles[h][1]
    x.suspends = {}

    def hold(h):
        key = x.calls.handles[h]
        assert x.suspends[key] == 1
        x.suspends[key] = 2
        x.calls.events.append("independent-suspended-fence")

    def resume(h):
        key = x.calls.handles[h]
        assert x.suspends[key] == 2
        x.suspends[key] = 0
        x.calls.events.append("independent-bootstrap-release")

    x.calls.hold_created_thread = hold
    x.calls.resume_staged_thread = resume

    def objects(h):
        kind, value = x.calls.handles[h]
        return {
            "type": "Thread" if kind == "thread" else kind,
            "pid": value,
            "tid": value + 1,
            "created": x.calls.rows[value]["created"] + 1,
            "exited": value in x.calls.exits,
        }

    def observer_factory(*, job, parent):
        api = NativeProcessObserver(
            calls=x.calls,
            cim=x.cim,
            images=x.controller.profile["images"],
            clock_ns=lambda: x.now[0],
        )
        api.job, api.parent = job, parent
        return api

    objects_port = SimpleNamespace(
        same=lambda a, b: x.calls.handles[a] == x.calls.handles[b], observe=objects
    )
    registry = DeclaredDescendants(
        peer=peer,
        calls=x.calls,
        objects=objects_port,
        allocations=x.alloc,
        observer_factory=observer_factory,
        aggregate=x.aggregate,
        files=x.files,
    )
    registry.declare(request, slot=slot, parent_owner=owner, resources=x.ledger)
    creator = NativeAllocations(x.ledger, owner, namespace="source-creator")
    held = []

    def allocate(kind, label, operation):
        key = creator.reserve(label, kind)
        h = operation()
        held.append((key, h))
        return h

    limits = {
        k: LIMITS[k]
        for k in ("processes", "private_bytes", "child_private_bytes", "cpu_ns")
    }
    limits["kill_on_close"] = True
    job = allocate(
        "job", "leaf", lambda: x.calls.create_job("injected-new-leaf", limits)
    )
    parent = allocate(
        "handle",
        "parent-original",
        lambda: x.calls.allocate("process", peer.runtime["pid"]),
    )
    source = allocate("image", "source-image", lambda: x.files.open_image(EXE))
    thread_ticket = creator.reserve("primary-before-create", "thread")
    assert x.ledger.state["resources"][slot]["kind"] == "launch"
    hp, ht, pid, tid = x.calls.create_suspended(
        executable=EXE, argv=[EXE, "-B", r"D:\reviewed\child.py"]
    )
    held.append((thread_ticket, ht))
    x.calls.rows[pid]["parent_pid"] = peer.runtime["pid"]
    x.suspends[x.calls.handles[ht]] = 1
    # Inject the documented inherited parent/root chain before leaf assignment.
    for group in (x.aggregate.job, peer.api.job, job):
        x.calls.assign(group, hp)
    proof = {
        "nonce": request.nonce,
        "parent": parent,
        "launch": hp,
        "thread": ht,
        "tid": tid,
        "image": source,
        "job": job,
    }
    return SimpleNamespace(**locals())


def test_original_registry_stages_before_resume_binds_real_ready_and_releases_exact_handles():
    f = staged_fixture()
    x = f.x
    r = f.registry
    receipt = r.stage_suspended(f.proof)
    assert receipt["released_to_bootstrap"] is False and not receipt["financial_ack"]
    assert x.suspends[x.calls.handles[f.ht]] == 2
    assert "independent-bootstrap-release" not in x.calls.events
    assert r.staging.verify()["members"] == [20, 30]
    released = r.resume_staged(f.request.nonce)
    assert not released["guard_release"] and not released["financial_ack"]
    assert x.suspends[x.calls.handles[f.ht]] == 0
    bound, h = r.import_binding(
        {
            "nonce": f.request.nonce,
            "parent": f.parent,
            "launch": f.hp,
            "runtime": f.hp,
            "job": f.job,
            "ready": {
                "pid": f.pid,
                "nonce": f.request.nonce,
                "role": "acceptance_worker",
            },
        }
    )
    x.ledger.bind_reserved_process(f.slot, f.owner, bound, h)
    assert x.calls.members(f.peer.api.job) == {20, 30} and x.calls.members(
        x.aggregate.job
    ) == {10, 20, 30}
    x.calls.exits[f.pid] = 0
    for job in x.calls.jobs.values():
        job["members"].discard(f.pid)
    result = r.release(f.request.nonce, deadline_ns=x.now[0] + 10**9)
    assert result["normal_exit"] and f.request.nonce in r.finished
    assert all(x.calls.closed(h) for _, h in r.held[f.request.nonce])
    assert not r.allocations.live.intersection(k for k, _ in r.held[f.request.nonce])
    # Creator-side handles remain separate capabilities until independent exit.
    assert not x.calls.closed(f.hp)
    for key, h in reversed(f.held):
        x.calls.close(h)
        assert x.calls.closed(h)
        f.creator.release(key)
    x.calls.close(f.hp)
    assert x.calls.closed(f.hp)
    x.ledger.close(
        digest(bound.runtime),
        f.slot,
        observer=SimpleNamespace(
            closed=lambda owner, key: (
                owner == digest(bound.runtime)
                and key == f.slot
                and x.calls.closed(f.hp)
            )
        ),
    )
    f.peer_process.communicate()
    x.aggregate.close(deadline_ns=x.now[0] + 10**9)
    assert not x.calls.handles and all(
        v["closed"] for v in x.ledger.state["resources"].values()
    )


@pytest.mark.parametrize(
    "damage",
    [
        "parent",
        "job",
        "thread",
        "image",
        "missing",
        "extra",
        "expired",
        "count",
        "source",
        "tid",
    ],
)
def test_suspended_stage_never_adopts_unverified_handles_or_members(damage):
    f = staged_fixture()
    x = f.x
    proof = copy.deepcopy(f.proof)
    if damage == "parent":
        proof["parent"] = f.hp
    elif damage == "job":
        proof["job"] = x.aggregate.job
    elif damage == "thread":
        proof["thread"] = f.hp
    elif damage == "image":
        proof["image"] = f.hp
    elif damage == "missing":
        x.calls.jobs[f.peer.api.job]["members"].remove(f.pid)
    elif damage == "extra":
        x.calls.jobs[f.peer.api.job]["members"].add(999)
    elif damage == "expired":
        x.now[0] += 7 * 10**9
    elif damage == "count":

        def bad(h):
            raise ValueError("injected running thread")

        x.calls.hold_created_thread = bad
    elif damage == "source":
        x.calls.rows[f.pid]["command_line"] = "foreign command"
    else:
        proof["tid"] += 1
    with pytest.raises((ValueError, KeyError, TypeError)):
        f.registry.stage_suspended(proof)
    assert f.registry.failed and "independent-bootstrap-release" not in x.calls.events
    assert f.pid not in x.calls.exits
    with pytest.raises(ValueError):
        f.registry.resume_staged(f.request.nonce)


def test_staged_full_job_proof_does_not_change_original_leaf_binding_refusal():
    f = staged_fixture()
    f.registry.stage_suspended(f.proof)
    with pytest.raises(ValueError, match="JOB_PROCESS"):
        f.peer.verify()
    assert f.peer.refused
    with pytest.raises(ValueError):
        f.registry.staging.verify()


@pytest.mark.parametrize("counts", [(1, 2, 1), (0, 2, 1), (1, 1, 1), (1, 2, 0)])
def test_real_suspend_api_adapter_requires_both_original_counts_before_bootstrap(
    counts,
):
    class Kernel:
        def __init__(self):
            self.resumes = iter(counts[1:])
            self.events = []

        def SuspendThread(self, h):
            self.events.append(("hold", h))
            return counts[0]

        def ResumeThread(self, h):
            self.events.append(("resume", h))
            return next(self.resumes)

    kernel = Kernel()
    calls = Win32ProcessCalls(kernel)
    if counts == (1, 2, 1):
        calls.hold_created_thread(77)
        calls.resume_staged_thread(77)
        assert kernel.events == [("hold", 77), ("resume", 77), ("resume", 77)]
    else:
        with pytest.raises(ValueError):
            calls.hold_created_thread(77)
            calls.resume_staged_thread(77)


def test_observed_graph_mismatch_cannot_be_repaired_into_later_acceptance():
    f = staged_fixture()
    f.registry.stage_suspended(f.proof)
    f.x.calls.jobs[f.peer.api.job]["members"].add(999)
    with pytest.raises(ValueError):
        f.registry.staging.verify()
    f.x.calls.jobs[f.peer.api.job]["members"].remove(999)
    assert f.registry.staging.failed
    with pytest.raises(ValueError, match="LATCHED"):
        f.registry.staging.verify()
    with pytest.raises(ValueError):
        f.registry.resume_staged(f.request.nonce)
    assert "independent-bootstrap-release" not in f.x.calls.events


def test_replayed_bootstrap_release_latches_refusal_without_a_second_resume():
    f = staged_fixture()
    f.registry.stage_suspended(f.proof)
    f.registry.resume_staged(f.request.nonce)
    before = list(f.x.calls.events)
    with pytest.raises(ValueError):
        f.registry.resume_staged(f.request.nonce)
    assert (
        f.registry.failed and f.registry.staging.failed and f.x.calls.events == before
    )
