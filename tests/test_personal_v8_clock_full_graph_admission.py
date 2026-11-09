"""V8 clock profile is opt-in, exact, and never native financial authority."""
import pytest

from scripts.observation_runtime import personal_v8_operator_clock as v8
from scripts.observation_runtime import personal_activation_commission as commission
from scripts.observation_runtime import personal_activation_publisher as publisher
from scripts.observation_runtime import personal_source_install_authority as source
from scripts.observation_runtime import personal_installation_technical as technical
from scripts.observation_runtime import personal_local_authority as authority
from scripts.observation_runtime.personal_paper_activation import (
    NativePersonalActivationReader,
)
from test_personal_v7_activation_publisher_and_commission import (
    publisher_inputs, FakeNativeV7,
)
from test_personal_v7_installed_composition_clock import synthetic_call
from test_personal_v7_clock_financial_source_gates import fake_v7_clock


def test_v8_publisher_reaches_only_intercepted_native_boundary_with_exact_clock(monkeypatch):
    kw=publisher_inputs(monkeypatch)
    monkeypatch.setattr(v8, "NativeV8PaperOperatorClock", FakeNativeV7)
    kw["release_digest"] = v8.ARTIFACT
    kw["clock_profile"] = v8.PROFILE
    with pytest.raises(RuntimeError,match="WOULD_ENTER_NATIVE_CUSTODY"):
        publisher.publish_personal_activation(**kw)
    assert kw["clock"].checked == 1


@pytest.mark.parametrize("overrides", [
    {"release_digest": "f"*64},
    {"clock_profile": "V8_UNREVIEWED_OVERRIDE"},
    {"clock_profile": "V7_INDEPENDENT_NTP_OPERATOR_CLOCK_V1"},
    {"clock": object()},
])
def test_v8_publisher_refuses_unreviewed_identity_or_clock_before_native(monkeypatch, overrides):
    kw=publisher_inputs(monkeypatch)
    kw.update({"release_digest": v8.ARTIFACT, "clock_profile": v8.PROFILE})
    kw.update(overrides)
    with pytest.raises(publisher.PersonalActivationPublicationRefused):
        publisher.publish_personal_activation(**kw)


def test_v8_commission_rejects_foreign_release_or_ntp_source_before_file_read():
    kw=dict(root=r"D:\AtlasCustody\PersonalPaper\synthetic-v8",
            record_path="nonexistent",policy_path="nonexistent",accounts_path="nonexistent",
            release_digest=v8.ARTIFACT,
            expected_clock_source="ATLAS_NTP_V1:time.cloudflare.com+time.google.com",
            runtime_id="SYNTHETIC_V8_COMMISSION",
            qd_enrollment_path="nonexistent",perp_enrollment_path="nonexistent",
            clock_profile=v8.PROFILE)
    with pytest.raises(ValueError,match="EXACT_V8_NATIVE_RELEASE_AND_NTP_SOURCE_REQUIRED"):
        commission.commission(**{**kw,"release_digest":"f"*64})
    with pytest.raises(ValueError,match="EXACT_V8_NATIVE_RELEASE_AND_NTP_SOURCE_REQUIRED"):
        commission.commission(**{**kw,"expected_clock_source":"WINDOWS_TIME"})
    with pytest.raises(ValueError,match="BOTH_NATIVE_ACCOUNT_ENROLLMENTS_REQUIRED"):
        commission.commission(**{**kw,"qd_enrollment_path":None})
    with pytest.raises(FileNotFoundError):
        commission.commission(**kw)


def test_v8_installed_qd_composition_optin_only_and_same_legacy_custody(monkeypatch):
    observed=[]
    monkeypatch.setattr(v8.NativeV8PaperOperatorClock, "require_operational",
                        lambda self, rid: observed.append(rid))
    c=object.__new__(v8.NativeV8PaperOperatorClock)
    with pytest.raises(ValueError,match="PERSONAL_INSTALLED_CURRENT_CUSTODY_BINDING"):
        synthetic_call(monkeypatch,c,v8.PROFILE)
    assert observed == ["SYNTHETIC_V7_COMPOSITION"]
    with pytest.raises(ValueError,match="INSTALLED_NATIVE_DEPENDENCIES_REQUIRED"):
        synthetic_call(monkeypatch,c,"WINDOWS_TIME_OPERATOR_CLOCK_V4")
    with pytest.raises(ValueError,match="INSTALLED_NATIVE_DEPENDENCIES_REQUIRED"):
        synthetic_call(monkeypatch,c,"V7_INDEPENDENT_NTP_OPERATOR_CLOCK_V1")


def test_v8_source_installer_exact_profile_preserves_reader_requirement(monkeypatch):
    c,_,_=fake_v7_clock(monkeypatch)
    # Make only the V8 class's temporal methods synthetic; native operations
    # remain unavailable unless their original reader/account checks pass.
    monkeypatch.setattr(v8.NativeV8PaperOperatorClock,"require_operational",
                        lambda self,rid: None)
    v8clock=object.__new__(v8.NativeV8PaperOperatorClock)
    args=dict(reader=object.__new__(NativePersonalActivationReader),
              policy={},release_digest=v8.ARTIFACT,
              accounts={"QUALITY_DIPS":"a"*64}, clock=v8clock,
              runtime_id="SYNTHETIC_V8_COMMISSION",enrollment_digest="f"*64,
              root_id=[1,2,3],initial_image=b"test-no-financial-write")
    monkeypatch.setattr(source,"validate_policy",lambda p:p)
    monkeypatch.setattr(source,"current_sid",lambda:"SYNTHETIC")
    obj=source.NativePersonalSourceInstallAuthority(**args,clock_profile=v8.PROFILE)
    assert obj.clock is v8clock and obj.clock_profile == v8.PROFILE
    assert obj.used is False
    with pytest.raises(ValueError,match="SOURCE_INSTALL_NATIVE_ACTIVATION_AND_CLOCK_REQUIRED"):
        source.NativePersonalSourceInstallAuthority(**args)
    with pytest.raises(ValueError,match="SOURCE_INSTALL_NATIVE_ACTIVATION_AND_CLOCK_REQUIRED"):
        source.NativePersonalSourceInstallAuthority(**args,clock_profile="V7_INDEPENDENT_NTP_OPERATOR_CLOCK_V1")
    assert not hasattr(obj,"financial_writer")


def test_operator_and_technical_v8_exact_clock_profiles_in_source():
    from pathlib import Path
    for module,identifier in (
        (authority,"NativePersonalOperatorAuthority"),
        (technical,"NativePersonalTechnicalChecks"),
        (source,"NativePersonalSourceInstallAuthority"),
    ):
        contents=Path(module.__file__).read_text(encoding="utf-8-sig")
        assert identifier in contents
        assert "NativeV8PaperOperatorClock" in contents
        assert "V8_NTP_PROFILE" in contents
        assert "NativeV7PaperOperatorClock" in contents
        assert "LocalWindowsClock" in contents
