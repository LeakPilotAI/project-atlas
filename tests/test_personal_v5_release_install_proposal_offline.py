"""Bounded V5 code-only installer adapter; all tests are inert, no native copy."""
import hashlib
import json
from pathlib import Path

import pytest

from scripts import install_verified_release as installer
from scripts.build_release_candidate import source_bytes
from scripts.observation_runtime import personal_windows_clock

ROOT = Path(__file__).resolve().parents[1]
PROPOSAL = ROOT / "docs/QD_UNSELECTED_CODE_INSTALL_PROPOSAL_V5_R1_2026-11-08.json"
OLD = ROOT / "docs/QD_UNSELECTED_CODE_INSTALL_PROPOSAL_V5_2026-11-08.json"
PIN = "e783bce33d6ef5a235d5ae2b07c59c38a847de9bb07d0560e2f8a602ddbd07db"
OLD_PIN = "23927a0c5928667824c3eb6b313d1f8e82cd0531b94960f36608a829cd999815"
COMMIT = "247a4f4e1d78594cdb55ef55f185ef37921bf535"
ARCHIVE = "35c5b6b623f197f085cbe40bc0ff9e0d16672d5b5c3557ad48eb47e4bc20b437"
INVENTORY = "ff8635bd4f246f49234036b8aad56d9483147bb5cbba28f20f7970aebc47985c"


def load():
    raw = PROPOSAL.read_bytes().replace(b"\r\n", b"\n")
    assert hashlib.sha256(raw).hexdigest() == PIN
    return installer.validate_proposal(json.loads(raw))


def test_v5_r1_is_nonactivating_and_original_proposal_unchanged():
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


def test_v5_r1_preserves_its_original_pinned_adapter_sources():
    """Old approval is immutable and must not silently rebind to a newer installer."""
    import subprocess

    p = load()
    assert set(p["adapter_source_sha256"]) == {
        "scripts/install_verified_release.py", "scripts/native_install_candidate.py",
        "scripts/native_install_plan.py"
    }
    for name, sha in p["adapter_source_sha256"].items():
        # 3ba3aa78 is the exact prior release-candidate checkpoint, not live
        # current code. V6 changed the CLI allowlist deliberately.
        historical = subprocess.check_output(
            ["git", "show", "3ba3aa78:" + name], cwd=ROOT
        ).replace(b"\r\n", b"\n")
        assert hashlib.sha256(historical).hexdigest() == sha
    actual = source_bytes(ROOT, "scripts/install_verified_release.py", maximum_bytes=65536)
    assert hashlib.sha256(actual.replace(b"\r\n", b"\n")).hexdigest() != p["adapter_source_sha256"]["scripts/install_verified_release.py"]


def test_v5_requires_explicit_approved_entrypoint():
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


def test_historical_v5_proposal_cannot_reuse_updated_v6_installer(monkeypatch):
    """Old proposal must refuse before any native clock or release copy."""
    monkeypatch.setattr(personal_windows_clock, "LocalWindowsClock",
                        lambda **kw: pytest.fail("old proposal reached native clock"))
    monkeypatch.setattr(installer, "install_unselected_release",
                        lambda **kw: pytest.fail("old proposal reached native copy"))
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
