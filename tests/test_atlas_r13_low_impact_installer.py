"""R13 review-only code installation safety. No copying or provider access.

All low-impact process-priority, deadline and throttle cases use a fake
kernel32 and clock. Exactly one real READ-ONLY release-plan check is allowed.
"""
import copy
import json

import pytest

from scripts import atlas_r13_low_impact_installer as r13


class Kernel:
    def __init__(self, *, fail_idle=False, fail_restore=False):
        self.priority = 0x20
        self.calls = []
        self.fail_idle = fail_idle
        self.fail_restore = fail_restore

    def GetCurrentProcess(self):
        return 1337

    def GetPriorityClass(self, handle):
        assert handle == 1337
        return self.priority

    def SetPriorityClass(self, handle, priority):
        assert handle == 1337
        self.calls.append(priority)
        if (priority == r13.IDLE_PRIORITY_CLASS and self.fail_idle or
                priority == 0x20 and self.fail_restore):
            return 0
        self.priority = priority
        return 1


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


def test_no_code_copy_without_fresh_pinned_separate_approval(monkeypatch):
    monkeypatch.setattr(r13,"_copy_prepared_code",
                        lambda **_:pytest.fail("NO_COPY_OR_NATIVE_WRITE"))
    monkeypatch.setattr(r13,"prepare_readonly",
                        lambda:pytest.fail("NO_PREAPPROVAL_PLAN"))
    with pytest.raises(ValueError,match="EXPLICIT_CODE_INSTALL"):
        r13.install(execute_approved=False)
    with pytest.raises(ValueError,match="NOT_YET_GRANTED"):
        r13.install(execute_approved=True)


def test_readonly_review_file_is_not_an_install_approval():
    review = r13._read_review()
    assert all(x is False for x in review["flags"].values())
    assert review["source"]["commit"] == r13.SOURCE
    with pytest.raises(ValueError,match="NOT_YET_GRANTED"):
        r13._require_separate_consent()


def test_exact_pinned_readonly_plan_has_no_financial_or_native_effect():
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
