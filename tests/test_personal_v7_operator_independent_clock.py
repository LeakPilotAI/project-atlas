"""V7 operator UTC port: strict native selected application, no financial rights.

All synthetic examples are disposable monkeypatched in-process test doubles.
The actual source port always creates its own independent two-peer NTP clock.
"""
import copy
import os

import pytest

from scripts.observation_runtime import personal_v7_operator_clock as v7
from scripts.observation_runtime import personal_local_authority as auth
from scripts.observation_runtime.atlas_independent_ntp_clock import SOURCE
from scripts.observation_runtime.personal_paper_activation import NativePersonalActivationReader
from test_personal_local_authority_memory import authority as old_authority


class FakeTwoPeer:
    def __init__(self, *, runtime_id):
        self.runtime_id = runtime_id
        self.verified = 0
        self.revoked = False
        self.utc = 1000
        self.evidence = {
            "source": SOURCE,
            "domain": "TWO_PUBLIC_UNAUTHENTICATED_NTP_PEERS",
            "financial_authority": False,
            "bound_ms": 150,
        }

    def require_operational(self, runtime_id):
        if self.revoked or self.runtime_id != runtime_id:
            raise ValueError("TEST_REAL_CLOCK_REVOKED")
        self.verified += 1
        return self

    def sample(self):
        self.require_operational(self.runtime_id)
        return {
            "schema": "QD_AUTO_NATIVE_CLOCK_V4", "utc": self.utc,
            "monotonic_ns": self.verified, "uncertainty_ms": 150, "source": SOURCE}

    def __call__(self):
        return self.sample()["utc"]

    def verify(self, sample):
        return not self.revoked and sample.get("source") == SOURCE

    def runtime_sample(self):
        native = self.sample()
        return {
            "schema": "QD_AUTO_CLOCK_V3",
            "utc": native["utc"], "monotonic_ns": native["monotonic_ns"],
            "uncertainty_ms": native["uncertainty_ms"], "source_id": SOURCE}

    def verify_runtime_sample(self, sample):
        return not self.revoked and sample.get("source_id") == SOURCE

    def revoke(self):
        self.revoked = True


def prepared(monkeypatch):
    observations = []
    monkeypatch.setattr(v7, "verify_selected_v7",
                        lambda: (observations.append("native_full_readback"), True)[1])
    monkeypatch.setattr(v7, "_require_current_v7_selected",
                        lambda: observations.append("native_selector_current"))
    monkeypatch.setattr(v7, "IndependentNtpClock", FakeTwoPeer)
    c = v7.NativeV7PaperOperatorClock(runtime_id="TEST_V7_RUNTIME")
    return c, observations


def test_clock_creates_its_own_two_peer_source_after_full_native_readback(monkeypatch):
    c, logs = prepared(monkeypatch)
    assert logs[0] == "native_full_readback"
    assert logs[1] == "native_selector_current"
    assert c._clock.runtime_id == "TEST_V7_RUNTIME"
    assert c._clock.verified >= 1
    assert c() == 1000
    native = c.sample()
    runtime = c.runtime_sample()
    assert c.verify(native) and c.verify_runtime_sample(runtime)
    assert c.runtime_clock().verify(c.runtime_clock().sample())
    assert logs.count("native_selector_current") >= 5
    assert c._clock.evidence["financial_authority"] is False
    c.revoke()
    assert c._clock.revoked
    with pytest.raises(ValueError, match="OWNER_OR_RUNTIME_CHANGED"):
        c.sample()


def test_current_native_selector_failure_revokes_without_fallback(monkeypatch):
    c, _ = prepared(monkeypatch)
    def changed():
        raise ValueError("V7_OPERATOR_CLOCK_NATIVE_SELECTOR_CHANGED")
    monkeypatch.setattr(v7, "_require_current_v7_selected", changed)
    with pytest.raises(ValueError, match="SELECTED_SOURCE_REVOKED"):
        c.sample()
    assert c._revoked and c._clock.revoked
    with pytest.raises(ValueError, match="OWNER_OR_RUNTIME_CHANGED"):
        c.require_operational("TEST_V7_RUNTIME")


@pytest.mark.parametrize("damage", ["wrong_runtime", "process", "foreign_clock",
                                   "financial_flag", "source", "bound", "revoked"])
def test_clock_owner_source_and_status_fail_closed(monkeypatch, damage):
    c, _ = prepared(monkeypatch)
    if damage == "wrong_runtime":
        with pytest.raises(ValueError, match="OWNER_OR_RUNTIME_CHANGED"):
            c.require_operational("FOREIGN")
    elif damage == "process":
        actual_pid = os.getpid()
        monkeypatch.setattr(v7.os, "getpid", lambda: actual_pid + 100)
        with pytest.raises(ValueError, match="OWNER_OR_RUNTIME_CHANGED"):
            c.sample()
    elif damage == "foreign_clock":
        c._clock = object()
        with pytest.raises(ValueError, match="OWNER_OR_RUNTIME_CHANGED"):
            c.sample()
    elif damage == "financial_flag":
        c._clock.evidence["financial_authority"] = True
        with pytest.raises(ValueError, match="SELECTED_SOURCE_REVOKED"):
            c.sample()
    elif damage == "source":
        c._clock.evidence["source"] = "UNVERIFIED"
        with pytest.raises(ValueError, match="SELECTED_SOURCE_REVOKED"):
            c.sample()
    elif damage == "bound":
        c._clock.evidence["bound_ms"] = 1001
        with pytest.raises(ValueError, match="SELECTED_SOURCE_REVOKED"):
            c.sample()
    elif damage == "revoked":
        c.revoke()
        with pytest.raises(ValueError, match="OWNER_OR_RUNTIME_CHANGED"):
            c.sample()
    assert c._revoked


def test_real_operator_authority_rejects_unreviewed_ntp_or_unscoped_clock(monkeypatch):
    s = old_authority(monkeypatch)
    assert s.port.verify(s.request)
    c, _ = prepared(monkeypatch)
    with pytest.raises(ValueError, match="DEPENDENCIES_REQUIRED"):
        auth.NativePersonalOperatorAuthority(policy=s.i.p, enrollment=s.f.e,
            reader=s.reader, clock=c, runtime_id="TEST_V7_RUNTIME")
    with pytest.raises(ValueError, match="DEPENDENCIES_REQUIRED"):
        auth.NativePersonalOperatorAuthority(policy=s.i.p, enrollment=s.f.e,
            reader=s.reader, clock=c._clock, runtime_id="TEST_V7_RUNTIME",
            clock_profile=v7.PROFILE)
    with pytest.raises(ValueError, match="DEPENDENCIES_REQUIRED"):
        auth.NativePersonalOperatorAuthority(policy=s.i.p, enrollment=s.f.e,
            reader=s.reader, clock=c, runtime_id="TEST_V7_RUNTIME",
            clock_profile="FINANCIAL_OVERRIDE")
    c.revoke()


def test_v7_operator_clock_reaches_existing_activation_checks_not_writer(monkeypatch):
    s = old_authority(monkeypatch)
    c, _ = prepared(monkeypatch)
    port = auth.NativePersonalOperatorAuthority(
        policy=s.i.p, enrollment=s.f.e, reader=s.reader, clock=c,
        runtime_id="TEST_V7_RUNTIME", clock_profile=v7.PROFILE)
    # Same existing native activation/record/session contract is still in force.
    assert port.verify(s.request)
    c._clock.utc = 1061
    with pytest.raises(ValueError):
        port.verify(s.request)
    assert not hasattr(port, "financial_writer")
    assert not hasattr(port, "inception")
    c.revoke()


def test_v7_operator_clock_profile_mutation_revocation(monkeypatch):
    s = old_authority(monkeypatch)
    c, _ = prepared(monkeypatch)
    port = auth.NativePersonalOperatorAuthority(
        policy=s.i.p, enrollment=s.f.e, reader=s.reader, clock=c,
        runtime_id="TEST_V7_RUNTIME", clock_profile=v7.PROFILE)
    port.clock_profile = "WINDOWS_TIME_OPERATOR_CLOCK_V4"
    with pytest.raises(ValueError, match="REVOKED_OR_CHANGED"):
        port.verify(s.request)
    c.revoke()


def test_v7_selector_only_is_not_financial_acceptance(monkeypatch):
    c, _ = prepared(monkeypatch)
    assert c._clock.evidence["financial_authority"] is False
    assert c.__class__ is v7.NativeV7PaperOperatorClock
    assert v7.PROFILE == "V7_INDEPENDENT_NTP_OPERATOR_CLOCK_V1"
    with pytest.raises(ValueError, match="DEPENDENCIES_REQUIRED"):
        auth.NativePersonalOperatorAuthority(clock=c, clock_profile=v7.PROFILE,
                                             runtime_id="TEST_V7_RUNTIME")
    c.revoke()


def test_false_installed_native_readback_refuses_before_network(monkeypatch):
    monkeypatch.setattr(v7, "verify_selected_v7", lambda: False)
    monkeypatch.setattr(v7, "IndependentNtpClock",
                        lambda **kwargs: pytest.fail("no two-peer clock without native binding"))
    with pytest.raises(ValueError, match="NATIVE_RELEASE_READBACK_REQUIRED"):
        v7.NativeV7PaperOperatorClock(runtime_id="TEST_V7_RUNTIME")
