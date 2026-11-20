"""Synthetic orchestration only. No native selector or installed application."""

import threading

import pytest

from scripts.observation_runtime.installed_acceptance_handoff import (
    SIGNOFFS,
    submit_browser_ack,
)
from scripts.observation_runtime.installed_acceptance_sequence import (
    PreselectionCut,
    run_cycle,
)

NS = 10**9
PORT = 42005


def packet(rows=()):
    return {
        "port": PORT,
        "observations": [
            {
                "source": source,
                "query_address": "127.0.0.1",
                "query_port": PORT,
                "complete": True,
                "error": None,
                "rows": list(rows),
                "started_ns": 11 * NS + i * NS,
                "finished_ns": 12 * NS + i * NS,
            }
            for i, source in enumerate(("IP_HELPER", "CIM", "NETSTAT"))
        ],
        "snapshot": {
            "schema": "QD_SOCKET_CLEANUP_CIM_V1",
            "protocol": "TCP",
            "query_address": "127.0.0.1",
            "query_port": PORT,
            "started_ticks": 15 * NS,
            "finished_ticks": 16 * NS,
            "frequency": NS,
            "rows": list(rows),
            "non_helpers": 0,
            "error": None,
        },
    }


def row(**changes):
    return {
        "protocol": "TCP",
        "family": 4,
        "local_address": "127.0.0.1",
        "local_port": PORT,
        "remote_address": "0.0.0.0",
        "remote_port": 0,
        "state": 2,
        "owner_pid": 0,
        "owner_present": True,
        **changes,
    }


def gate(proof, *, clock=lambda: 17 * NS):
    return PreselectionCut(
        address="127.0.0.1",
        port=PORT,
        after_ns=10 * NS,
        packet=proof,
        monotonic_ns=clock,
    )


def test_exact_three_readers_and_last_process_snapshot_admit_once():
    calls = []
    cut = gate(packet())
    assert cut.dispatch(lambda: calls.append("DISPOSABLE_CALLBACK")) is None
    assert calls == ["DISPOSABLE_CALLBACK"]
    with pytest.raises(ValueError, match="ALREADY_USED"):
        cut.dispatch(lambda: calls.append("BAD"))
    assert calls == ["DISPOSABLE_CALLBACK"]


@pytest.mark.parametrize(
    "failure",
    [
        "missing",
        "no_observations",
        "missing_reader",
        "reader_error",
        "reader_silence",
        "state_zero",
        "pid_zero_listening",
        "missing_owner",
        "active_connection",
        "conflicting_reader",
        "stale_reader",
        "stale_roster",
        "wrong_endpoint",
        "wrong_family",
        "roster_first",
        "unknown_process",
        "roster_error",
        "expired_after_capture",
    ],
)
def test_ambiguous_or_missing_preselection_evidence_never_dispatches(failure):
    p = packet()
    clock = lambda: 17 * NS
    if failure == "missing":
        p = None
    elif failure == "no_observations":
        p.pop("observations")
    elif failure == "missing_reader":
        p["observations"].pop()
    elif failure == "reader_error":
        p["observations"][1]["error"] = "REFUSED"
    elif failure == "reader_silence":
        p["observations"][2]["complete"] = False
    elif failure in (
        "state_zero",
        "pid_zero_listening",
        "missing_owner",
        "active_connection",
    ):
        r = row()
        if failure == "state_zero":
            r["state"] = 0
        if failure == "missing_owner":
            r.update(owner_present=False, owner_pid=None)
        if failure == "active_connection":
            r.update(state=5, owner_pid=123)
        p = packet([r])
    elif failure == "conflicting_reader":
        p["observations"][0]["rows"] = [row(state=11)]
    elif failure == "stale_reader":
        p["observations"][0]["started_ns"] = 1
    elif failure == "stale_roster":
        p["snapshot"]["finished_ticks"] = 14 * NS
    elif failure == "wrong_endpoint":
        p["observations"][1]["query_port"] += 1
    elif failure == "wrong_family":
        p["observations"][1]["query_address"] = "::1"
    elif failure == "roster_first":
        p["snapshot"].update(started_ticks=12 * NS, finished_ticks=16 * NS)
    elif failure == "unknown_process":
        p["snapshot"]["non_helpers"] = 1
    elif failure == "roster_error":
        p["snapshot"]["error"] = "DENIED"
    elif failure == "expired_after_capture":
        clock = lambda: 20 * NS
    cut = gate(p, clock=clock)
    calls = []
    with pytest.raises(ValueError):
        cut.dispatch(lambda: calls.append("FORBIDDEN"))
    assert calls == []
    with pytest.raises(ValueError, match="ALREADY_USED"):
        cut.dispatch(lambda: calls.append("FORBIDDEN"))


def test_cached_accepted_flags_do_not_replace_raw_evidence():
    p = packet([row()])
    p.update(crosscheck={"cleanup_clear": True}, socket_process={"accepted": True})
    with pytest.raises(ValueError):
        gate(p).dispatch(lambda: pytest.fail("selected"))


class Clock:
    ns = 10 * NS

    def __call__(self):
        return self.ns


class Controller:
    def __init__(self, events, clock):
        self.events, self.clock = events, clock
        self.stopped_ns = None

    def ready(self, host_id):
        self.events.append("VERIFIED_READY")

    def stop(self):
        self.events.append("STOP")
        self.clock.ns += NS
        self.stopped_ns = self.clock.ns
        return {"closed": True, "financial_actions": 0, "seconds": 1}

    def next_cycle(self, *args, **kwargs):
        self.events.append("STRICT_NEXT_GATE")

    def finish(self):
        self.events.append("DRAIN")
        return {"accepted": True, "exit_code": 0}


def cycle_fixture(clock, events):
    r = {
        "mode": "DISPOSABLE_CONTROL_FIXTURE",
        "host_id": "a" * 32,
        "head": "b" * 64,
        "release": "SYNTHETIC_FIXTURE",
        "image": "fixture.exe",
        "url": "http://127.0.0.1:42005/",
        "providers": False,
        "financial_writers": False,
        "trading": False,
        "automatic_startup": False,
    }

    def diagnose(_):
        events.append("HTTP_DIAGNOSTICS")
        clock.ns += 20 * NS
        return {"synthetic": True}

    def collect(_, after):
        events.append("COLLECT_BUNDLE_THEN_ROSTER")
        p = packet()
        now = clock.ns
        for i, o in enumerate(p["observations"]):
            o.update(started_ns=now + i * 1000, finished_ns=now + i * 1000 + 500)
        p["snapshot"].update(started_ticks=now + 4000, finished_ticks=now + 5000)
        clock.ns = now + 6000
        assert now >= after
        return p

    return r, diagnose, collect


def test_two_cycles_ack_first_diagnostics_then_original_stop_next_and_final_drain(
    tmp_path,
):
    events = []
    clock = Clock()
    controller = Controller(events, clock)
    for cycle in (1, 2):
        r, diagnose, collect = cycle_fixture(clock, events)

        def notify(ticket):
            events.append("BROWSER_REQUEST")
            assert ticket["ready_ns"] == clock.ns
            # Explicit synthetic fixture witness, not installed/browser acceptance.
            clock.ns += 44 * NS
            submit_browser_ack(
                tmp_path, ticket, dict.fromkeys(SIGNOFFS, True), monotonic_ns=clock
            )
            events.append("FIXTURE_ACK_PUBLISHED")

        result = run_cycle(
            controller=controller,
            ready=r,
            expected={k: r[k] for k in ("release", "head", "image")},
            cycle=cycle,
            root=tmp_path,
            domain="DISPOSABLE",
            ready_ns=clock.ns,
            notify=notify,
            diagnose=diagnose,
            collect=collect,
            final=cycle == 2,
            monotonic_ns=clock,
            sleep=lambda _: None,
        )
        assert (
            result["browser"]["received_ns"]
            - result["browser"]["packet"]["ticket"]["ready_ns"]
            == 44 * NS
        )
    assert events == [
        "VERIFIED_READY",
        "BROWSER_REQUEST",
        "FIXTURE_ACK_PUBLISHED",
        "HTTP_DIAGNOSTICS",
        "STOP",
        "COLLECT_BUNDLE_THEN_ROSTER",
        "STRICT_NEXT_GATE",
        "VERIFIED_READY",
        "BROWSER_REQUEST",
        "FIXTURE_ACK_PUBLISHED",
        "HTTP_DIAGNOSTICS",
        "STOP",
        "COLLECT_BUNDLE_THEN_ROSTER",
        "DRAIN",
    ]


def test_delayed_ack_receipt_cannot_reach_unrelated_diagnostics_or_next(tmp_path):
    events = []
    clock = Clock()
    controller = Controller(events, clock)
    r, diagnose, collect = cycle_fixture(clock, events)

    def notify(ticket):
        submit_browser_ack(
            tmp_path, ticket, dict.fromkeys(SIGNOFFS, True), monotonic_ns=clock
        )
        clock.ns += 46 * NS

    with pytest.raises(ValueError, match="RECEIVED_LATE"):
        run_cycle(
            controller=controller,
            ready=r,
            expected={k: r[k] for k in ("release", "head", "image")},
            cycle=1,
            root=tmp_path,
            domain="DISPOSABLE",
            ready_ns=clock.ns,
            notify=notify,
            diagnose=diagnose,
            collect=collect,
            monotonic_ns=clock,
        )
    assert events == ["VERIFIED_READY"]


def test_bad_poststop_bundle_refuses_second_cycle_even_if_cached_pass(tmp_path):
    events = []
    clock = Clock()
    controller = Controller(events, clock)
    r, diagnose, collect = cycle_fixture(clock, events)

    def notify(ticket):
        submit_browser_ack(
            tmp_path, ticket, dict.fromkeys(SIGNOFFS, True), monotonic_ns=clock
        )

    def bad_collect(ready, after):
        p = collect(ready, after)
        p["observations"][0]["rows"] = [row()]
        return p

    with pytest.raises(ValueError, match="CLEANUP_UNRESOLVED"):
        run_cycle(
            controller=controller,
            ready=r,
            expected={k: r[k] for k in ("release", "head", "image")},
            cycle=1,
            root=tmp_path,
            domain="DISPOSABLE",
            ready_ns=clock.ns,
            notify=notify,
            diagnose=diagnose,
            collect=bad_collect,
            monotonic_ns=clock,
        )
    assert "STOP" in events and "STRICT_NEXT_GATE" not in events
    assert controller.refused
    assert (tmp_path / "cycle-1-stop-ack.json").exists()


def test_native_observed_finwait_closed_absent_pattern_stays_refused():
    p = packet()
    p["observations"][0]["rows"] = [row(state=6)]
    p["observations"][1]["rows"] = [row(state=1)]
    # This is a synthetic reproduction of the native transition, never UTC or
    # operational custody evidence. No terminal-state normalizing is allowed.
    with pytest.raises(ValueError, match="UNRESOLVED"):
        gate(p).dispatch(lambda: pytest.fail("selection must not occur"))


def test_different_thread_cannot_dispatch_preselection_action():
    cut = gate(packet())
    errors = []
    effects = []

    def other_owner():
        try:
            cut.dispatch(lambda: effects.append("BAD"))
        except ValueError as exc:
            errors.append(str(exc))

    worker = threading.Thread(target=other_owner)
    worker.start()
    worker.join(timeout=2)
    assert (
        not worker.is_alive()
        and effects == []
        and errors == ["EXACT_PRESELECTION_OWNER_REQUIRED"]
    )


def test_poststop_evidence_for_a_different_port_cannot_substitute(tmp_path):
    events = []
    clock = Clock()
    controller = Controller(events, clock)
    r, diagnose, collect = cycle_fixture(clock, events)

    def notify(ticket):
        submit_browser_ack(
            tmp_path, ticket, dict.fromkeys(SIGNOFFS, True), monotonic_ns=clock
        )

    def wrong_endpoint(ready, after):
        p = collect(ready, after)
        p["port"] = PORT + 1
        p["snapshot"]["query_port"] = PORT + 1
        for o in p["observations"]:
            o["query_port"] = PORT + 1
        return p

    with pytest.raises(ValueError, match="ENDPOINT_SUBSTITUTION"):
        run_cycle(
            controller=controller,
            ready=r,
            expected={k: r[k] for k in ("release", "head", "image")},
            cycle=1,
            root=tmp_path,
            domain="DISPOSABLE",
            ready_ns=clock.ns,
            notify=notify,
            diagnose=diagnose,
            collect=wrong_endpoint,
            monotonic_ns=clock,
        )
    assert controller.refused and "STRICT_NEXT_GATE" not in events
