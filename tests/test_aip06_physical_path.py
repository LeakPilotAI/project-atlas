"""Injected physical-path responses only. Never loads Windows or starts a child."""

import copy
from types import SimpleNamespace
import pytest
from scripts.observation_runtime.aip06_native_query import (
    ARGS,
    NETSTAT,
    NativeQueryExecutor,
)
from scripts.observation_runtime.aip06_cleanup_providers import GuardedNetstat
from test_aip06_native_session_stop import PIN
from test_aip06_physical_native_proofs import aggregate_fixture, Pipes


def query_fixture(damage=None):
    x = aggregate_fixture()
    x.controller.profile["session"] = "a" * 32
    x.port.pinned_images[NETSTAT.casefold()] = copy.deepcopy(PIN)
    x.files.final_path = lambda h: x.calls.handles[h][1]
    x.pipes = Pipes(x.calls)
    x.calls.pipe = x.pipes.pair
    create = x.calls.create_suspended
    resume = x.calls.resume
    kill = x.calls.terminate_created
    x.raw = b"\r\nActive Connections\r\n\r\n  Proto  Local Address          Foreign Address        State           PID\r\n  TCP    127.0.0.1:1234         0.0.0.0:0              LISTENING       123\r\n"

    def spawn(**kw):
        result = create(**kw)
        pid = result[2]
        if kw["executable"] != NETSTAT:
            return result
        x.calls.rows[pid]["image"] = NETSTAT.casefold()
        if damage == "image":
            x.calls.rows[pid]["image"] = x.parent["image"]
        if damage == "birth":
            x.calls.rows[pid]["parent_pid"] = 99
        if damage == "assignment":
            x.calls.fail = "assign"
        return result

    x.calls.create_suspended = spawn

    def start(h):
        resume(h)
        if x.executor.active is None:
            return
        if damage == "timeout":
            return
        s = x.executor.active
        writes = [v for k, v in s["held"] if x.calls.handles[v][0] == "pipe"]
        # Parent has closed inherited/write ends; find original read endpoints.
        reads = [h for h in writes if h in x.pipes.buffers]
        assert len(reads) == 2
        x.pipes.buffers[reads[0]].extend(
            b"x" * 65537 if damage == "oversize" else x.raw
        )
        x.calls.exits[x.calls.native(s["launch"])["pid"]] = 0
        for j in x.calls.jobs.values():
            j["members"].discard(result_pid(s))

    def result_pid(s):
        return x.calls.native(s["launch"])["pid"]

    x.calls.resume = start

    def terminate(h, expected):
        kill(h, expected)
        for j in x.calls.jobs.values():
            j["members"].discard(expected["pid"])

    x.calls.terminate_created = terminate
    original_job_kill = x.calls.terminate_owned_job

    def terminate_job(job):
        original_job_kill(job)
        for group in x.calls.jobs.values():
            group["members"].difference_update(x.calls.exits)

    x.calls.terminate_owned_job = terminate_job
    available = x.pipes.available

    def count(h):
        n = available(h)
        if n:
            return n
        if (
            x.executor.active["launch"] is not None
            and x.calls.lifecycle(x.executor.active["launch"])["exited"]
        ):
            exc = OSError("injected pipe EOF")
            exc.winerror = 109
            raise exc
        return 0

    x.pipes.available = count
    x.pipes.pause = lambda: x.now.__setitem__(0, x.now[0] + 100_000_000)
    x.records = []
    x.executor = NativeQueryExecutor(
        x.port, pipes=x.pipes, output=SimpleNamespace(append=x.records.append)
    )
    x.port.native_queries = x.executor
    return x


def test_actual_guard_native_query_preserves_native_output_exit_provenance_and_full_release():
    x = query_fixture()
    result = x.guard.query(ARGS, timeout=1)
    assert (
        result["closed"]
        and result["exit_code"] == 0
        and result["identity"]["image"] == NETSTAT.casefold()
    )
    assert result["stdout"].encode() == x.raw and result["stderr"] == ""
    assert (
        x.records[-1]["schema"] == "AIP06_NATIVE_COMMAND_V1"
        and not x.records[-1]["financial_ack"]
    )
    assert x.records[-1]["closed"] and x.records[-1]["failure"] is None
    assert x.port.all_members() == set() and x.aggregate.finished == {20}
    assert set(x.calls.handles) == {h for _, h in x.aggregate.held}
    assert all(
        v["closed"]
        for k, v in x.ledger.state["resources"].items()
        if k not in {k for k, _ in x.aggregate.held}
    )


@pytest.mark.parametrize(
    "damage", ["timeout", "oversize", "birth", "assignment", "image"]
)
def test_query_failure_keeps_original_refusal_and_cleans_original_owned_process(damage):
    x = query_fixture(damage)
    with pytest.raises((ValueError, OSError)):
        x.guard.query(ARGS, timeout=1)
    assert x.executor.failed and "release" not in x.protocol.events
    assert all(pid == 10 or pid in x.calls.exits for pid in x.calls.rows)
    assert all(not (j["members"] - {10}) for j in x.calls.jobs.values())
    assert x.records and x.records[-1]["failure"] and not x.records[-1]["financial_ack"]


@pytest.mark.parametrize("damage", ["path", "arguments", "pin"])
def test_native_query_refuses_undeclared_command_before_creation(damage):
    x = query_fixture()
    argv = list(ARGS)
    if damage == "path":
        argv[0] = "C:\\private\\netstat.exe"
    elif damage == "arguments":
        argv.append("-b")
    else:
        x.port.pinned_images.pop(NETSTAT.casefold())
    with pytest.raises(ValueError):
        x.guard.query(argv, timeout=1)
    assert "create-suspended" not in x.calls.events


def test_real_netstat_reader_keeps_three_reader_parser_semantics_over_native_command():
    x = query_fixture()
    observed = GuardedNetstat(x.guard, ARGS).read(deadline_ns=x.now[0] + 10**9)
    assert observed["complete"] and observed["error"] is None
    assert observed["rows"][0]["state"] == 2 and observed["rows"][0]["owner_pid"] == 123


def probe_fixture(damage=None):
    import ntpath
    import json
    from scripts.observation_runtime.aip06_harness import BASE, SCOPE_HASH
    from scripts.observation_runtime.aip06_native_controller import NativeController

    x = aggregate_fixture()
    target = ntpath.join(
        ntpath.dirname(ntpath.dirname(BASE)),
        "scripts",
        "observation_runtime",
        "aip06_legacy_entry.py",
    )
    x.targets["query"] = target
    x.controller.profile["targets"]["query"] = target
    x.controller.profile["source_pins"][target] = "a" * 64
    x.controller.profile["session"] = "c" * 32
    c = NativeController.__new__(NativeController)
    c.__dict__.update(x.controller.__dict__)
    c.initialized = True
    c.failed = False
    c.guard = x.guard
    c.process_port = x.port
    c.legacy_probes = None
    c.verify_source = x.controller.verify_source
    x.port.controller = c
    x.c = c
    x.records = []
    c.bind_legacy_probes(
        SimpleNamespace(
            append=x.records.append, producer={"session": c.profile["session"]}
        )
    )

    def communicate(child, request, **kw):
        actual = child.binding.runtime
        ready = {
            "schema": "AIP06_LEGACY_READY_V1",
            "scope": SCOPE_HASH,
            "case": request["case"],
            "nonce": request["nonce"],
            "pid": actual["pid"],
            "created": actual["created"],
            "image": actual["image"],
            "role": "acceptance_supervisor"
            if request["case"] == "direct-supervisor"
            else "acceptance_worker",
        }
        if damage == "nonce":
            ready["nonce"] = "d" * 32
        elif damage == "pid":
            ready["pid"] += 1
        elif damage == "extra":
            ready["unverified"] = True
        x.calls.finish(child)
        return json.dumps(ready) + "\n", ""

    x.protocol.communicate = communicate
    return x


def test_actual_legacy_adapter_reuses_guard_session_binding_and_exact_terminal_readback():
    from scripts.observation_runtime.aip06_harness import ROOTS

    x = probe_fixture()
    result = x.port.legacy_probe(ROOTS["L"], ["direct-worker"])
    assert result["passed"] and result["native_acceptance"] is False
    assert len(result["cases"]) == 1
    assert len(x.c.legacy_probes.runs) == 1 and all(
        row["verified"] for row in x.c.legacy_probes.runs.values()
    )
    assert x.port.all_members() == set() and all(
        pid == 10 or pid in x.calls.exits for pid in x.calls.rows
    )
    assert set(x.calls.handles) == {h for _, h in x.aggregate.held}


@pytest.mark.parametrize("damage", ["nonce", "pid", "extra"])
def test_legacy_probe_rejects_changed_genuine_output_and_preserves_failure(damage):
    x = probe_fixture(damage)
    with pytest.raises(ValueError):
        x.c.probe_case("direct-worker")
    assert x.c.legacy_probes.failed and not x.c.legacy_probes.runs


@pytest.mark.parametrize("damage", ["copy", "time", "source"])
def test_legacy_verifier_does_not_accept_unretained_or_changed_source(damage):
    x = probe_fixture()
    result = x.c.probe_case("direct-worker")
    if damage == "copy":
        result["ready"]["created"] += 1
    elif damage == "time":
        x.now[0] += 181 * 10**9
    else:
        result["source"]["target_sha256"] = "0" * 64
    with pytest.raises(ValueError):
        x.c.verify_probe_result(result)


@pytest.mark.parametrize("case", ["direct-unexpected", "direct-supervisor"])
def test_legacy_unsupported_unexpected_descendant_remains_blocked_before_creation(case):
    x = probe_fixture()
    with pytest.raises(ValueError, match="SUPPORTED_RETAINED_SOURCE"):
        x.c.probe_case(case)
    assert "create-suspended" not in x.calls.events


def _dmtf(created):
    from datetime import datetime, timedelta

    return (datetime(1601, 1, 1) + timedelta(microseconds=created // 10)).strftime(
        "%Y%m%d%H%M%S.%f"
    ) + "+000"


@pytest.mark.parametrize(
    "damage",
    [
        None,
        "query-timeout",
        "invalid-netstat",
        "missing-ack",
        "drain",
        "leak",
        "stop-deadline",
    ],
)
def test_original_three_sample_financial_path_includes_native_query_and_strict_reader_release(
    tmp_path, damage
):
    import ast, inspect
    import test_aip06_source_closure as original
    from scripts.observation_runtime.aip06_cleanup_providers import (
        ThreeReaderCleanup,
        StrictProcessCleanup,
    )
    from scripts.observation_runtime.aip06_stop import GuardedStopCollector

    original_function = original.test_actual_guard_factory_collector_and_original_financial_verifier_complete_three_offline_samples
    observed = {}

    def factory():
        x = query_fixture("timeout" if damage == "query-timeout" else None)
        x.raw = (
            b"Active Connections\r\n  Proto Local Address Foreign Address State PID\r\n"
        )
        if damage == "invalid-netstat":
            x.raw += b" TCP 127.0.0.1:1234 0.0.0.0:0 UNKNOWN_STATE 0\r\n"
        if damage == "leak":
            x.ledger.reserve(x.owner, "unreleased-original-test-resource", "job")
        if damage in ("missing-ack", "drain"):
            ready = x.protocol.ready

            def wrapped(child, *a, **kw):
                result = ready(child, *a, **kw)
                send = child.channel.send

                def corrupt(kind, payload, **limits):
                    send(kind, payload, **limits)
                    if kind == "STOP":
                        if damage == "missing-ack":
                            child.channel.queue.pop(0)
                        else:
                            child.channel.queue[1][1]["pending"] = 1

                child.channel.send = corrupt
                return result

            x.protocol.ready = wrapped
        observed["x"] = x
        return x

    def collector(**kw):
        x = observed["x"]
        old_sockets = kw["sockets"]
        old_processes = kw["processes"]

        def empty(deadline_ns):
            return {
                "complete": True,
                "error": None,
                "rows": [],
                "started_ns": x.now[0],
                "finished_ns": x.now[0],
            }

        output = SimpleNamespace(append=x.records.append)
        sockets = ThreeReaderCleanup(
            readers={
                "CIM": SimpleNamespace(read=empty),
                "IP_HELPER": SimpleNamespace(read=empty),
                "NETSTAT": GuardedNetstat(x.guard, ARGS),
            },
            port=x.port,
            output=output,
            clock_ns=lambda: x.now[0],
        )

        def table(**limits):
            parent = x.aggregate.controller
            return {
                "complete": True,
                "error": None,
                "started_ns": x.now[0],
                "finished_ns": x.now[0],
                "rows": [
                    {
                        "ProcessId": parent["pid"],
                        "CreationDate": _dmtf(parent["created"]),
                        "ExecutablePath": parent["image"],
                        "ParentProcessId": parent["parent_pid"],
                        "CommandLine": parent["command_line"],
                    }
                ],
            }

        processes = StrictProcessCleanup(
            port=x.port,
            tables=SimpleNamespace(read=table),
            output=output,
            clock_ns=lambda: x.now[0],
        )

        def socket_cut(**limits):
            old_sockets.collect(**limits)
            if damage == "stop-deadline":
                x.now[0] += 9 * 10**9
            return sockets.collect(**limits)

        def process_cut(**limits):
            old_processes.collect(**limits)
            return processes.collect(**limits)

        kw.update(
            sockets=SimpleNamespace(collect=socket_cut),
            processes=SimpleNamespace(collect=process_cut),
        )
        return GuardedStopCollector(**kw)

    namespace = dict(
        original.__dict__, aggregate_fixture=factory, GuardedStopCollector=collector
    )
    module = ast.parse(inspect.getsource(original_function))
    exec(compile(module, inspect.getsourcefile(original_function), "exec"), namespace)
    invoke = lambda: namespace[original_function.__name__](tmp_path)
    if damage is None:
        invoke()
        x = observed["x"]
        assert len(x.executor.records) == 3 and all(
            r["failure"] is None and r["closed"] for r in x.executor.records
        )
        assert (
            len(x.aggregate.rows) == 9
            and x.aggregate.generation == 2
            and not x.calls.handles
        )
        assert (
            len([r for r in x.records if r["schema"] == "AIP06_STRICT_PROCESS_CUT_V1"])
            == 3
        )
        assert all(v["closed"] for v in x.ledger.state["resources"].values())
    else:
        with pytest.raises((ValueError, AssertionError, IndexError)):
            invoke()
        x = observed["x"]
        assert x.aggregate.generation == 0
        assert not x.ledger.state["stops"] or all(
            v["state"] != "CLOSED" for v in x.ledger.state["stops"].values()
        )


def test_source_readback_accepts_kernel_case_normalization_and_still_rejects_other_drives():
    import hashlib
    from scripts.observation_runtime.aip06_child_entry import ChildRuntime
    from test_aip06_source_closure import lease_fixture
    from test_aip06_windows_adapters import FileResponses
    from scripts.observation_runtime.aip06_windows_io import AllocationBook

    x = lease_fixture()
    files = FileResponses()
    path = "d:\\runtime\\python.exe"
    files.rows[path] = {
        "path": path,
        "parent_id": [1, 2, 0],
        "id": [1, 3, 0],
        "kind": "file",
        "reparse": False,
        "links": 1,
    }
    files.raw[path] = b"PINNED_OFFLINE_IMAGE"
    files.open_image = files.allocate
    runtime = ChildRuntime(
        files=files, calls=None, cim_api=None, pipes=None, clock_ns=lambda: x.now[0]
    )
    runtime.book = AllocationBook(x.client, x.client.owner, files, lambda: x.now[0])
    result = runtime._source(path, hashlib.sha256(files.raw[path]).hexdigest())
    assert result["closed"] and not files.handles
    with pytest.raises(ValueError):
        runtime._source("c:\\runtime\\python.exe", result["sha256"])


def test_query_close_refusal_keeps_original_capabilities_and_failure_evidence():
    x = query_fixture()
    close = x.calls.close

    def refuse(h):
        if x.calls.handles[h] == ("image", NETSTAT):
            raise OSError("injected original image close failure")
        close(h)

    x.calls.close = refuse
    with pytest.raises(OSError):
        x.guard.query(ARGS, timeout=1)
    assert x.executor.failed and x.executor.active is not None and x.guard.failed
    assert x.executor.active["held"] and x.records[-1]["cleanup_failure"]
    assert not x.records[-1]["closed"] and x.records[-1]["unresolved_tickets"]
    with pytest.raises(ValueError):
        x.guard.query(ARGS, timeout=1)


def test_query_late_cleanup_is_recorded_as_failure_not_a_late_passing_ack():
    x = query_fixture()
    close = x.calls.close

    def late(h):
        close(h)
        if x.executor.active is not None and h == x.executor.active["launch"]:
            x.now[0] += 2 * 10**9

    x.calls.close = late
    with pytest.raises(ValueError):
        x.guard.query(ARGS, timeout=1)
    assert (
        x.guard.failed
        and x.records[-1]["failure"]
        == "ValueError:QUERY_CLEANUP_EXCEEDED_ORIGINAL_DEADLINE"
    )
    assert x.records[-1]["closed"] and not x.records[-1]["financial_ack"]


def test_query_known_creation_failure_releases_only_proved_unused_slots():
    from scripts.observation_runtime.aip06_windows_process import SuspendedLaunchFailure

    x = query_fixture()

    def refuse(**kw):
        raise SuspendedLaunchFailure(
            created=None, cause=OSError("injected"), restore_errors=[]
        )

    x.calls.create_suspended = refuse
    with pytest.raises(SuspendedLaunchFailure):
        x.guard.query(ARGS, timeout=1)
    assert x.records[-1]["closed"] and x.records[-1]["failure"]
    assert set(x.calls.handles) == {h for _, h in x.aggregate.held}
    assert all(
        v["closed"]
        for k, v in x.ledger.state["resources"].items()
        if k not in {k for k, _ in x.aggregate.held}
    )


def test_query_captures_nonzero_terminal_status_without_fabricated_success():
    x = query_fixture()
    resume = x.calls.resume

    def fail(h):
        resume(h)
        x.calls.exits[x.calls.native(x.executor.active["launch"])["pid"]] = 17

    x.calls.resume = fail
    with pytest.raises(ValueError):
        x.guard.query(ARGS, timeout=1)
    assert x.records[-1]["terminal_exit_code"] == 17 and x.records[-1]["failure"]
    assert x.records[-1]["closed"] and not x.records[-1]["financial_ack"]


def test_query_capacity_refusal_occurs_before_any_create_and_retains_failure_record():
    from scripts.observation_runtime.aip06_harness import LIMITS

    x = query_fixture()
    from scripts.observation_runtime.native_fixture_budget import BudgetRefused

    count = 0
    # Real pure-ledger reservations, each within the unchanged 1 MiB per-effect
    # limit. No filesystem allocation or native capacity acceptance is claimed.
    for size in (1024**2, 0):
        for _ in range(512):
            count += 1
            try:
                x.ledger.reserve(
                    x.owner, "already-charged-work:" + str(count), "file", size=size
                )
            except BudgetRefused as exc:
                assert str(exc) == "PROSPECTIVE_RESOURCE_LIMIT"
                break
        else:
            raise AssertionError("fixture work bound was not reached")
    assert x.ledger.state["charged_bytes"] <= LIMITS["bytes"] - LIMITS["stop_bytes"]
    with pytest.raises(ValueError):
        x.guard.query(ARGS, timeout=1)
    assert "create-suspended" not in x.calls.events and x.guard.failed
    assert x.records and x.records[-1]["failure"] and x.records[-1]["closed"]


def test_unexpected_query_job_member_cannot_pass_and_cleanup_uses_only_original_query_job():
    x = query_fixture()
    resume = x.calls.resume

    def unexpected(h):
        resume(h)
        state = x.executor.active
        # Simulated kernel member; no PID-based open, query or adoption exists.
        x.calls.jobs[state["job"]]["members"].add(999)
        x.calls.jobs[x.aggregate.job]["members"].add(999)

    x.calls.resume = unexpected
    with pytest.raises(ValueError):
        x.guard.query(ARGS, timeout=1)
    assert (
        x.guard.failed
        and x.records[-1]["failure"]
        and not x.records[-1]["financial_ack"]
    )
    assert "terminate-owned-job" in x.calls.events
    assert x.calls.members(x.aggregate.job) == {10} and x.calls.exits[999] == 71
    assert 999 not in x.aggregate.rows
