"""V7 independent dual NTP code-only installer admission; no native copy."""
import hashlib
import json
from pathlib import Path

import pytest

from scripts import install_verified_release as installer
from scripts.build_release_candidate import source_bytes
from scripts.observation_runtime import atlas_independent_ntp_clock, personal_windows_clock


ROOT = Path(__file__).resolve().parents[1]
PROPOSAL = ROOT / "docs/QD_UNSELECTED_CODE_INSTALL_PROPOSAL_V7_R1_2026-11-08.json"
REVIEW = ROOT / "docs/QD_UNSELECTED_CODE_INSTALL_PROPOSAL_V7_REVIEW_2026-11-08.json"
PIN = "de48078c9524e0b339f57b22e7d3d5e03df4e3b0952e084e3a5638581fb86ab0"
REVIEW_PIN = "fd43a4b403ec262f9b404dd1c39064abe54650b806eececf7403d32215c67a6b"
COMMIT = "af96bec0484a8e43f9965610e071a907a0d316bf"
ARCHIVE = "253798f88386efedc41453169da402c4d09ce24e567687422a7a9c26dae5b631"
INVENTORY = "e57514a84927ae7087302a111683342ef23b162208382a442dada09b9ee364f1"


def verified():
    raw = PROPOSAL.read_bytes().replace(b"\r\n", b"\n")
    assert hashlib.sha256(raw).hexdigest() == PIN
    return installer.validate_proposal(json.loads(raw))


def test_v7_exact_pinned_code_only_proposal_and_immutable_review():
    p = verified()
    assert hashlib.sha256(REVIEW.read_bytes().replace(b"\r\n", b"\n")).hexdigest() == REVIEW_PIN
    assert p["source_commit"] == COMMIT
    assert p["archive_sha256"] == ARCHIVE
    assert p["inventory_sha256"] == INVENTORY
    assert p["status"] == "PROPOSAL_NOT_PERMISSION"
    assert all(p[k] is False for k in (
        "selected", "financial_enrollment", "provider_activation", "paper_startup", "promotion"
    ))
    assert p["destination"] == "D:\\AtlasRuntime\\releases\\" + COMMIT


def test_historic_v7_adapter_pins_immutable_with_new_v8_installer_refusal():
    p = verified()
    assert set(p["adapter_source_sha256"]) == {
        "scripts/install_verified_release.py", "scripts/native_install_candidate.py",
        "scripts/native_install_plan.py",
    }
    assert p["adapter_source_sha256"]["scripts/install_verified_release.py"] == (
        "bf958e0b7983ee95c2ab52e6e376003e4b14f32606344242af7247fe936faac5"
    )
    # Source-only V8 admission changed installer bytes. Never repin V7's
    # historical proposal or reuse its old installer's authority.
    for name, pin in p["adapter_source_sha256"].items():
        actual = hashlib.sha256(source_bytes(ROOT, name, maximum_bytes=65536).replace(
            b"\r\n", b"\n")).hexdigest()
        if name == "scripts/install_verified_release.py":
            assert actual != pin
        else:
            assert actual == pin
    assert installer.INDEPENDENT_NTP_CODE_INSTALL_SOURCE_COMMIT == COMMIT


def test_absent_explicit_installer_permission_refused_without_time_or_copy():
    with pytest.raises(SystemExit, match="separately reviewed exact installation"):
        installer.main(["--proposal", str(PROPOSAL), "--proposal-sha256", PIN])


def test_wrong_hash_refused_before_ntp_or_install(monkeypatch):
    monkeypatch.setattr(atlas_independent_ntp_clock, "IndependentNtpClock",
                        lambda **kw: pytest.fail("network before source hash"))
    monkeypatch.setattr(installer, "install_unselected_release",
                        lambda **kw: pytest.fail("copy before source hash"))
    with pytest.raises(ValueError, match="APPROVED_INSTALL_PROPOSAL_HASH_MISMATCH"):
        installer.main(["--execute-approved-unselected", "--proposal", str(PROPOSAL),
                        "--proposal-sha256", "0"*64])


def test_historic_v7_cli_refuses_changed_adapter_before_network_or_install(monkeypatch):
    monkeypatch.setattr(atlas_independent_ntp_clock, "IndependentNtpClock",
                        lambda **kw: pytest.fail("V7 old installer authority reused"))
    monkeypatch.setattr(personal_windows_clock, "LocalWindowsClock",
                        lambda **kw: pytest.fail("V7 fallback to Windows Time"))
    monkeypatch.setattr(installer, "install_unselected_release",
                        lambda **kw: pytest.fail("V7 historical proposal copied again"))
    with pytest.raises(ValueError, match="INSTALL_ADAPTER_SOURCE_CHANGED"):
        installer.main([
            "--execute-approved-unselected", "--proposal", str(PROPOSAL),
            "--proposal-sha256", PIN,
        ])


def test_lookalike_filename_never_admitted_even_with_real_proposal_bytes(monkeypatch, tmp_path):
    monkeypatch.setattr(atlas_independent_ntp_clock, "IndependentNtpClock",
                        lambda **kw: pytest.fail("NTP attempted from unapproved filename"))
    lookalike = tmp_path / "QD_UNSELECTED_CODE_INSTALL_PROPOSAL_V7_R1_2026-11-08.json"
    lookalike.write_bytes(PROPOSAL.read_bytes())
    with pytest.raises(ValueError, match="EXACT_INSTALL_PROPOSAL_REQUIRED"):
        installer.main(["--execute-approved-unselected", "--proposal", str(lookalike),
                        "--proposal-sha256", PIN])
