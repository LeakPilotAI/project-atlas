"""Low-CPU, synthetic and one short Windows-native R17 CPU-budget checks.

No copy, financial authority, provider calls or broad test suite.
"""
from __future__ import annotations

import sys

import pytest

from scripts.observation_runtime import atlas_r17_cpu_budget as cpu


@pytest.mark.parametrize(("available", "wanted"), [
    (0b111111111111, 0b110000000000),
    (0b101010101, 0b101000000),
    (0b11111, 0b11000),
])
def test_affinity_restricts_to_two_allowed_high_logical_cpus(available, wanted):
    selected = cpu.choose_bounded_mask(available)
    assert selected == wanted
    assert (selected & available) == selected
    assert selected.bit_count() == 2


@pytest.mark.parametrize("mask", [0, -1, 1, 3, True, None, "4095"])
def test_insufficient_or_invalid_affinity_never_starts(mask):
    with pytest.raises(ValueError, match="R17_CPU_NOT_ENOUGH_ALLOWED"):
        cpu.choose_bounded_mask(mask)


@pytest.mark.parametrize(("first", "second", "expected"), [
    ((0, 0, 0), (80, 100, 0), 20.0),
    ((0, 0, 0), (30, 100, 0), 70.0),
    ((10, 20, 30), (60, 120, 30), 50.0),
])
def test_native_system_times_busy_formula(first, second, expected):
    assert cpu.cpu_busy_percent(first, second) == expected


@pytest.mark.parametrize(("first", "second"), [
    ((0, 0, 0), (0, 0, 0)),
    ((0, 0, 0), (110, 100, 0)),
    ((100, 100, 0), (99, 200, 0)),
    ((0, 0, 0), (-1, 0, 0)),
    ((0, 0, 0), (True, 100, 0)),
])
def test_unknown_or_invalid_system_load_refuses(first, second):
    with pytest.raises(ValueError, match="R17_CPU_SYSTEM_SAMPLE"):
        cpu.cpu_busy_percent(first, second)


def fixture_budget(monkeypatch, *, samples, state=None):
    observed = {"mask": 0xFFF, "clock": 0.0, "changes": []}
    if state:
        observed.update(state)
    guard = cpu.NativeR17CpuBudget(
        kernel=object(), wait=lambda seconds: None,
        monotonic=lambda: observed["clock"],
    )
    monkeypatch.setattr(guard, "_native", lambda: setattr(guard, "process", 123))
    monkeypatch.setattr(guard, "_affinity",
                        lambda: (observed["mask"], 0xFFF))
    def set_mask(value):
        observed["mask"] = value
        observed["changes"].append(value)
    monkeypatch.setattr(guard, "_set_affinity", set_mask)
    readings = iter(samples)
    monkeypatch.setattr(guard, "_times", lambda: next(readings))
    return guard, observed


def test_budget_affinity_kept_and_restored_after_success(monkeypatch):
    guard, observed = fixture_budget(monkeypatch, samples=[
        (0,0,0), (80,100,0), (160,200,0), (240,300,0),
        (320,400,0), (400,500,0),
    ])
    with guard:
        assert guard.active
        assert observed["mask"] == 0xC00
        observed["clock"] = 1.4
        assert guard.pulse()
    assert observed["mask"] == 0xFFF
    assert observed["changes"] == [0xC00, 0xFFF]
    assert not guard.active


def test_busy_host_aborts_before_native_copy_and_restores_affinity(monkeypatch):
    guard, observed = fixture_budget(monkeypatch, samples=[
        (0,0,0), (5,100,0),
    ])
    with pytest.raises(ValueError, match="HOST_BUSY_NO_NATIVE_COPY"), guard:
        pytest.fail("BUSY_HOST_MUST_NOT_ENTER_NATIVE_COPY")
    assert observed["mask"] == 0xFFF
    assert not guard.active


def test_cpu_pressure_during_copy_refuses_and_restores(monkeypatch):
    guard, observed = fixture_budget(monkeypatch, samples=[
        (0,0,0), (90,100,0), (180,200,0), (270,300,0),
        (360,400,0), (365,500,0),
    ])
    with pytest.raises(ValueError, match="HOST_BUSY_PRESERVE_PARTIAL"), guard:
        observed["clock"] = 2.0
        guard.pulse()
    assert observed["mask"] == 0xFFF


def test_affinity_drift_during_native_copy_refuses_and_restores(monkeypatch):
    guard, observed = fixture_budget(monkeypatch, samples=[
        (0,0,0), (80,100,0), (160,200,0),
        (240,300,0), (320,400,0),
    ])
    with pytest.raises(ValueError, match="AFFINITY_DRIFT"), guard:
        observed["mask"] = 0x400
        observed["clock"] = 2.0
        guard.pulse()
    assert observed["mask"] == 0xFFF


def test_monotonic_time_rollback_refuses_copy(monkeypatch):
    guard, observed = fixture_budget(monkeypatch, samples=[
        (0,0,0), (80,100,0), (160,200,0),
        (240,300,0), (320,400,0),
    ])
    with pytest.raises(ValueError, match="MONOTONIC_ROLLBACK"), guard:
        observed["clock"] = -2.0
        guard.pulse()
    assert observed["mask"] == 0xFFF


def test_cpu_budget_never_returns_install_or_financial_authority():
    assert not hasattr(cpu.NativeR17CpuBudget, "issue_lease")
    assert not hasattr(cpu.NativeR17CpuBudget, "publish_selection")
    assert cpu.MAX_LOGICAL_CPUS == 2
    assert cpu.MAX_SYSTEM_CPU_PERCENT == 70.0


@pytest.mark.skipif(sys.platform != "win32", reason="Native Windows only")
def test_real_windows_native_process_affinity_is_restored_immediately():
    # Genuine OS original PROCESS handle/affinity readback, only a 0.3s load
    # sample; no full installation, child processes, market feed or account I/O.
    guard = cpu.NativeR17CpuBudget()
    guard._native()
    original, _ = guard._affinity()
    try:
        with guard:
            current, system = guard._affinity()
            assert current == guard.restricted_mask
            assert current.bit_count() <= 2
            assert current & ~system == 0
            assert current != original
            assert guard.pulse()
    except ValueError as exc:
        # A busy shared host must refuse admission; still confirm no
        # process affinity remains modified after the exception.
        if str(exc) == "R17_CPU_HOST_BUSY_NO_NATIVE_COPY":
            assert guard._affinity()[0] == original
            pytest.skip("Host CPU busy; production CPU admission correctly refused")
        raise
    restored, _ = guard._affinity()
    assert restored == original
    assert guard.original_mask is None
    assert not guard.active


def test_four_window_preflight_rejects_late_cpu_spike_and_restores(monkeypatch):
    guard, observed = fixture_budget(monkeypatch, samples=[
        (0,0,0), (80,100,0), (160,200,0), (165,300,0),
    ])
    with pytest.raises(ValueError, match="HOST_BUSY_NO_NATIVE_COPY"), guard:
        pytest.fail("LATE_SPIKE_CANNOT_ENTER_NATIVE_COPY")
    assert observed["mask"] == 0xFFF
    assert not guard.active


def test_cpu_preflight_requires_multiple_consecutive_samples():
    assert cpu.INITIAL_SAMPLE_WINDOWS == 4
    assert cpu.INITIAL_SAMPLE_WINDOWS * cpu.INITIAL_SAMPLE_SECONDS >= 2.0
