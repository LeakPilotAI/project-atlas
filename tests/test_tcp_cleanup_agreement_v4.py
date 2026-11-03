"""V4 offline lifecycle evidence; no Windows settings or installed application."""

import sys
from pathlib import Path

import pytest

from scripts.observation_runtime import installed_acceptance_capture as capture
from scripts.observation_runtime.installed_acceptance_capture_v4 import collect
from scripts.observation_runtime.installed_acceptance_sequence import PreselectionCut
from scripts.observation_runtime.socket_evidence import reconcile
from tests.run_tcp_cleanup_agreement_v4 import verify_fixture_ready
from tests.test_installed_acceptance_capture import NS, PORT, rig, row


def frames(states=(11, 11, 11)):
    return [
        {
            "source": source,
            "query_address": "127.0.0.1",
            "query_port": PORT,
            "complete": True,
            "error": None,
            "rows": [] if state is None else [row(state=state, pid=0)],
            "started_ns": (11 + index) * NS,
            "finished_ns": (11 + index) * NS + 10,
        }
        for index, (source, state) in enumerate(
            zip(capture.TEARDOWN_ORDER, states, strict=True)
        )
    ]


@pytest.mark.parametrize(
    "states,expected",
    [
        ((6, 6, 6), False),
        ((7, 7, 7), False),
        ((11, 11, 11), True),
        ((1, 1, 1), True),
        ((None, None, None), True),
        ((6, 1, None), False),
        ((7, 11, None), False),
        ((1, 11, 11), False),
        ((2, 2, 2), False),
        ((0, 0, 0), False),
    ],
)
def test_unmodified_three_reader_gate_all_terminal_active_and_conflicting_states(
    states, expected
):
    decision = reconcile(
        frames(states),
        address="127.0.0.1",
        port=PORT,
        after_ns=10 * NS,
        now_ns=19 * NS,
    )
    assert decision["cleanup_clear"] is expected


@pytest.mark.parametrize("fault", ["missing", "stale", "owner", "endpoint", "error"])
def test_new_order_never_excuses_unusable_evidence(fault):
    values = frames()
    if fault == "missing":
        values.pop()
    elif fault == "stale":
        values[0]["started_ns"] = NS
    elif fault == "owner":
        values[1]["rows"][0]["owner_pid"] = 99
    elif fault == "endpoint":
        values[1]["query_port"] += 1
    else:
        values[1]["error"] = "QUERY_FAILED"
    assert not reconcile(
        values, address="127.0.0.1", port=PORT, after_ns=10 * NS, now_ns=19 * NS
    )["cleanup_clear"]


def test_capture_v4_invokes_each_reader_once_then_strict_roster(tmp_path, monkeypatch):
    events, run = rig(monkeypatch)
    result = collect(
        repo=tmp_path,
        evidence=tmp_path,
        port=PORT,
        after_ns=10 * NS,
        label="ordered",
        run=run,
    )
    assert events == ["CIM", "NETSTAT", "IP_HELPER", "PROCESS_ROSTER"]
    assert result["reader_order"] == ["CIM", "NETSTAT", "IP_HELPER"]
    assert result["crosscheck"]["cleanup_clear"]


@pytest.mark.parametrize(
    "order",
    [(), ("CIM",), ("CIM", "CIM", "IP_HELPER"), ["CIM", "NETSTAT", "IP_HELPER"]],
)
def test_partial_or_ambiguous_order_refuses_before_any_query(tmp_path, order):
    with pytest.raises(ValueError, match="EXACT_THREE_READER_ORDER_REQUIRED"):
        capture.collect(
            repo=tmp_path,
            evidence=tmp_path,
            port=PORT,
            after_ns=NS,
            label="invalid",
            run=lambda *_: pytest.fail("query"),
            reader_order=order,
        )
    assert not list(tmp_path.iterdir())


def test_failed_cut_cannot_be_resampled_and_dispatched(tmp_path, monkeypatch):
    _events, run = rig(monkeypatch)
    packet = collect(
        repo=tmp_path,
        evidence=tmp_path,
        port=PORT,
        after_ns=10 * NS,
        label="cut",
        run=run,
    )
    packet["observations"][0]["rows"] = [row(state=6, pid=0)]
    gate = PreselectionCut(
        address="127.0.0.1",
        port=PORT,
        after_ns=10 * NS,
        packet=packet,
        monotonic_ns=lambda: 19 * NS,
    )
    with pytest.raises(ValueError, match="UNRESOLVED"):
        gate.dispatch(lambda: pytest.fail("must not dispatch"))
    gate.packet["observations"][0]["rows"] = []
    with pytest.raises(ValueError, match="ALREADY_USED_OR_REFUSED"):
        gate.dispatch(lambda: pytest.fail("failed attempt cannot revive"))


def test_old_disagreement_stays_a_failure_independent_of_reader_iteration_order():
    values = frames((1, None, 6))
    assert not reconcile(
        values, address="127.0.0.1", port=PORT, after_ns=10 * NS, now_ns=19 * NS
    )["cleanup_clear"]
    assert not reconcile(
        list(reversed(values)),
        address="127.0.0.1",
        port=PORT,
        after_ns=10 * NS,
        now_ns=19 * NS,
    )["cleanup_clear"]


@pytest.mark.parametrize(
    "fault", [None, "pid", "image", "provider", "missing", "release"]
)
def test_fixture_image_check_uses_same_canonical_path_as_native_observer(fault):
    image = str(Path(sys.executable).resolve())
    identity = {"pid": 123, "image": image.casefold()}
    ready = {
        "pid": 123,
        "image": image,
        "release": "SYNTHETIC_FIXTURE",
        "head": "f" * 64,
        "providers": False,
        "financial_writers": False,
        "trading": False,
        "automatic_startup": False,
    }
    if fault == "pid":
        ready["pid"] = 124
    elif fault == "image":
        ready["image"] = str(Path(image).with_name("foreign.exe"))
    elif fault == "provider":
        ready["providers"] = 0
    elif fault == "missing":
        del ready["trading"]
    elif fault == "release":
        ready["release"] = "OPERATIONAL"
    if fault is None:
        verify_fixture_ready(ready, identity)
    else:
        with pytest.raises(
            ValueError, match="EXACT_DISPOSABLE_READY_IDENTITY_REQUIRED"
        ):
            verify_fixture_ready(ready, identity)


def test_review_worker_uses_eof_verified_probe_and_v4_order_without_changing_gates():
    root = Path(__file__).resolve().parents[1]
    worker = (root / "scripts/acceptance_harness_v3/worker.py").read_text()
    adapter = (root / "scripts/acceptance_harness_v3/capture.py").read_text()
    assert (
        "from scripts.observation_runtime.acceptance_http_probe import probe" in worker
    )
    assert "HTTPConnection(" not in worker
    assert "installed_acceptance_capture_v4 import collect" in adapter
    assert "sample=run_cycle(" in worker
    assert "PreselectionCut(" in worker
