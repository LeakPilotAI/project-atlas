"""R13 review-only code installation safety. No copying or provider access.

Priority-drift, deadline and throttle cases use a fake kernel32 and clock.
One tiny Windows child-priority inheritance case and one real READ-ONLY
release-plan check are allowed; no native copy or market access.
"""
import copy
import json
import os
import subprocess
import sys

import pytest

from scripts import atlas_r13_low_impact_installer as r13


class Kernel:
    def __init__(self, *, fail_idle=False, fail_restore=False,
                 false_idle_readback=False):
        self.priority = 0x20
        self.calls = []
        self.fail_idle = fail_idle
        self.fail_restore = fail_restore
        self.false_idle_readback = false_idle_readback

    def GetCurrentProcess(self):
        return 1337

    def GetPriorityClass(self, handle):
        assert handle == 1337
        if self.false_idle_readback and self.priority == r13.IDLE_PRIORITY_CLASS:
            return 0x20
        return self.priority

    def SetPriorityClass(self, handle, priority):
        assert handle == 1337
        self.calls.append(priority)
        if (priority == r13.IDLE_PRIORITY_CLASS and self.fail_idle or
                priority == 0x20 and self.fail_restore):
            return 0
        self.priority = priority
        return 1


@pytest.mark.skipif(os.name != "nt", reason="native Windows priority inheritance")
def test_installed_readback_style_child_inherits_idle_priority():
    # Same CREATE_NO_WINDOW-only flag shape as installed_readback() uses.
    # A real child must not silently undo the low-impact parent contract.
    import ctypes
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.GetCurrentProcess.restype = ctypes.c_void_p
    kernel.GetPriorityClass.argtypes = [ctypes.c_void_p]
    kernel.GetPriorityClass.restype = ctypes.c_uint32
    original = kernel.GetPriorityClass(kernel.GetCurrentProcess())
    child_code = (
        "import ctypes as C; k=C.WinDLL('kernel32'); "
        "k.GetCurrentProcess.restype=C.c_void_p; "
        "k.GetPriorityClass.argtypes=[C.c_void_p]; "
        "k.GetPriorityClass.restype=C.c_uint32; "
        "print(k.GetPriorityClass(k.GetCurrentProcess()))"
    )
    with r13.LowImpactEnvelope():
        cp = subprocess.run(
            [sys.executable, "-I", "-B", "-S", "-c", child_code],
            capture_output=True, text=True, timeout=8,
            creationflags=subprocess.CREATE_NO_WINDOW,
            env={key: os.environ[key] for key in
                 ("SystemRoot", "WINDIR", "TEMP", "TMP", "PATH")
                 if key in os.environ},
        )
        assert cp.returncode == 0, cp.stderr
        assert cp.stdout.strip() == str(r13.IDLE_PRIORITY_CLASS)
    assert kernel.GetPriorityClass(kernel.GetCurrentProcess()) == original


def test_low_impact_envelope_paces_and_restores_priority(monkeypatch):
    kernel=Kernel()
    sleeps=[]
    clock=[100.0]
    monkeypatch.setattr(r13, "_selector_unchanged", lambda: True)
    with r13.LowImpactEnvelope(
            kernel=kernel, wait=sleeps.append, monotonic=lambda:clock[0],
            check_every=8, pause_seconds=.06, max_seconds=40) as guard:
        for _ in range(24):
            assert guard.tick() is True
        assert kernel.priority == r13.IDLE_PRIORITY_CLASS
        assert sleeps==[.06,.06,.06]
        assert guard.checks==24
    assert kernel.priority==0x20
    assert kernel.calls==[r13.IDLE_PRIORITY_CLASS,0x20]
    with pytest.raises(ValueError,match="NOT_ACTIVE"):
        guard.tick()


def test_r13_copy_pacing_decoupled_from_safety_checks(monkeypatch):
    kernel = Kernel()
    pauses, selectors = [], []
    monkeypatch.setattr(r13, "_selector_unchanged",
                        lambda: selectors.append(True) or True)
    with r13.LowImpactEnvelope(
            kernel=kernel, wait=pauses.append, monotonic=lambda: 5.0,
            check_every=32, pace_every=128, pause_seconds=.06,
            max_seconds=500) as guard:
        for _ in range(256):
            assert guard.tick() is True
        assert guard.checks == 256
        assert len(selectors) == 8  # Selector/priority every 32 admissions.
        assert pauses == [.06, .06]  # Deliberate wait only every 128.
        assert kernel.priority == r13.IDLE_PRIORITY_CLASS
    assert kernel.priority == 0x20


def test_r13_idle_priority_loss_still_refused_before_first_pause(monkeypatch):
    kernel = Kernel()
    pauses = []
    monkeypatch.setattr(r13, "_selector_unchanged", lambda: True)
    with r13.LowImpactEnvelope(
            kernel=kernel, wait=pauses.append, monotonic=lambda: 5.0,
            check_every=32, pace_every=128, max_seconds=500) as guard:
        for _ in range(31):
            guard.tick()
        kernel.priority = 0x20
        with pytest.raises(ValueError, match="IDLE_PRIORITY_LOST"):
            guard.tick()
    assert pauses == []  # The safety guard did not wait until 128.


@pytest.mark.parametrize("invalid", [0, 16, 33, 129, True, 32.0])
def test_r13_pacing_policy_rejects_invalid_cadence(invalid):
    with pytest.raises(ValueError, match="BOUNDED_PACING_CADENCE"):
        r13.LowImpactEnvelope(check_every=32, pace_every=invalid)


def test_low_impact_envelope_restores_after_failure(monkeypatch):
    kernel=Kernel()
    monkeypatch.setattr(r13, "_selector_unchanged",lambda: True)
    with pytest.raises(RuntimeError,match="SYNTHETIC_INTERRUPT"):
        with r13.LowImpactEnvelope(kernel=kernel,wait=lambda _:None,
                                   monotonic=lambda:1.0):
            raise RuntimeError("SYNTHETIC_INTERRUPT")
    assert kernel.priority==0x20


def test_idle_priority_must_be_accepted_before_any_work():
    kernel=Kernel(fail_idle=True)
    with pytest.raises(ValueError,match="IDLE_PRIORITY_REQUIRED"):
        with r13.LowImpactEnvelope(kernel=kernel,wait=lambda _:None,
                                   monotonic=lambda:1.0):
            pytest.fail("NO_WORK_BEFORE_LOW_PRIORITY")
    assert kernel.priority==0x20


def test_idle_priority_must_read_back_before_native_io():
    kernel = Kernel(false_idle_readback=True)
    with pytest.raises(ValueError, match="IDLE_PRIORITY_READBACK_REFUSED"):
        with r13.LowImpactEnvelope(kernel=kernel, wait=lambda _: None,
                                   monotonic=lambda: 1.0):
            pytest.fail("NO_NATIVE_IO_WITHOUT_CONFIRMED_IDLE_PRIORITY")
    assert kernel.priority == 0x20
    assert kernel.calls == [r13.IDLE_PRIORITY_CLASS, 0x20]


def test_idle_priority_drift_mid_copy_refuses_and_restores(monkeypatch):
    kernel = Kernel()
    monkeypatch.setattr(r13, "_selector_unchanged", lambda: True)
    with r13.LowImpactEnvelope(kernel=kernel, wait=lambda _: None,
                               monotonic=lambda: 1.0, check_every=8) as guard:
        for _ in range(7):
            guard.tick()
        kernel.priority = 0x20  # Simulate interference during native copying.
        with pytest.raises(ValueError, match="IDLE_PRIORITY_LOST"):
            guard.tick()
    assert kernel.priority == 0x20


def test_deadline_rechecked_after_throttle_wait(monkeypatch):
    kernel = Kernel()
    now = [1.0]
    monkeypatch.setattr(r13, "_selector_unchanged", lambda: True)
    with r13.LowImpactEnvelope(kernel=kernel, wait=lambda _: now.__setitem__(0, 32.0),
                               monotonic=lambda: now[0], max_seconds=30,
                               check_every=8) as guard:
        for _ in range(7):
            guard.tick()
        with pytest.raises(ValueError, match="PRESERVE_PARTIAL"):
            guard.tick()
    assert kernel.priority == 0x20


def test_low_impact_time_bound_refuses_and_restores(monkeypatch):
    kernel=Kernel()
    now=[100.0]
    monkeypatch.setattr(r13, "_selector_unchanged",lambda:True)
    with r13.LowImpactEnvelope(
            kernel=kernel,wait=lambda _:None,monotonic=lambda:now[0],
            max_seconds=30) as guard:
        assert guard.tick() is True
        now[0]=130.0
        with pytest.raises(ValueError,match="PRESERVE_PARTIAL"):
            guard.tick()
    assert kernel.priority==0x20


@pytest.mark.parametrize("bad_kwargs",[
    {"check_every":0},{"check_every":False},{"check_every":129},
    {"pause_seconds":0},{"pause_seconds":.5},
    {"max_seconds":10},{"max_seconds":591},
])
def test_low_impact_envelope_rejects_unbounded_configuration(bad_kwargs):
    with pytest.raises(ValueError,match="BOUNDED_LOW_RESOURCE"):
        r13.LowImpactEnvelope(**bad_kwargs)


def test_original_selector_pin_checked_before_create_only(monkeypatch):
    monkeypatch.setattr(r13, "_selector_unchanged",lambda:True)
    monkeypatch.setattr(r13.os.path,"lexists",lambda path:False)
    assert r13._r12_unchanged() is True
    monkeypatch.setattr(r13.os.path,"lexists",
                        lambda path:path==r13.DESTINATION)
    with pytest.raises(ValueError,match="ALREADY_USED"):
        r13._r12_unchanged()


def test_existing_partial_destination_does_not_block_priority_tick(monkeypatch):
    kernel=Kernel()
    monkeypatch.setattr(
        r13.os.path,"lexists",
        lambda path:path==r13.DESTINATION,
    )
    calls=[]
    monkeypatch.setattr(r13,"_selector_unchanged",lambda:calls.append("sel") or True)
    with r13.LowImpactEnvelope(
            kernel=kernel,wait=lambda _:None,
            monotonic=lambda:10.0,check_every=8) as guard:
        for _ in range(8):assert guard.tick() is True
    assert calls==["sel"]
    # A prior broken version incorrectly refused its own destination here.


def test_future_install_preflight_runs_at_idle_before_any_journal(monkeypatch):
    """An approved synthetic entry cannot hash inputs at normal priority."""
    from scripts.observation_runtime import atlas_independent_ntp_clock as ntp
    from scripts import install_version_safe_candidate as clock_gate

    class FakeClock:
        def require_operational(self, identity):
            assert identity.startswith("r13-code-only-")

    kernel = Kernel()
    original_envelope = r13.LowImpactEnvelope

    class SimulatedEnvelope(original_envelope):
        def __init__(self, **kwargs):
            super().__init__(kernel=kernel, wait=lambda _: None,
                             monotonic=lambda: 1.0, **kwargs)

    def refuse_after_priority_check():
        assert kernel.priority == r13.IDLE_PRIORITY_CLASS
        raise RuntimeError("SYNTHETIC_STOP_BEFORE_JOURNAL")

    monkeypatch.setattr(ntp, "IndependentNtpClock", FakeClock)
    monkeypatch.setattr(clock_gate, "_qualify_native_clock_180s",
                        lambda *_: None)
    monkeypatch.setattr(r13, "_require_separate_consent", lambda: None)
    monkeypatch.setattr(r13, "LowImpactEnvelope", SimulatedEnvelope)
    monkeypatch.setattr(r13, "prepare_readonly", refuse_after_priority_check)
    monkeypatch.setattr(r13, "write_new_json",
                        lambda *_args, **_kwargs: pytest.fail("NO_NATIVE_JOURNAL"))
    monkeypatch.setattr(r13, "_copy_prepared_code",
                        lambda **_kwargs: pytest.fail("NO_NATIVE_COPY"))
    with pytest.raises(RuntimeError, match="SYNTHETIC_STOP_BEFORE_JOURNAL"):
        r13.install(execute_approved=True, clock=FakeClock())
    assert kernel.priority == 0x20
    assert kernel.calls == [r13.IDLE_PRIORITY_CLASS, 0x20]


def test_no_code_copy_without_fresh_pinned_separate_approval(monkeypatch):
    # Explicit one-time local operator consent never changes default fail-closed
    # behavior in a fresh checkout without a separately pinned grant.
    monkeypatch.setattr(r13, "APPROVAL_SHA256", None)
    monkeypatch.setattr(r13,"_copy_prepared_code",
                        lambda **_:pytest.fail("NO_COPY_OR_NATIVE_WRITE"))
    monkeypatch.setattr(r13,"prepare_readonly",
                        lambda:pytest.fail("NO_PREAPPROVAL_PLAN"))
    with pytest.raises(ValueError,match="EXPLICIT_CODE_INSTALL"):
        r13.install(execute_approved=False)
    with pytest.raises(ValueError,match="NOT_YET_GRANTED"):
        r13.install(execute_approved=True)


def test_readonly_review_file_is_not_an_install_approval(monkeypatch):
    monkeypatch.setattr(r13, "APPROVAL_SHA256", None)
    review = r13._read_review()
    assert all(x is False for x in review["flags"].values())
    assert review["source"]["commit"] == r13.SOURCE
    with pytest.raises(ValueError,match="NOT_YET_GRANTED"):
        r13._require_separate_consent()


def test_readonly_inspection_low_priority_preflight_and_restoration(monkeypatch):
    """The public inspect CLI must not hash inputs at normal CPU priority."""
    kernel = Kernel()
    original = r13.LowImpactEnvelope

    class SimulatedEnvelope(original):
        def __init__(self):
            super().__init__(kernel=kernel, wait=lambda _: None,
                             monotonic=lambda: 1.0)

    def simulated_plan():
        assert kernel.priority == r13.IDLE_PRIORITY_CLASS
        return {
            "runtime": {"source.py": {}},
            "dependencies": {"python/python.exe": {}},
            "names": ["source.py", "python/python.exe"],
            "total": 42,
        }

    monkeypatch.setattr(r13, "LowImpactEnvelope", SimulatedEnvelope)
    monkeypatch.setattr(r13, "prepare_readonly", simulated_plan)
    report = r13.inspect()
    assert report["planned_files"] == 2
    assert report["planned_bytes"] == 42
    assert report["installation_authorized"] is False
    assert report["paper_orders_authorized"] is False
    assert kernel.priority == 0x20
    assert kernel.calls == [r13.IDLE_PRIORITY_CLASS, 0x20]


def test_readonly_inspection_low_priority_refusal_restores(monkeypatch):
    kernel = Kernel()
    original = r13.LowImpactEnvelope

    class SimulatedEnvelope(original):
        def __init__(self):
            super().__init__(kernel=kernel, wait=lambda _: None,
                             monotonic=lambda: 1.0)

    def refused_plan():
        assert kernel.priority == r13.IDLE_PRIORITY_CLASS
        raise ValueError("SIMULATED_PIN_MISMATCH")

    monkeypatch.setattr(r13, "LowImpactEnvelope", SimulatedEnvelope)
    monkeypatch.setattr(r13, "prepare_readonly", refused_plan)
    with pytest.raises(ValueError, match="SIMULATED_PIN_MISMATCH"):
        r13.inspect()
    assert kernel.priority == 0x20


def test_exact_pinned_readonly_plan_has_no_financial_or_native_effect():
    # A prior one-shot attempt may have permanently occupied the destination.
    # The read-only inspection must then refuse before source/plan work; the
    # test cannot treat a preserved failed install as a fresh empty namespace.
    if any(os.path.lexists(path) for path in (
            r13.DESTINATION, r13.RECEIPT,
            r13.RECEIPT.with_suffix(".pending.jsonl"))):
        with pytest.raises(ValueError, match="R13_CREATE_ONLY_DESTINATION_ALREADY_USED"):
            r13.inspect()
        return
    report=r13.inspect()
    assert report["status"]=="SOURCE_DEPENDENCY_AND_LAYOUT_VERIFIED_NOT_INSTALL_APPROVAL"
    assert report["planned_files"]==10518
    assert report["native_python_files"]==9566
    assert report["planned_bytes"]==263440156
    assert report["idle_priority_required"] is True
    assert report["paced_native_copy_and_readback_required"] is True
    for key in ("installation_authorized","installed","selected",
                "startup_authorized","paper_orders_authorized",
                "live_orders_authorized"):
        assert report[key] is False
