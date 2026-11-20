"""Real selected-writer lease boundary invariants, no filesystem financial writes.

A trusted same-process independent UTC may advance exactly 1 second between
reads. Never accept backward, >1-second drift, stale leases, foreign tokens,
changed activation or weakened original mutex / lease owner constraints.
"""
from contextlib import contextmanager
from threading import RLock
from types import SimpleNamespace
import pytest

from scripts.observation_runtime.personal_writer_ownership import (
    NativePersonalWriterOwnership,
)


def fake_owner(samples):
    supplied=list(samples)
    counts={"activation":0,"wait":0,"release":0,"checks":0}
    def clock():
        if not supplied:
            raise ValueError("SYNTHETIC_CLOCK_UNEXPECTED_EXTRA_READ")
        return supplied.pop(0)
    def activation(action):
        assert action=="READ_ONLY"
        counts["activation"]+=1
        return {"status":"EXACT_NATIVE_SIMULATED_APPROVAL"}
    def owned_verify():
        counts["checks"]+=1
        return True
    def context(req):
        return "READ_ONLY",req
    def wait(*args):
        counts["wait"]+=1
        return 0
    def release(*args):
        counts["release"]+=1
        return 1
    owner=object.__new__(NativePersonalWriterOwnership)
    owner._verify=owned_verify
    owner._context=context
    owner.authority=SimpleNamespace(clock=clock,activation=activation)
    owner.coordinator=SimpleNamespace(wait=wait,release=release)
    owner.mutex=object()
    owner.native=SimpleNamespace(w=SimpleNamespace(check=lambda value:True))
    owner.lock=RLock()
    owner.active=0
    owner.poisoned=False
    return owner,counts,supplied


@pytest.mark.parametrize(
    "entry,stamp,inner_verification,exit_stamp,exit_verification",
    [
        (1000,1000,1000,1000,1000),
        (1001,1001,1002,1002,1003),
        (1000,1001,1002,1003,1004),
    ],
)
def test_genuine_one_second_utc_rollover_does_not_refuse_original_owner(
        entry,stamp,inner_verification,exit_stamp,exit_verification):
    owner,counts,remain=fake_owner([
        entry,inner_verification,exit_stamp,exit_verification])
    request={"schema":"PERSONAL_NATIVE_READ_LEASE_V1",
             "account_id":"DUMMY_NOT_FINANCIAL_ACCOUNT"}
    with owner._lease(request,1000) as lease:
        assert lease.check(lease.snapshot,stamp) is True
    assert remain==[]
    assert counts["wait"]==1
    assert counts["release"]==1
    assert counts["activation"]==3
    assert owner.active==0


@pytest.mark.parametrize("invalid", [998,999,1002,1003,True,"1000",None])
def test_trusted_clock_rejects_backwards_stale_or_wrong_type_at_entry(invalid):
    owner,counts,_=fake_owner([invalid])
    with pytest.raises(ValueError,match="PERSONAL_WRITER_CLOCK"):
        with owner._lease({"schema":"DUMMY"},1000):
            raise AssertionError("NEVER_REACH_EFFECΤ")
    assert counts["wait"]==0
    assert counts["release"]==0
    assert owner.active==0


@pytest.mark.parametrize(
    "candidate_stamp,clock_inside",
    [(999,1000),(1000,999),(1000,1002),(1031,1031),(True,1000)],
)
def test_writer_lease_refuses_stale_rollback_and_expired_inner_stamps(
        candidate_stamp,clock_inside):
    owner,counts,_=fake_owner([1000,clock_inside,1000,1000])
    with owner._lease({"schema":"DUMMY"},1000) as lease:
        assert lease.check(lease.snapshot,candidate_stamp) is False
    assert counts["release"]==1
    assert owner.active==0


def test_writer_lease_rejects_clock_jump_during_final_activation_recheck():
    owner,counts,_=fake_owner([1000,1000,1000,1002])
    with pytest.raises(ValueError,match="PERSONAL_WRITER_LEASE_CHANGED"):
        with owner._lease({"schema":"DUMMY"},1000) as lease:
            assert lease.check(lease.snapshot,1000) is True
    assert counts["release"]==1
    assert owner.active==0


def test_writer_lease_refuses_modified_candidate_even_with_good_clock():
    owner,counts,_=fake_owner([1000,1000,1000,1000])
    with owner._lease({"schema":"DUMMY"},1000) as lease:
        assert lease.check({"schema":"FORGED"},1000) is False
    assert counts["release"]==1
    assert owner.active==0


def test_writer_lease_refuses_changed_activation_during_original_lease():
    owner,counts,_=fake_owner([1000,1000,1000,1000])
    def changed(action):
        counts["activation"]+=1
        return {"status":"CHANGED"}
    with pytest.raises(ValueError,match="PERSONAL_WRITER_LEASE_CHANGED"):
        with owner._lease({"schema":"DUMMY"},1000) as lease:
            owner.authority.activation=changed
            assert lease.check(lease.snapshot,1000) is False
    assert counts["release"]==1
