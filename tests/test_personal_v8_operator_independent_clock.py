"""Synthetic tests plus read-only real native checks for V8 PAPER clock binding."""
import hashlib
import json
import os
from pathlib import Path

import pytest

from scripts.observation_runtime import personal_v8_operator_clock as v8
from scripts.observation_runtime.atlas_independent_ntp_clock import SOURCE


class FakeNtp:
    def __init__(self, *, runtime_id):
        self.runtime_id = runtime_id
        self.closed = False
        self.evidence = {
            "source": SOURCE, "domain": "TWO_PUBLIC_UNAUTHENTICATED_NTP_PEERS",
            "financial_authority": False, "bound_ms": 139,
        }

    def require_operational(self, rid):
        if self.closed or rid != self.runtime_id:
            raise ValueError("TEST_NTP_WRONG_OWNER")

    def sample(self):
        self.require_operational(self.runtime_id)
        return {"utc": 1800000000, "source": SOURCE}

    def runtime_sample(self):
        self.require_operational(self.runtime_id)
        return {"utc": 1800000000, "source_id": SOURCE}

    def verify(self, sample):
        return not self.closed and sample.get("source") == SOURCE

    def verify_runtime_sample(self, sample):
        return not self.closed and sample.get("source_id") == SOURCE

    def revoke(self):
        self.closed = True


def make_clock(monkeypatch):
    events = []
    monkeypatch.setattr(v8, "require_selected_v8",
                        lambda *,deep: events.append(deep) or "approved-r12-digest")
    monkeypatch.setattr(v8, "IndependentNtpClock", FakeNtp)
    c = v8.NativeV8PaperOperatorClock(runtime_id="TEST_V8_NATIVE_CLOCK")
    return c, events


def test_real_current_selected_v7_r11_refuses_v8_clock_before_ntp(monkeypatch):
    assert not (v8.ROOT / "selection/r0012.json").exists()
    from scripts.release_selection import digest
    old = json.loads((v8.ROOT / "selection/r0011.json").read_bytes())["record"]
    assert old["revision"] == 11 and digest(old) == v8.V7_R11_HEAD
    assert old["selected"]["release"] == v8.V7_APP
    assert hashlib.sha256((v8.ROOT / "support-installations" /
        v8.SUPPORT / "receipt.json").read_bytes()).hexdigest() == v8.SUPPORT_RECEIPT
    assert hashlib.sha256((Path(r"D:\Work\Project Atlas\logs\diagnostics") /
        ("qd-unselected-release-" + v8.APP + ".json")).read_bytes()).hexdigest() == v8.APP_RECEIPT
    monkeypatch.setattr(v8, "IndependentNtpClock",
                        lambda **kw: pytest.fail("must not request NTP before native V8 selection"))
    with pytest.raises(ValueError, match="V8_OPERATOR_SELECTED_NATIVE_V7_PREDECESSOR_REQUIRED"):
        v8.NativeV8PaperOperatorClock(runtime_id="real-v8-rejected-before-selection")


def test_v8_synthetic_exact_release_first_then_same_runtime_clock(monkeypatch):
    c, observations = make_clock(monkeypatch)
    assert observations == [True, False]
    assert c._selected_head == "approved-r12-digest"
    assert c.sample()["source"] == SOURCE
    assert c.verify(c.sample())
    assert c.runtime_clock().verify(c.runtime_clock().sample())
    assert c._clock.evidence["financial_authority"] is False
    assert observations.count(False) >= 5
    c.revoke()
    assert c._revoked and c._clock.closed
    with pytest.raises(ValueError, match="OWNER_OR_IDENTITY_CHANGED"):
        c.sample()


@pytest.mark.parametrize("damage", [
    "selection", "process", "runtime", "provider", "source", "uncertainty",
    "finance_claim", "revoked",
])
def test_v8_clock_fail_closed_and_original_provider_revoked(monkeypatch, damage):
    c, _ = make_clock(monkeypatch)
    original=c._clock
    if damage == "selection":
        monkeypatch.setattr(v8, "require_selected_v8", lambda *,deep: "foreign-head")
    elif damage == "process":
        monkeypatch.setattr(v8.os, "getpid", lambda: c._pid + 1)
    elif damage == "runtime":
        c._runtime_id="CHANGED_RUNTIME"
    elif damage == "provider":
        c._clock=object()
    elif damage == "source":
        c._clock.evidence["source"]="SPOOFED"
    elif damage == "uncertainty":
        c._clock.evidence["bound_ms"]=1001
    elif damage == "finance_claim":
        c._clock.evidence["financial_authority"]=True
    elif damage == "revoked":
        c.revoke()
    with pytest.raises(ValueError, match="V8_OPERATOR_"):
        c.require_operational("TEST_V8_NATIVE_CLOCK")
    assert c._revoked and original.closed


def test_v8_native_profile_source_has_no_bypass_or_financial_authorization():
    assert v8.PROFILE == "V8_INDEPENDENT_NTP_OPERATOR_CLOCK_V1"
    assert v8.APP == "c8cc4846508b29483d10a0b4c4353f8a26f1fc9c"
    assert v8.ARTIFACT == "65c4b4661ec6aef7359e9dae716a416327379f5082a5b309ccdb5a148a569c95"
    source=Path(v8.__file__).read_text(encoding="utf-8")
    assert 'len(rows) != 12' in source
    assert 'r12.get("previous") != V7_R11_HEAD' in source
    assert 'with NativeInstalledReleaseVerifier().open(spec)' in source
    assert 'support_deployment.verify_deployment(' in source
    assert "os.getpid()" in source
    assert "financial_writer" not in source
    assert "publish" not in source
    assert "place_order" not in source
