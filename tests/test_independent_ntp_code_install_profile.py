"""Independent-NTP code-only install profile admission: no financial or native effects."""
from pathlib import Path

import pytest

from scripts import install_verified_release as installer
from scripts.observation_runtime import personal_windows_clock, atlas_independent_ntp_clock


CODE = "a"*40


def test_independent_profile_denies_every_other_source_commit(monkeypatch):
    assert installer.INDEPENDENT_NTP_CODE_INSTALL_SOURCE_COMMIT == (
        "af96bec0484a8e43f9965610e071a907a0d316bf")

    class OfflineClock:
        def require_operational(self, runtime_id):
            pytest.fail("clock verified without reviewed frozen source")

    monkeypatch.setattr(atlas_independent_ntp_clock, "IndependentNtpClock", OfflineClock)
    monkeypatch.setattr(installer, "prepare_install_inputs",
                        lambda **kw: pytest.fail("source files prepared without reviewed pin"))
    with pytest.raises(ValueError, match="REVIEWED_INDEPENDENT_NTP_INSTALL_PIN_REQUIRED"):
        installer.install_unselected_release(
            approved_execution=True, source_commit=CODE,
            clock_profile=installer.INDEPENDENT_NTP_CODE_ONLY_PROFILE,
            clock=OfflineClock())


@pytest.mark.parametrize("profile", [None, "", "NTP", True, "FINANCIAL_NTP",
                                      "WINDOWS_TIME_CODE_INSTALL_V1-OVERRIDE"])
def test_arbitrary_clock_profiles_refuse_before_any_native_effect(monkeypatch, profile):
    monkeypatch.setattr(installer, "prepare_install_inputs",
                        lambda **kw: pytest.fail("unreviewed profile reached native source"))
    with pytest.raises(ValueError, match="UNREVIEWED_INSTALL_CLOCK_PROFILE"):
        installer.install_unselected_release(approved_execution=True, clock_profile=profile,
                                             clock=object())


def test_legacy_windows_clock_profile_remains_default_and_exact_type(monkeypatch):
    class TestLegacy:
        pass

    monkeypatch.setattr(personal_windows_clock, "LocalWindowsClock", TestLegacy)
    monkeypatch.setattr(installer, "prepare_install_inputs",
                        lambda **kw: (_ for _ in ()).throw(RuntimeError("SAFE_LEGACY_PREP_REACHED")))
    with pytest.raises(RuntimeError, match="SAFE_LEGACY_PREP_REACHED"):
        installer.install_unselected_release(
            approved_execution=True, source_commit=CODE, clock=TestLegacy())
    with pytest.raises(ValueError, match="GENUINE_INSTALL_CLOCK_REQUIRED"):
        installer.install_unselected_release(
            approved_execution=True, source_commit=CODE, clock=object())


def test_frozen_commit_and_exact_independent_authority_must_both_match(monkeypatch):
    class SyntheticNtpClock:
        pass

    monkeypatch.setattr(atlas_independent_ntp_clock, "IndependentNtpClock", SyntheticNtpClock)
    monkeypatch.setattr(installer, "INDEPENDENT_NTP_CODE_INSTALL_SOURCE_COMMIT", CODE)
    monkeypatch.setattr(installer, "prepare_install_inputs",
                        lambda **kw: (_ for _ in ()).throw(RuntimeError("PREPARATION_REACHED_ONLY")))
    with pytest.raises(ValueError, match="REVIEWED_INDEPENDENT_NTP_INSTALL_PIN_REQUIRED"):
        installer.install_unselected_release(
            approved_execution=True, source_commit="b"*40,
            clock_profile=installer.INDEPENDENT_NTP_CODE_ONLY_PROFILE,
            clock=SyntheticNtpClock())
    with pytest.raises(ValueError, match="REVIEWED_INDEPENDENT_NTP_INSTALL_PIN_REQUIRED"):
        installer.install_unselected_release(
            approved_execution=True, source_commit=CODE,
            clock_profile=installer.INDEPENDENT_NTP_CODE_ONLY_PROFILE,
            clock=object())
    with pytest.raises(RuntimeError, match="PREPARATION_REACHED_ONLY"):
        installer.install_unselected_release(
            approved_execution=True, source_commit=CODE,
            clock_profile=installer.INDEPENDENT_NTP_CODE_ONLY_PROFILE,
            clock=SyntheticNtpClock())


def test_financial_and_legacy_installer_entry_remains_unmodified():
    p = Path(installer.__file__)
    src = p.read_text(encoding="utf-8")
    assert "INDEPENDENT_NTP_CODE_INSTALL_SOURCE_COMMIT = 'af96bec0484a8e43f9965610e071a907a0d316bf'" in src
    assert "if approved_execution is not True" in src
    assert "type(clock) is not LocalWindowsClock" in src
    assert "type(clock) is not IndependentNtpClock" in src
    assert "SEPARATE_CODE_INSTALL_AUTHORIZATION_REQUIRED" in src
    assert "financial_authority':False" in src
    assert "selection_allowed':False" in src
    assert "source_commit != INDEPENDENT_NTP_CODE_INSTALL_SOURCE_COMMIT" in src
    # The command line still constructs only the legacy clock: no V7 URL,
    # no silent installer approval, no selected release modified.
    assert "clock=LocalWindowsClock(expected_source=clock_source" in src
    assert "candidate_v7=" in src
    assert "EXACT_V7_DUAL_NTP_SELECTED_SOURCE_PIN_REQUIRED" in src
    assert "clock=IndependentNtpClock(runtime_id=runtime_id)" in src


def test_missing_approval_denies_new_profile_before_probe_even_if_pinned(monkeypatch):
    monkeypatch.setattr(installer, "prepare_install_inputs",
                        lambda **kw: pytest.fail("no approval but prepared archive"))
    with pytest.raises(ValueError, match="SEPARATE_CODE_INSTALL_AUTHORIZATION_REQUIRED"):
        installer.install_unselected_release(approved_execution=False, source_commit=CODE,
            clock_profile=installer.INDEPENDENT_NTP_CODE_ONLY_PROFILE)
