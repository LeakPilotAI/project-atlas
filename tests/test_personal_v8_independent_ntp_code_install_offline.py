"""V8 exact independent-NTP code-only installer admission; no native effects.

The verified V8 candidate is an immutable source archive from commit c8cc4846.
This review adapter has NO V8 financial selection/clock-authority handoff.
"""
import hashlib
import json
from pathlib import Path

import pytest

from scripts import install_verified_release as installer
from scripts.build_release_candidate import source_bytes
from scripts.observation_runtime import (
    atlas_independent_ntp_clock,
    personal_windows_clock,
)

ROOT = Path(__file__).resolve().parents[1]
V8 = "c8cc4846508b29483d10a0b4c4353f8a26f1fc9c"
ARCHIVE = "d09717b36eaf9f484c4e7fa9dc5193aa6a1a147e8c7df5c0d0859bcee9f02a54"
INVENTORY = "0b97513bfb318d3c656deef4061e9fe8de85af870cf7b87fcf77e6d894c47c6e"
DEPENDENCY = "93e52e897fd2f2f3cc4b17bd3e804e8c598a1a3a8938c2b5c47d386890310c91"
APPROVED_PROPOSAL_FILENAME = "QD_UNSELECTED_CODE_INSTALL_PROPOSAL_V8_R1_2026-11-08.json"
PROPOSAL = ROOT / "docs" / APPROVED_PROPOSAL_FILENAME
PROPOSAL_PIN = "6c0cc73f024dcf3343e36810eb78a2904e30d7e11c969166d49140fd6c269533"
REVIEW = ROOT / "docs/QD_UNSELECTED_CODE_INSTALL_PROPOSAL_V8_REVIEW_2026-11-08.json"
V7 = "af96bec0484a8e43f9965610e071a907a0d316bf"


def reviewed():
    raw = PROPOSAL.read_bytes().replace(b"\r\n", b"\n")
    assert hashlib.sha256(raw).hexdigest() == PROPOSAL_PIN
    proposal = installer.validate_proposal(json.loads(raw))
    assert proposal["source_commit"] == V8
    assert proposal["archive_sha256"] == ARCHIVE
    assert proposal["inventory_sha256"] == INVENTORY
    assert proposal["dependency_sha256"] == DEPENDENCY
    return proposal


def test_v8_review_only_source_and_exact_install_r1_pins():
    assert hashlib.sha256(REVIEW.read_bytes().replace(b"\r\n", b"\n")).hexdigest() == (
        "b47ad718d3ad793d22517950697c8d78e8bf92c8ff03e7b5fdb1a9db513f7c61"
    )
    p = reviewed()
    assert p["destination"] == "D:\\AtlasRuntime\\releases\\" + V8
    assert p["status"] == "PROPOSAL_NOT_PERMISSION"
    assert all(p[name] is False for name in (
        "selected", "financial_enrollment", "provider_activation", "paper_startup", "promotion"
    ))
    assert p["adapter_source_sha256"]["scripts/install_verified_release.py"] == (
        "39ada814be1448789d255476f202ea83b90175deed4d33e574e881c61bf34ed0"
    )
    for name, expected in p["adapter_source_sha256"].items():
        assert hashlib.sha256(
            source_bytes(ROOT, name, maximum_bytes=65536).replace(b"\r\n", b"\n")
        ).hexdigest() == expected
    assert installer.INDEPENDENT_NTP_CODE_INSTALL_V8_SOURCE_COMMIT == V8
    assert installer.INDEPENDENT_NTP_CODE_INSTALL_V8_ARCHIVE == ARCHIVE
    assert installer.INDEPENDENT_NTP_CODE_INSTALL_V8_INVENTORY == INVENTORY
    assert installer.INDEPENDENT_NTP_CODE_INSTALL_SOURCE_COMMIT == V7


def test_v8_requires_explicit_installer_action_before_network():
    with pytest.raises(SystemExit, match="separately reviewed exact installation"):
        installer.main(["--proposal", str(PROPOSAL), "--proposal-sha256", PROPOSAL_PIN])


def test_v8_missing_or_wrong_proposal_pin_fails_before_any_native_effect(monkeypatch):
    monkeypatch.setattr(atlas_independent_ntp_clock, "IndependentNtpClock",
                        lambda **kwargs: pytest.fail("NTP before proposal hash"))
    monkeypatch.setattr(installer, "install_unselected_release",
                        lambda **kwargs: pytest.fail("native copy before proposal hash"))
    with pytest.raises(ValueError, match="APPROVED_INSTALL_PROPOSAL_HASH_MISMATCH"):
        installer.main(["--execute-approved-unselected", "--proposal", str(PROPOSAL),
                        "--proposal-sha256", "0" * 64])


def test_v8_source_only_cli_opens_only_exact_reviewed_two_peer_NTP(monkeypatch):
    events = []

    class FakeNtp:
        def __init__(self, *, runtime_id):
            events.append(("clock", runtime_id))

        def revoke(self):
            events.append(("revoke", None))

    monkeypatch.setattr(atlas_independent_ntp_clock, "IndependentNtpClock", FakeNtp)
    monkeypatch.setattr(personal_windows_clock, "LocalWindowsClock",
                        lambda **kwargs: pytest.fail("Windows time V8 source"))
    def inert_native(**kwargs):
        events.append(("native_call_intercepted", kwargs))
        return {"status": "SOURCE_TEST_NO_NATIVE_WRITE"}
    monkeypatch.setattr(installer, "install_unselected_release", inert_native)
    assert installer.main([
        "--execute-approved-unselected", "--proposal", str(PROPOSAL),
        "--proposal-sha256", PROPOSAL_PIN,
    ]) == {"status": "SOURCE_TEST_NO_NATIVE_WRITE"}
    assert [event[0] for event in events] == [
        "clock", "native_call_intercepted", "revoke"
    ]
    assert events[0][1] == "qd-unselected-code-install-" + V8
    arguments = events[1][1]
    assert arguments["source_commit"] == V8
    assert arguments["approved_execution"] is True
    assert arguments["archive_sha256"] == ARCHIVE
    assert arguments["inventory_digest"] == INVENTORY
    assert arguments["dependency_digest"] == DEPENDENCY
    assert arguments["clock_profile"] == installer.INDEPENDENT_NTP_CODE_ONLY_PROFILE


def test_v8_lookalike_proposal_file_refused_before_network(monkeypatch, tmp_path):
    monkeypatch.setattr(atlas_independent_ntp_clock, "IndependentNtpClock",
                        lambda **kwargs: pytest.fail("NTP from foreign proposal"))
    monkeypatch.setattr(installer, "install_unselected_release",
                        lambda **kwargs: pytest.fail("copy from foreign proposal"))
    other = tmp_path / APPROVED_PROPOSAL_FILENAME
    other.write_bytes(PROPOSAL.read_bytes())
    with pytest.raises(ValueError, match="EXACT_INSTALL_PROPOSAL_REQUIRED"):
        installer.main(["--execute-approved-unselected", "--proposal", str(other),
                        "--proposal-sha256", PROPOSAL_PIN])


@pytest.mark.parametrize("changed", ["archive_sha256", "inventory_digest", "dependency_digest"])
def test_v8_native_admission_requires_exact_all_source_pins_before_plan(monkeypatch, changed):
    class FakeNtp:
        pass
    monkeypatch.setattr(atlas_independent_ntp_clock, "IndependentNtpClock", FakeNtp)
    monkeypatch.setattr(installer, "prepare_install_inputs",
                        lambda **kwargs: pytest.fail("source plan reached from forged pins"))
    kwargs = {"approved_execution": True, "clock_profile": installer.INDEPENDENT_NTP_CODE_ONLY_PROFILE,
              "source_commit": V8, "archive_sha256": ARCHIVE, "inventory_digest": INVENTORY,
              "dependency_digest": DEPENDENCY, "clock": FakeNtp()}
    kwargs[changed] = "f" * 64
    with pytest.raises(ValueError, match="EXACT_V8_NATIVE_CODE_INSTALL_SOURCE_PIN_REQUIRED"):
        installer.install_unselected_release(**kwargs)


def test_v8_native_admission_requires_exact_clock_class(monkeypatch):
    monkeypatch.setattr(installer, "prepare_install_inputs",
                        lambda **kwargs: pytest.fail("native plan with foreign clock"))
    with pytest.raises(ValueError, match="REVIEWED_INDEPENDENT_NTP_INSTALL_PIN_REQUIRED"):
        installer.install_unselected_release(
            approved_execution=True, clock_profile=installer.INDEPENDENT_NTP_CODE_ONLY_PROFILE,
            source_commit=V8, archive_sha256=ARCHIVE, inventory_digest=INVENTORY,
            dependency_digest=DEPENDENCY, clock=object(),
        )


def test_v8_never_automatically_selects_or_claims_financial_authority():
    text = (ROOT / "scripts/install_verified_release.py").read_text(encoding="utf-8-sig")
    assert "'selection_allowed':False" in text
    assert "'financial_authority':False" in text
    assert "'selected':False" in text
    assert "'financial_effects':False" in text
    assert "'provider_connections':False" in text
    assert "candidate_v8=" in text
    assert "if expected in (candidate_v7,candidate_v8)" in text
    assert "INDEPENDENT_NTP_CODE_INSTALL_V8_SOURCE_COMMIT" in text
    assert "type(clock) is not IndependentNtpClock" in text
