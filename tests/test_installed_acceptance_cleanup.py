"""Offline fault injection. No installed launch, selection, or financial store."""

import io
import json
import subprocess

import pytest

from scripts.observation_runtime import installed_acceptance_cleanup as c


def row(**changes):
    return {
        "protocol": "TCP",
        "family": 4,
        "local_address": "127.0.0.1",
        "local_port": 42001,
        "remote_address": "0.0.0.0",
        "remote_port": 0,
        "state": 2,
        "owner_present": True,
        "owner_pid": 5000,
        **changes,
    }


def snapshot(rows=(), **changes):
    return {
        "schema": "QD_SOCKET_CLEANUP_CIM_V1",
        "protocol": "TCP",
        "query_port": 42001,
        "query_address": "127.0.0.1",
        "started_ticks": 1100000000,
        "finished_ticks": 1200000000,
        "frequency": 10**9,
        "rows": list(rows) if rows is not None else None,
        "non_helpers": 0,
        "error": None,
        **changes,
    }


def assess(s, **changes):
    return c.socket_cleanup(
        s,
        address="127.0.0.1",
        port=42001,
        stopped_ns=10**9,
        now_ns=1300000000,
        **changes,
    )


def test_confirmed_complete_fresh_empty_enumeration_is_not_process_count_inference():
    assert assess(snapshot())["accepted"]
    assert not assess(snapshot(error="Access denied"))["accepted"]
    assert not assess(snapshot(non_helpers=None))["accepted"]


@pytest.mark.parametrize("pid", [0, 3, 5000, 99999])
def test_listener_blocks_even_after_process_exit_or_unrelated_port_reuse(pid):
    evidence = assess(snapshot([row(owner_pid=pid)]))
    assert not evidence["accepted"] and evidence["matching_rows"][0]["owner_pid"] == pid
    assert evidence["enumeration_error"] is None
    assert (
        "LISTENER_REMAINS_PID_ZERO" in evidence["reasons"]
        if pid == 0
        else "LISTENER_REMAINS" in evidence["reasons"]
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"owner_pid": None, "owner_present": False},
        {"owner_pid": None},
        {"owner_pid": False},
        {"owner_pid": -1},
        {"owner_pid": 2**32},
    ],
)
def test_missing_owner_is_not_coerced_to_pid_zero(changes):
    evidence = assess(snapshot([row(**changes)]))
    assert (
        not evidence["accepted"] and "SOCKET_OWNER_UNAVAILABLE" in evidence["reasons"]
    )
    assert evidence["matching_rows"][0]["owner_pid"] == changes["owner_pid"]


@pytest.mark.parametrize("state", [0, 3, 4, 5, 6, 7, 8, 9, 10, 12, 255])
def test_active_unknown_or_transitioning_states_never_pass(state):
    assert not assess(snapshot([row(state=state)]))["accepted"]


@pytest.mark.parametrize("state", [1, 11])
def test_terminal_rows_preserved_as_evidence_not_mislabelled_listeners(state):
    result = assess(snapshot([row(state=state, owner_pid=0)]))
    assert result["accepted"] and result["matching_rows"][0]["owner_pid"] == 0


@pytest.mark.parametrize(
    "address,family,remote,blocked",
    [
        ("127.0.0.1", 4, "0.0.0.0", True),
        ("0.0.0.0", 4, "0.0.0.0", True),
        ("127.0.0.2", 4, "0.0.0.0", False),
        ("::1", 6, "::", False),
        ("::", 6, "::", True),
        ("::ffff:127.0.0.1", 6, "::", True),
    ],
)
def test_exact_endpoint_family_and_possible_wildcard_overlap(
    address, family, remote, blocked
):
    result = assess(
        snapshot([row(local_address=address, family=family, remote_address=remote)])
    )
    assert result["accepted"] is not blocked


def test_ipv6_target_not_conflated_with_concrete_ipv4():
    s = snapshot([row()], query_address="::1")
    assert c.socket_cleanup(
        s, address="::1", port=42001, stopped_ns=10**9, now_ns=1300000000
    )["accepted"]
    s["rows"] = [row(family=6, local_address="::1", remote_address="::")]
    assert not c.socket_cleanup(
        s, address="::1", port=42001, stopped_ns=10**9, now_ns=1300000000
    )["accepted"]


@pytest.mark.parametrize(
    "changes",
    [
        {"protocol": "UDP"},
        {"family": 6},
        {"local_port": 42002},
        {"local_port": "42001"},
        {"remote_port": None},
        {"remote_address": "::"},
        {"state": None},
        {"local_address": "not-an-address"},
        {"state": True},
    ],
)
def test_incomplete_or_contradictory_row_is_enumeration_failure(changes):
    result = assess(snapshot([row(**changes)]))
    assert not result["accepted"] and result["enumeration_error"]


@pytest.mark.parametrize(
    "changes",
    [
        {"error": "query failed"},
        {"rows": None},
        {"rows": [{}]},
        {"rows": [row()] * 1025},
        {"query_port": 42002},
        {"query_address": "::1"},
        {"query_address": None},
        {"protocol": "UDP"},
        {"schema": "OTHER"},
        {"started_ticks": 999999999},
        {"finished_ticks": 1400000000},
        {"frequency": 0},
        {"started_ticks": True},
        {"finished_ticks": 1000000000},
    ],
)
def test_query_failure_partial_result_or_invalid_time_refuses(changes):
    result = assess(snapshot(**changes))
    assert not result["accepted"] and result["enumeration_error"]


def test_stale_or_slow_observation_cannot_clear_restart():
    s = snapshot()
    assert not c.socket_cleanup(
        s, address="127.0.0.1", port=42001, stopped_ns=10**9, now_ns=4 * 10**9
    )["accepted"]
    assert not c.socket_cleanup(
        snapshot(finished_ticks=8 * 10**9),
        address="127.0.0.1",
        port=42001,
        stopped_ns=10**9,
        now_ns=8 * 10**9,
    )["accepted"]


def test_missing_query_completion_field_is_not_success():
    s = snapshot()
    s.pop("error")
    assert not assess(s)["accepted"]


class Handle:
    closed = False

    def __init__(self, events):
        self.events = events

    def __int__(self):
        return 123

    def Close(self):
        assert not self.closed
        self.events.append("close-handle")
        self.closed = True


class Pipe(io.BytesIO):
    def __init__(self, events):
        super().__init__()
        self.events = events

    def write(self, data):
        self.events.append(data)
        return super().write(data)


class Child:
    pid, returncode = (5000, None)

    def __init__(self):
        self.events = []
        self._handle = Handle(self.events)
        self.stdin = Pipe(self.events)
        self.stdout = io.BytesIO()
        self.stderr = io.BytesIO()
        self.timeout = False
        self.code = 0
        self.err = b""
        self.out = b""

    def poll(self):
        assert not self._handle.closed
        return self.returncode

    def communicate(self, timeout):
        assert self.stdin is None and (not self._handle.closed)
        self.events.append("communicate")
        if self.timeout:
            raise subprocess.TimeoutExpired("synthetic", timeout)
        self.returncode = self.code
        self.events.append("returncode-collected")
        return (self.out, self.err)


@pytest.fixture
def controller(monkeypatch):
    child = Child()
    identity = {"pid": 5000, "created": 12345, "image": "d:/synthetic/python.exe"}
    monkeypatch.setattr(c, "observe_pid", lambda pid: dict(identity))

    def observe(handle):
        assert not child._handle.closed
        return identity["created"]

    monkeypatch.setattr(c, "observe_handle", observe)
    monkeypatch.setattr(
        c,
        "read_ready",
        lambda *a, **kw: json.dumps(
            {"closed": True, "seconds": 0.5, "financial_actions": 0}
        ),
    )
    monkeypatch.setattr(c.time, "perf_counter_ns", lambda: 10**9)
    observer = c.AcceptanceController(child, identity)
    observer.ready("a" * 32)
    return (observer, child, identity)


def test_poststop_audit_failure_does_not_repeat_stop_and_reaps_before_handle_close(
    controller,
):
    guard, child, _ = controller
    first = guard.stop()
    with pytest.raises(ValueError, match="CLEANUP_UNRESOLVED"):
        guard.next_cycle(snapshot([row(owner_pid=0)]), address="127.0.0.1", port=42001)
    assert guard.stop() == first
    result = guard.finish()
    assert result["accepted"] and result["exit_code"] == 0
    assert child.events == [
        b"STOP " + b"a" * 32 + b"\n",
        "communicate",
        "returncode-collected",
        "close-handle",
    ]
    assert guard.finish() is result


@pytest.mark.parametrize(
    "reply",
    [
        {"closed": False, "seconds": 0.5, "financial_actions": 0},
        {"closed": True, "seconds": 8.01, "financial_actions": 0},
        {"closed": True, "seconds": True, "financial_actions": 0},
        {"closed": True, "seconds": float("nan"), "financial_actions": 0},
        {"closed": True, "seconds": 0.5, "financial_actions": True},
        {"closed": True, "seconds": 0.5, "financial_actions": 1},
        {"closed": True, "financial_actions": 0},
    ],
)
def test_uncertain_stop_no_retry_but_eof_drain_still_possible(
    controller, monkeypatch, reply
):
    guard, child, _ = controller
    monkeypatch.setattr(c, "read_ready", lambda *a, **kw: json.dumps(reply))
    with pytest.raises(ValueError):
        guard.stop()
    with pytest.raises(ValueError, match="NO_RETRY"):
        guard.stop()
    with pytest.raises(ValueError):
        guard.next_cycle(snapshot(), address="127.0.0.1", port=42001)
    assert guard.finish()["accepted"]
    assert (
        sum(isinstance(x, bytes) and x.startswith(b"STOP") for x in child.events) == 1
    )


def test_pipe_exception_does_not_bypass_reaping(controller, monkeypatch):
    guard, child, _ = controller

    def fail(*a, **k):
        raise ValueError("INSTALLED_READINESS_PIPE_REFUSED")

    monkeypatch.setattr(c, "read_ready", fail)
    with pytest.raises(ValueError):
        guard.stop()
    assert guard.finish()["accepted"] and child._handle.closed


def test_full_outer_stop_budget_cannot_be_hidden_by_small_adapter_value(
    controller, monkeypatch
):
    guard, child, _ = controller
    readings = iter([1.0, 9.01])
    monkeypatch.setattr(c.time, "perf_counter", lambda: next(readings))
    with pytest.raises(ValueError, match="EIGHT_SECOND"):
        guard.stop()
    assert guard.finish()["accepted"]
    assert child.events.count(b"STOP " + b"a" * 32 + b"\n") == 1


def test_pipe_close_error_still_collects_exit_and_disposes_handle_but_refuses(
    controller,
):
    guard, child, _ = controller
    guard.stop()

    class BrokenClose:
        def close(self):
            raise OSError("SYNTHETIC_CLOSE_ERROR")

    child.stdin = BrokenClose()
    assert (
        not guard.finish()["accepted"]
        and child.returncode == 0
        and child._handle.closed
    )


def test_drain_timeout_retains_creation_handle_and_latches_restart_refusal(controller):
    guard, child, _ = controller
    guard.stop()
    child.timeout = True
    with pytest.raises(ValueError, match="OWNERSHIP_RETAINED"):
        guard.finish()
    assert not child._handle.closed and child.returncode is None
    with pytest.raises(ValueError):
        guard.next_cycle(snapshot(), address="127.0.0.1", port=42001)
    child.timeout = False
    assert guard.finish()["accepted"]


@pytest.mark.parametrize(
    "field,value",
    [("pid", 5001), ("created", 4444), ("image", "d:/foreign/python.exe")],
)
def test_exact_native_pid_creation_image_changes_refuse_without_dispatch(
    controller, monkeypatch, field, value
):
    guard, child, identity = controller
    foreign = {**identity, field: value}
    monkeypatch.setattr(c, "observe_pid", lambda pid: foreign)
    with pytest.raises(ValueError, match="IDENTITY|CREATION|IMAGE"):
        guard.stop()
    assert not child.events


def test_native_creation_handle_change_also_refuses(controller, monkeypatch):
    guard, child, _ = controller
    monkeypatch.setattr(c, "observe_handle", lambda h: 99999)
    with pytest.raises(ValueError, match="CREATION_HANDLE"):
        guard.stop()
    assert not child.events


def test_only_complete_current_socket_and_process_evidence_admits_next(
    controller, monkeypatch
):
    guard, child, _ = controller
    guard.stop()
    monkeypatch.setattr(c.time, "perf_counter_ns", lambda: 1300000000)
    observations = [
        {
            "source": source,
            "complete": True,
            "error": None,
            "rows": [],
            "query_address": "127.0.0.1",
            "query_port": 42001,
            "started_ns": 1_100_000_000,
            "finished_ns": 1_200_000_000,
        }
        for source in ("CIM", "IP_HELPER", "NETSTAT")
    ]
    assert guard.next_cycle(
        snapshot(), address="127.0.0.1", port=42001, observations=observations
    )["accepted"]
    guard.ready("b" * 32)
    guard.stop()
    guard.finish()
    assert child.events.count(b"NEXT\n") == 1
    assert [
        x for x in child.events if isinstance(x, bytes) and x.startswith(b"STOP")
    ] == [b"STOP " + b"a" * 32 + b"\n", b"STOP " + b"b" * 32 + b"\n"]


@pytest.mark.parametrize(
    "changes",
    [
        {"non_helpers": 1},
        {"non_helpers": None},
        {"error": "query exception"},
        {"rows": [row(owner_pid=0)]},
        {"rows": [row(owner_pid=None, owner_present=False)]},
    ],
)
def test_second_open_refused_on_ambiguous_cleanup(controller, monkeypatch, changes):
    guard, child, _ = controller
    guard.stop()
    monkeypatch.setattr(c.time, "perf_counter_ns", lambda: 1300000000)
    with pytest.raises(ValueError):
        guard.next_cycle(snapshot(**changes), address="127.0.0.1", port=42001)
    with pytest.raises(ValueError):
        guard.next_cycle(snapshot(), address="127.0.0.1", port=42001)
    assert b"NEXT\n" not in child.events


@pytest.mark.parametrize(
    "code,err,out", [(1, b"", b""), (0, b"error", b""), (0, b"", b"unexpected")]
)
def test_unverified_controller_exit_never_becomes_success(controller, code, err, out):
    guard, child, _ = controller
    guard.stop()
    child.code = code
    child.err = err
    child.out = out
    assert not guard.finish()["accepted"] and child._handle.closed


@pytest.mark.parametrize(
    "problem",
    [
        "missing",
        "native_zero",
        "cim_zero",
        "pid_zero",
        "missing_owner",
        "conflict",
        "failed_query",
        "stale",
        "foreign_listener",
    ],
)
def test_second_open_requires_full_unanimous_crosscheck(
    controller, monkeypatch, problem
):
    guard, child, _ = controller
    guard.stop()
    monkeypatch.setattr(c.time, "perf_counter_ns", lambda: 1_300_000_000)
    observations = [
        {
            "source": source,
            "complete": True,
            "error": None,
            "rows": [],
            "query_address": "127.0.0.1",
            "query_port": 42001,
            "started_ns": 1_100_000_000,
            "finished_ns": 1_200_000_000,
        }
        for source in ("CIM", "IP_HELPER", "NETSTAT")
    ]
    if problem == "missing":
        observations = None
    elif problem in ("native_zero", "cim_zero"):
        observations[1 if problem == "native_zero" else 0]["rows"] = [row(state=0)]
    elif problem == "pid_zero":
        for observed in observations:
            observed["rows"] = [row(owner_pid=0)]
    elif problem == "missing_owner":
        observations[1]["rows"] = [row(owner_present=False, owner_pid=None)]
    elif problem == "conflict":
        observations[1]["rows"] = [row(state=11, owner_pid=0)]
    elif problem == "failed_query":
        observations[1]["error"] = "API_ERROR"
    elif problem == "stale":
        observations[1]["started_ns"] = 1
    elif problem == "foreign_listener":
        for observed in observations:
            observed["rows"] = [row(owner_pid=99999)]
    with pytest.raises(ValueError, match="UNANIMOUS"):
        guard.next_cycle(
            snapshot(), address="127.0.0.1", port=42001, observations=observations
        )
    assert b"NEXT\n" not in child.events
    guard.finish()
