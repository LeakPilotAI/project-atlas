"""V7 independent NTP activation admission — synthetic, never native financial effects."""
import json

import pytest

from app.services.paper_financial_replay import digest
from app.services.personal_paper_runtime import validate_policy
from scripts.observation_runtime import personal_activation_commission as commission
from scripts.observation_runtime import personal_activation_publisher as publisher
from scripts.observation_runtime import personal_v7_operator_clock as v7
from scripts.observation_runtime.atlas_independent_ntp_clock import SOURCE
from scripts.observation_runtime.atlas_v7_commissioning_ntp_probe import V7_ARTIFACT


class FakeNativeV7:
    """Only used as an exact monkeypatched class in disposable unit tests."""
    created = []
    def __init__(self, *, runtime_id):
        self.runtime_id = runtime_id
        self.revoked = False
        self.checked = 0
        self.source = SOURCE
        self.uncertainty = 140
        self.verified = True
        self.created.append(self)

    def require_operational(self, runtime_id):
        if runtime_id != self.runtime_id or self.revoked:
            raise ValueError("SYNTHETIC_WRONG_RUNTIME")
        self.checked += 1

    def runtime_sample(self):
        return {"schema": "QD_AUTO_CLOCK_V3", "utc": 1794000000,
                "source_id": self.source, "uncertainty_ms": self.uncertainty}

    def verify_runtime_sample(self, sample):
        return self.verified and sample["source_id"] == self.source

    def revoke(self):
        self.revoked = True


def publisher_inputs(monkeypatch):
    monkeypatch.setattr(v7, "NativeV7PaperOperatorClock", FakeNativeV7)
    from scripts.volume_inspector import windows_output
    monkeypatch.setattr(windows_output, "current_sid", lambda: "SYNTHETIC_OPERATOR")
    monkeypatch.setattr("backend.app.services.personal_paper_runtime.validate_activation_record",
                        lambda *a, **kw: True)
    monkeypatch.setattr(publisher, "_native_store",
                        lambda: (_ for _ in ()).throw(RuntimeError("WOULD_ENTER_NATIVE_CUSTODY")))
    return {
        "root": "D:\\AtlasCustody\\PersonalPaper\\synthetic-once-only",
        "record": {"actions": ["READ_ONLY"]},
        "policy": {},
        "operator_id": "SYNTHETIC_OPERATOR",
        "release_digest": V7_ARTIFACT,
        "accounts": {"QUALITY_DIPS": "a" * 64, "HYPERLIQUID": "b" * 64},
        "clock": FakeNativeV7(runtime_id="TEST_V7_PUBLISHER"),
        "runtime_id": "TEST_V7_PUBLISHER",
        "clock_profile": v7.PROFILE,
    }


def test_exact_v7_publisher_checks_clock_and_native_authority_before_write(monkeypatch):
    kw = publisher_inputs(monkeypatch)
    with pytest.raises(RuntimeError, match="WOULD_ENTER_NATIVE_CUSTODY"):
        publisher.publish_personal_activation(**kw)
    assert kw["clock"].checked == 1
    assert kw["clock"].revoked is False


@pytest.mark.parametrize("change,code", [
    ({"release_digest": "f" * 64}, "Selected V7 native release"),
    ({"clock_profile": "UNREVIEWED"}, "Unreviewed activation clock"),
    ({"clock_profile": "WINDOWS_TIME_OPERATOR_CLOCK_V4"}, "Operational Windows clock"),
    ({"operator_id": "WRONG_OPERATOR"}, "Windows operator identity"),
    ({"clock": object()}, "Selected V7 native release"),
])
def test_v7_publisher_refuses_unreviewed_profile_release_or_identity_before_write(
    monkeypatch, change, code
):
    kw = publisher_inputs(monkeypatch)
    kw.update(change)
    with pytest.raises(publisher.PersonalActivationPublicationRefused, match=code):
        publisher.publish_personal_activation(**kw)


@pytest.mark.parametrize("field,value", [
    ("source", "ATLAS_UNTRUSTED_NTP_SOURCE"),
    ("uncertainty", 1001),
    ("uncertainty", True),
    ("verified", False),
])
def test_v7_publisher_refuses_falsified_clock_evidence_before_native_custody(
    monkeypatch, field, value
):
    kw = publisher_inputs(monkeypatch)
    setattr(kw["clock"], field, value)
    with pytest.raises(publisher.PersonalActivationPublicationRefused):
        publisher.publish_personal_activation(**kw)


def test_v7_oversized_record_never_consumes_native_activation_root(monkeypatch):
    kw = publisher_inputs(monkeypatch)
    kw["record"]["payload"] = "a" * 65536
    with pytest.raises(publisher.PersonalActivationPublicationRefused,
                       match="exceeds native output bound"):
        publisher.publish_personal_activation(**kw)


def test_commission_requires_exact_v7_release_and_ntp_before_reading_file(monkeypatch):
    fake_path = "missing"
    args = dict(root="D:\\AtlasCustody\\PersonalPaper\\synthetic",
                record_path=fake_path,policy_path=fake_path,
                release_digest=V7_ARTIFACT,accounts_path=fake_path,
                expected_clock_source=SOURCE,runtime_id="TEST_V7",
                qd_enrollment_path=fake_path,perp_enrollment_path=fake_path,
                clock_profile=v7.PROFILE)
    for changes, message in (
        ({"release_digest": "f"*64}, "EXACT_V7_NATIVE_RELEASE_AND_NTP_SOURCE_REQUIRED"),
        ({"expected_clock_source": "time.google.com,0x8"},
         "EXACT_V7_NATIVE_RELEASE_AND_NTP_SOURCE_REQUIRED"),
        ({"clock_profile": "UNREVIEWED"}, "UNREVIEWED_ACTIVATION_CLOCK_PROFILE"),
    ):
        with pytest.raises(ValueError, match=message):
            commission.commission(**{**args, **changes})
    with pytest.raises(ValueError, match="BOTH_NATIVE_ACCOUNT_ENROLLMENTS_REQUIRED"):
        commission.commission(**{**args, "qd_enrollment_path": None})


def test_v7_commission_validated_enrollments_then_only_invokes_bound_publisher(
    monkeypatch,tmp_path
):
    from app.services import quality_dips_autonomous_enrollment as qe
    from app.services import perp_operational_contract as he
    FakeNativeV7.created = []
    source = {"account_id": "QD_DISPOSABLE", "release_digest": V7_ARTIFACT}
    other = {"account_id": "HL_DISPOSABLE", "release_digest": V7_ARTIFACT}
    accounts = {"QUALITY_DIPS": digest(source), "HYPERLIQUID": digest(other)}
    from pathlib import Path
    policy = json.loads((Path(__file__).resolve().parents[1] /
                          "docs/ATLAS_PERSONAL_PAPER_RELEASE_POLICY.json").read_text())
    record = {
        "accounts": accounts, "release_digest": V7_ARTIFACT,
        "policy_digest": digest(validate_policy(policy)),
        "origin": "LOCAL_OPERATOR", "schema": "ATLAS_PERSONAL_ACTIVATION_V1",
        "actions": ["READ_ONLY"],
    }
    paths = {}
    for name, value in (("record",record),("policy",policy),("accounts",accounts),
                        ("qd",source),("perp",other)):
        path=tmp_path / name
        path.write_text(json.dumps(value),encoding="utf-8")
        paths[name]=str(path)

    audit=[]
    monkeypatch.setattr(qe, "validate_enrollment", lambda o: audit.append("qd") or o)
    monkeypatch.setattr(he, "validate_enrollment", lambda o: audit.append("perp") or o)
    monkeypatch.setattr(commission, "verify_enrollment_native_roots",
                        lambda o:audit.append("native:"+o["account_id"]))
    # This pre-existing synthetic integration test deliberately bypasses only
    # the newly installed real HANDLE preflight; production never does.
    from contextlib import nullcontext
    from scripts.observation_runtime import personal_native_writer_lifetime as live
    class SyntheticRetention:
        def verify_still_running(self): return True
    monkeypatch.setattr(live, 'retain_live_enrollment_writers',
                        lambda *a, **kw: nullcontext(SyntheticRetention()))
    monkeypatch.setattr(commission, "NativeV7PaperOperatorClock", FakeNativeV7)
    monkeypatch.setattr(commission, "LocalWindowsClock",
                        lambda **kwargs:pytest.fail("V7 contacted Windows Time"))
    monkeypatch.setattr(commission, "current_sid",lambda:"SYNTHETIC_OPERATOR")
    def no_native_publish(**kwargs):
        audit.append("publisher")
        assert kwargs["release_digest"] == V7_ARTIFACT
        assert kwargs["clock_profile"] == v7.PROFILE
        assert type(kwargs["clock"]) is FakeNativeV7
        assert kwargs["accounts"] == accounts
        assert kwargs["operator_id"] == "SYNTHETIC_OPERATOR"
        return {"status":"DISPOSABLE_ONLY_NO_ACTIVATION"}
    monkeypatch.setattr(commission, "publish_personal_activation", no_native_publish)

    outcome=commission.commission(
        root="D:\\AtlasCustody\\PersonalPaper\\synthetic",
        record_path=paths["record"],policy_path=paths["policy"],
        release_digest=V7_ARTIFACT,accounts_path=paths["accounts"],
        expected_clock_source=SOURCE,runtime_id="TEST_V7",
        qd_enrollment_path=paths["qd"],perp_enrollment_path=paths["perp"],
        clock_profile=v7.PROFILE)
    assert outcome["status"] == "DISPOSABLE_ONLY_NO_ACTIVATION"
    assert audit==["qd","perp","native:QD_DISPOSABLE","native:HL_DISPOSABLE","publisher"]
    assert len(FakeNativeV7.created)==1 and FakeNativeV7.created[0].revoked


def test_v7_commission_cli_profile_defaults_legacy_and_rejects_foreign():
    from pathlib import Path
    code = Path(commission.__file__).read_text(encoding="utf-8-sig")
    assert "default='WINDOWS_TIME_OPERATOR_CLOCK_V4'" in code
    assert "choices=['WINDOWS_TIME_OPERATOR_CLOCK_V4', V7_NTP_PROFILE, V8_NTP_PROFILE, VERSION_SAFE_NTP_PROFILE]" in code
    assert "EXACT_V7_NATIVE_RELEASE_AND_NTP_SOURCE_REQUIRED" in code
    assert "clock.revoke()" in code
