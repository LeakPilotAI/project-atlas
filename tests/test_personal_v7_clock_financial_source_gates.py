"""Exact V7 independent NTP financial/source preconditions in disposable memory."""
import copy
import hashlib
from types import SimpleNamespace

import pytest

from scripts.observation_runtime.personal_v7_operator_clock import (
    NativeV7PaperOperatorClock, PROFILE,
)
from scripts.observation_runtime.personal_paper_activation import NativePersonalActivationReader
from scripts.observation_runtime import personal_source_install_authority as src
from scripts.observation_runtime import personal_installation_technical as tech
from test_personal_installation_technical import setup as setup_technical


def fake_v7_clock(monkeypatch, *, utc=1000):
    # No real network access is permitted in disposable tests.
    clock = object.__new__(NativeV7PaperOperatorClock)
    stamp = [utc]
    sample = {
        "schema": "QD_AUTO_CLOCK_V3",
        "utc": utc, "monotonic_ns": 1000,
        "uncertainty_ms": 140,
        "source_id": "ATLAS_NTP_V1:time.cloudflare.com+time.google.com",
    }
    monkeypatch.setattr(NativeV7PaperOperatorClock, "require_operational",
                        lambda self,runtime_id: self if runtime_id == "SYNTHETIC_V7" else
                        (_ for _ in ()).throw(ValueError("SYNTHETIC_WRONG_RUNTIME")))
    monkeypatch.setattr(NativeV7PaperOperatorClock, "__call__",
                        lambda self: stamp[0])
    monkeypatch.setattr(NativeV7PaperOperatorClock, "runtime_sample",
                        lambda self: copy.deepcopy(sample))
    monkeypatch.setattr(NativeV7PaperOperatorClock, "verify_runtime_sample",
                        lambda self,r: r == sample and r["uncertainty_ms"] <= 1000)
    return clock, stamp, sample


def test_v7_source_installer_requires_exact_profile_and_native_reader(monkeypatch):
    clock, stamp, sample = fake_v7_clock(monkeypatch)
    reader = object.__new__(NativePersonalActivationReader)
    monkeypatch.setattr(src, "current_sid", lambda: "SYNTHETIC_OPERATOR")
    monkeypatch.setattr(src, "validate_policy", lambda p: p)
    monkeypatch.setattr(src, "validate_activation_record", lambda r,**kw:r)
    monkeypatch.setattr(NativePersonalActivationReader, "read",
                        lambda self: {"activation_id":"SYNTHETIC_EXPLICIT"})
    args = dict(reader=reader,policy={},release_digest="a"*64,
                accounts={"QUALITY_DIPS":"b"*64},clock=clock,
                runtime_id="SYNTHETIC_V7",enrollment_digest="c"*64,
                root_id=[1,2,3],initial_image=b"synthetic-file")
    for variant in ({}, {"clock_profile": "UNREVIEWED"},
                    {"clock_profile": "WINDOWS_TIME_OPERATOR_CLOCK_V4"}):
        with pytest.raises(ValueError,match="SOURCE_INSTALL_NATIVE_ACTIVATION_AND_CLOCK_REQUIRED"):
            src.NativePersonalSourceInstallAuthority(**args,**variant)
    s=src.NativePersonalSourceInstallAuthority(**args,clock_profile=PROFILE)
    request={"schema":"PERSONAL_COORDINATION_INSTALL_V1",
             "root":[1,2,3],"enrollment":"c"*64,
             "image_digest":hashlib.sha256(b"synthetic-file").hexdigest()}
    with s.lease(request) as lease:
        assert lease.check(request)
    assert s.used
    with pytest.raises(ValueError,match="ONCE_ONLY_REFUSED"):
        with s.lease(request): pass
    assert not hasattr(s, "create_activation")
    assert not hasattr(s, "place_order")


def test_v7_source_installer_revokes_on_profile_or_clock_substitution(monkeypatch):
    clock, _stamp, _sample = fake_v7_clock(monkeypatch)
    reader=object.__new__(NativePersonalActivationReader)
    monkeypatch.setattr(src, "current_sid",lambda:"SYNTHETIC_OPERATOR")
    monkeypatch.setattr(src, "validate_policy",lambda p:p)
    monkeypatch.setattr(src, "validate_activation_record",lambda r,**kw:r)
    monkeypatch.setattr(NativePersonalActivationReader,"read",lambda self:{"activation_id":"SYNTHETIC"})
    args=dict(reader=reader,policy={},release_digest="a"*64,
              accounts={"QUALITY_DIPS":"b"*64},clock=clock,
              runtime_id="SYNTHETIC_V7",enrollment_digest="c"*64,
              root_id=[1,2,3],initial_image=b"fixed")
    for attribute,value in (("clock",object()),("clock_profile","WINDOWS_TIME_OPERATOR_CLOCK_V4")):
        s=src.NativePersonalSourceInstallAuthority(**args,clock_profile=PROFILE)
        setattr(s,attribute,value)
        request={"schema":"PERSONAL_COORDINATION_INSTALL_V1","root":[1,2,3],
                 "enrollment":"c"*64,"image_digest":hashlib.sha256(b"fixed").hexdigest()}
        with pytest.raises(ValueError,match="ONCE_ONLY_REFUSED"):
            with s.lease(request):pass
        # Failed before lease acquisition: there was no native writer attempt.
        assert not s.used


def test_v7_technical_inception_has_full_other_port_checks(monkeypatch):
    s=setup_technical(monkeypatch,initial=True)
    clock, _stamp, _sample=fake_v7_clock(monkeypatch,utc=s.s.now[0])
    s.owner.authority.clock=clock
    s.port=tech.NativePersonalTechnicalChecks(
        bootstrap=s.s.b,release=s.release,clock=clock,
        runtime_id="SYNTHETIC_V7",ownership=s.owner,
        ledger=s.ledger,files=s.files,clock_profile=PROFILE)
    request={"schema":"ATLAS_PERSONAL_INCEPTION_REQUEST_V1",
             "action":"INITIALIZE_SIMULATED_ACCOUNTS","scope":s.s.b.scope()}
    facts=s.port.inspect(request)
    assert all(facts.values()), facts
    assert s.s.b.publication.row(request["scope"]["operation_id"]) is None
    assert s.files._active is None
    assert not all(s.port.inspect({"action":"AUTO_PAPER"}).values())
    s.port.clock_profile="WINDOWS_TIME_OPERATOR_CLOCK_V4"
    assert not all(s.port.inspect(request).values())
    s.old.db.close()


def test_v7_technical_refuses_unprofiled_clock_and_foreign_owner(monkeypatch):
    s=setup_technical(monkeypatch,initial=True)
    clock,_stamp,_sample=fake_v7_clock(monkeypatch,utc=s.s.now[0])
    original_clock=s.owner.authority.clock
    kwargs=dict(bootstrap=s.s.b,release=s.release,clock=clock,
        runtime_id="SYNTHETIC_V7",ownership=s.owner,ledger=s.ledger,files=s.files)
    with pytest.raises(ValueError,match="PERSONAL_TECHNICAL_NATIVE_DEPENDENCIES_REQUIRED"):
        tech.NativePersonalTechnicalChecks(**kwargs)
    s.owner.authority.clock=clock
    with pytest.raises(ValueError,match="PERSONAL_TECHNICAL_NATIVE_DEPENDENCIES_REQUIRED"):
        tech.NativePersonalTechnicalChecks(**kwargs,clock_profile="UNREVIEWED")
    s.owner.authority.clock=original_clock
    with pytest.raises(ValueError,match="PERSONAL_TECHNICAL_NATIVE_DEPENDENCIES_REQUIRED"):
        tech.NativePersonalTechnicalChecks(**kwargs,clock_profile=PROFILE)
    s.old.db.close()


def test_v7_runtime_technical_refuses_mixed_clock_graph_without_financial_effects(monkeypatch):
    s=setup_technical(monkeypatch)
    clock,_stamp,_sample=fake_v7_clock(monkeypatch,utc=s.s.now[0])
    s.owner.authority.clock=clock
    s.current.clock=clock
    s.engine.clock=clock
    port=tech.NativePersonalTechnicalChecks(
        bootstrap=s.s.b,release=s.release,clock=clock,
        runtime_id="SYNTHETIC_V7",ownership=s.owner,
        ledger=s.ledger,current=s.current,engine=s.engine,
        clock_profile=PROFILE)
    before=s.old.db.serialize()
    facts=port.inspect({"schema":"ATLAS_PERSONAL_QD_COMPOSITION_V1"})
    # Current/reader/ownership ports still contain the previous clock identity.
    # V7 must reject the mixed graph rather than silently adopt the new clock.
    assert not all(facts.values()), facts
    assert s.old.db.serialize()==before
    s.old.db.close()
