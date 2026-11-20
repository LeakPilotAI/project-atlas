"""Bounded V6 code-only installer adapter; all tests are inert, no native copy."""
import hashlib
import json
from pathlib import Path

import pytest

from scripts import install_verified_release as installer
from scripts.build_release_candidate import source_bytes
from scripts.observation_runtime import personal_windows_clock

ROOT = Path(__file__).resolve().parents[1]
PROPOSAL = ROOT / "docs/QD_UNSELECTED_CODE_INSTALL_PROPOSAL_V6_R1_2026-11-08.json"
OLD = ROOT / "docs/QD_UNSELECTED_CODE_INSTALL_PROPOSAL_V6_2026-11-08.json"
PIN = "a0bfbdee3d02a41112d6dcd79d1ae499ec0e8dfff4a137441e9a09ab40dd308a"
OLD_PIN = "36584cd0085b09b6fc2e3618e0e55e271c57cd2de30d8b6364d4463b71dac547"
COMMIT = "d95b350fa585c2218614c9e5eb459c6edfc91807"
ARCHIVE = "a5bcdb78a4ab4d84839c56df8908ff86570b510be3504f711b61b381a360e99f"
INVENTORY = "1eb406f598a5154337762a660ac79c565132b7081ded5d4d73210ed4e49d35fa"


def load():
    raw = PROPOSAL.read_bytes().replace(b"\r\n", b"\n")
    assert hashlib.sha256(raw).hexdigest() == PIN
    return installer.validate_proposal(json.loads(raw))


def test_v6_r1_is_nonactivating_and_original_proposal_unchanged():
    p = load()
    assert hashlib.sha256(OLD.read_bytes().replace(b"\r\n", b"\n")).hexdigest() == OLD_PIN
    assert p["source_commit"] == COMMIT
    assert p["archive_sha256"] == ARCHIVE
    assert p["inventory_sha256"] == INVENTORY
    assert p["status"] == "PROPOSAL_NOT_PERMISSION"
    assert all(p[x] is False for x in (
        "selected", "financial_enrollment", "provider_activation", "paper_startup", "promotion"
    ))
    assert p["destination"] == "D:\\AtlasRuntime\\releases\\" + COMMIT


def test_v6_r1_historical_three_adapter_pins_preserved_and_current_changed():
    import subprocess
    p = load()
    assert set(p["adapter_source_sha256"]) == {
        "scripts/install_verified_release.py", "scripts/native_install_candidate.py",
        "scripts/native_install_plan.py",
    }
    for name, pinned_hash in p["adapter_source_sha256"].items():
        historic = subprocess.check_output(
            ["git", "show", "398d4a00:" + name], cwd=ROOT)
        assert hashlib.sha256(historic.replace(b"\r\n", b"\n")).hexdigest() == pinned_hash
    current = source_bytes(ROOT, "scripts/install_verified_release.py",
                           maximum_bytes=65536)
    assert hashlib.sha256(current.replace(b"\r\n", b"\n")).hexdigest() != (
        p["adapter_source_sha256"]["scripts/install_verified_release.py"])



def test_v6_requires_explicit_approved_entrypoint():
    with pytest.raises(SystemExit, match="separately reviewed exact installation invocation required"):
        installer.main(["--proposal", str(PROPOSAL), "--proposal-sha256", PIN])


def test_wrong_install_proposal_hash_refused_before_clock_or_copy(monkeypatch):
    monkeypatch.setattr(personal_windows_clock, "LocalWindowsClock",
                        lambda **kw: pytest.fail("clock accessed before hash admission"))
    monkeypatch.setattr(installer, "install_unselected_release",
                        lambda **kw: pytest.fail("copy invoked after bad hash"))
    with pytest.raises(ValueError, match="APPROVED_INSTALL_PROPOSAL_HASH_MISMATCH"):
        installer.main(["--execute-approved-unselected", "--proposal", str(PROPOSAL),
                        "--proposal-sha256", "0" * 64])


def test_historical_v6_cannot_silently_rebind_to_new_clock_installer(monkeypatch):
    def refuse(**kw):
        pytest.fail("historical proposal reached clock or installation")
    monkeypatch.setattr(personal_windows_clock, "LocalWindowsClock", refuse)
    monkeypatch.setattr(installer, "install_unselected_release", refuse)
    with pytest.raises(ValueError, match="INSTALL_ADAPTER_SOURCE_CHANGED"):
        installer.main(["--execute-approved-unselected", "--proposal", str(PROPOSAL),
                        "--proposal-sha256", PIN])



def test_unsupported_filename_cannot_override_allowlist(monkeypatch, tmp_path):
    def refuse(**kw):
        pytest.fail("clock or network was touched")
    monkeypatch.setattr(personal_windows_clock, "LocalWindowsClock", refuse)
    another = tmp_path / "lookalike.json"
    another.write_bytes(PROPOSAL.read_bytes())
    with pytest.raises(ValueError, match="EXACT_INSTALL_PROPOSAL_REQUIRED"):
        installer.main(["--execute-approved-unselected", "--proposal", str(another),
                        "--proposal-sha256", PIN])
