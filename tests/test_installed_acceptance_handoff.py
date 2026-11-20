"""Offline deadline and real receive-order fixtures; no browser or service."""

import json
import threading
from pathlib import Path

import pytest

from scripts.observation_runtime import installed_acceptance_handoff as h


class Clock:
    def __init__(self, ns=10**9):
        self.ns = ns

    def __call__(self):
        return self.ns


def ready(**changes):
    return {
        "mode": "DISPOSABLE_CONTROL_FIXTURE",
        "release": "SYNTHETIC_FIXTURE",
        "head": "a" * 64,
        "image": str(Path("fixture-python.exe")),
        "host_id": "b" * 32,
        "url": "http://127.0.0.1:42005/",
        "providers": False,
        "financial_writers": False,
        "trading": False,
        "automatic_startup": False,
        **changes,
    }


def window(root, clock, *, cycle=1, **changes):
    r = ready(**changes)
    return h.BrowserWindow(
        root=root,
        cycle=cycle,
        ready=r,
        expected={k: ready()[k] for k in ("release", "head", "image")},
        ready_ns=10**9,
        domain="DISPOSABLE",
        monotonic_ns=clock,
    )


def signoffs():
    return dict.fromkeys(h.SIGNOFFS, True)


@pytest.mark.parametrize("elapsed", [0, 1, 44 * 10**9, 45 * 10**9])
def test_genuine_driver_signoff_received_in_existing_window(tmp_path, elapsed):
    clock = Clock()
    w = window(tmp_path, clock)
    clock.ns += elapsed
    h.submit_browser_ack(tmp_path, w.ticket, signoffs(), monotonic_ns=clock)
    result = w.receive()
    assert result["accepted"] and result["received_ns"] == clock.ns
    assert w.ticket["deadline_ns"] == 46 * 10**9


def test_late_signoff_is_not_published_or_preacknowledged(tmp_path):
    clock = Clock()
    w = window(tmp_path, clock)
    clock.ns = 46 * 10**9 + 1
    with pytest.raises(ValueError, match="ACK_LATE"):
        h.submit_browser_ack(tmp_path, w.ticket, signoffs(), monotonic_ns=clock)
    assert not (tmp_path / "cycle-1-browser-ack.json").exists()


def test_generated_in_time_but_received_late_must_refuse(tmp_path):
    clock = Clock()
    w = window(tmp_path, clock)
    clock.ns = 45 * 10**9
    h.submit_browser_ack(tmp_path, w.ticket, signoffs(), monotonic_ns=clock)
    clock.ns = 46 * 10**9 + 1
    with pytest.raises(ValueError, match="RECEIVED_LATE"):
        w.receive()
    clock.ns = 45 * 10**9
    with pytest.raises(ValueError, match="LATCHED"):
        w.receive()


def test_receipt_captured_before_unrelated_diagnostics_stall(tmp_path):
    clock = Clock()
    w = window(tmp_path, clock)
    clock.ns = 45 * 10**9
    h.submit_browser_ack(tmp_path, w.ticket, signoffs(), monotonic_ns=clock)
    receipt = w.receive()
    clock.ns = 100 * 10**9  # Reporting later cannot change the observed receipt.
    assert w.receive() is receipt and receipt["received_ns"] == 45 * 10**9


def test_missing_ack_timeout_is_latched_no_revival(tmp_path):
    clock = Clock()
    w = window(tmp_path, clock)
    assert w.receive() is None
    clock.ns = 46 * 10**9 + 1
    with pytest.raises(ValueError, match="MISSING"):
        w.receive()
    clock.ns = 45 * 10**9
    h.submit_browser_ack(tmp_path, w.ticket, signoffs(), monotonic_ns=clock)
    with pytest.raises(ValueError, match="LATCHED"):
        w.receive()


def test_ready_origin_is_not_reset_by_delayed_request_or_navigation(tmp_path):
    clock = Clock(40 * 10**9)
    w = window(tmp_path, clock)
    assert w.ticket["ready_ns"] == 10**9 and w.ticket["deadline_ns"] == 46 * 10**9
    clock.ns = 46 * 10**9 + 1
    with pytest.raises(ValueError):
        h.submit_browser_ack(tmp_path, w.ticket, signoffs(), monotonic_ns=clock)


@pytest.mark.parametrize("field", list(h.SIGNOFFS))
@pytest.mark.parametrize("value", [False, 1, "true", None])
def test_missing_or_nonboolean_browser_claim_is_not_success(tmp_path, field, value):
    clock = Clock()
    w = window(tmp_path, clock)
    evidence = signoffs()
    evidence[field] = value
    with pytest.raises(ValueError, match="GENUINE_BROWSER"):
        h.submit_browser_ack(tmp_path, w.ticket, evidence, monotonic_ns=clock)
    assert not (tmp_path / "cycle-1-browser-ack.json").exists()


@pytest.mark.parametrize(
    "field,value",
    [
        ("host_id", "c" * 32),
        ("head", "c" * 64),
        ("cycle", 2),
        ("nonce", "c" * 32),
        ("domain", "WINDOWS_LOCAL"),
        ("deadline_ns", 47 * 10**9),
    ],
)
def test_foreign_replayed_or_changed_window_ack_refuses(tmp_path, field, value):
    clock = Clock()
    w = window(tmp_path, clock)
    h.submit_browser_ack(tmp_path, w.ticket, signoffs(), monotonic_ns=clock)
    path = tmp_path / "cycle-1-browser-ack.json"
    packet = json.loads(path.read_bytes())
    packet["ticket"][field] = value
    path.write_text(json.dumps(packet))
    with pytest.raises(ValueError, match="IDENTITY_OR_WITNESS"):
        w.receive()


def test_no_overwrite_duplicate_ack_or_ticket(tmp_path):
    clock = Clock()
    w = window(tmp_path, clock)
    h.submit_browser_ack(tmp_path, w.ticket, signoffs(), monotonic_ns=clock)
    original = (tmp_path / "cycle-1-browser-ack.json").read_bytes()
    with pytest.raises(FileExistsError):
        h.submit_browser_ack(tmp_path, w.ticket, signoffs(), monotonic_ns=clock)
    with pytest.raises(FileExistsError):
        window(tmp_path, clock)
    assert (tmp_path / "cycle-1-browser-ack.json").read_bytes() == original


def test_invalid_json_latches_refusal_and_cannot_be_repaired_in_place(tmp_path):
    clock = Clock()
    w = window(tmp_path, clock)
    (tmp_path / "cycle-1-browser-ack.json").write_text("{")
    with pytest.raises(ValueError):
        w.receive()
    (
        tmp_path / "cycle-1-browser-ack.json"
    ).unlink()  # This test owns its corrupt fixture.
    h.submit_browser_ack(tmp_path, w.ticket, signoffs(), monotonic_ns=clock)
    with pytest.raises(ValueError, match="LATCHED"):
        w.receive()


def test_publication_delayed_by_disk_io_refuses_before_visibility(
    tmp_path, monkeypatch
):
    clock = Clock()
    w = window(tmp_path, clock)
    create = h._create

    def slow_write(path, value):
        create(path, value)
        clock.ns = 46 * 10**9 + 1

    monkeypatch.setattr(h, "_create", slow_write)
    with pytest.raises(ValueError, match="LATE_BEFORE_PUBLICATION"):
        h.submit_browser_ack(tmp_path, w.ticket, signoffs(), monotonic_ns=clock)
    assert not (tmp_path / "cycle-1-browser-ack.json").exists()


@pytest.mark.parametrize(
    "change",
    [
        {"financial_writers": True},
        {"providers": True},
        {"trading": True},
        {"automatic_startup": True},
        {"image": "foreign.exe"},
        {"head": "f" * 64},
        {"mode": "INSTALLED_NONFINANCIAL_ONLY"},
        {"url": "https://example.com/"},
    ],
)
def test_unverified_ready_or_foreign_origin_never_creates_window(tmp_path, change):
    with pytest.raises(ValueError):
        window(tmp_path, Clock(), **change)
    assert list(tmp_path.iterdir()) == []


def test_synthetic_binding_cannot_be_relabelled_as_installed(tmp_path):
    r = ready()
    with pytest.raises(ValueError):
        h.BrowserWindow(
            root=tmp_path,
            cycle=1,
            ready=r,
            expected={k: r[k] for k in ("release", "head", "image")},
            ready_ns=10**9,
            domain="WINDOWS_LOCAL",
            monotonic_ns=Clock(),
        )


def test_timely_receipt_survives_later_diagnostic_failure(tmp_path):
    clock = Clock()
    w = window(tmp_path, clock)
    h.submit_browser_ack(tmp_path, w.ticket, signoffs(), monotonic_ns=clock)
    receipt = w.receive()
    assert (
        json.loads((tmp_path / "cycle-1-browser-receipt.json").read_bytes()) == receipt
    )


def test_regressing_clock_before_publication_never_passes(tmp_path):
    clock = Clock()
    w = window(tmp_path, clock)
    ticks = iter([2 * 10**9, 10**9])
    with pytest.raises(ValueError, match="LATE_BEFORE_PUBLICATION"):
        h.submit_browser_ack(
            tmp_path, w.ticket, signoffs(), monotonic_ns=lambda: next(ticks)
        )
    assert not (tmp_path / "cycle-1-browser-ack.json").exists()


def test_missing_ack_with_reversed_receiver_clock_refuses(tmp_path):
    clock = Clock()
    w = window(tmp_path, clock)
    clock.ns = 1
    with pytest.raises(ValueError, match="CLOCK_REVERSED"):
        w.receive()


def test_different_receiver_thread_cannot_race_receipt_publication(tmp_path):
    clock = Clock()
    w = window(tmp_path, clock)
    h.submit_browser_ack(tmp_path, w.ticket, signoffs(), monotonic_ns=clock)
    errors = []

    def other_owner():
        try:
            w.receive()
        except ValueError as exc:
            errors.append(str(exc))

    worker = threading.Thread(target=other_owner)
    worker.start()
    worker.join(timeout=2)
    assert not worker.is_alive() and errors == ["EXACT_BROWSER_RECEIVER_OWNER_REQUIRED"]
    assert w.receive()["accepted"]
