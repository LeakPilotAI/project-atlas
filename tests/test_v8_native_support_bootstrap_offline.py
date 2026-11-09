"""V8 code-only support bootstrap validation; all tests remain nonfinancial."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from scripts import atlas_v8_support_bootstrap as b
from scripts import support_deployment as support
from scripts.release_selection import digest

ROOT = Path(__file__).resolve().parents[1]
PROPOSAL_HASH = "835ae4edc94bee252faf450d8466191d6a347c112d962fe04f5861a2e52b375e"
BOOTSTRAP_SHA = "a5aaa5a3a84b42296943c54831a5074b17a97f53ebc08bc696718b72f64ea6fa"
SUPPORT_SHA = "808a7994ec644f596aa7214c281c557862d10b1ad571a6632d3c0c67d426ede8"


def sha(contents):
    return hashlib.sha256(contents.replace(b"\r\n", b"\n")).hexdigest()


def args(pin=PROPOSAL_HASH):
    return ["--review-proposal", str(b.PROPOSAL), "--proposal-sha256", pin]


def test_exact_bootstrap_proposal_and_support_archive_only():
    a, proposal = b.admit_proposal(args())
    assert not a.execute_code_only
    assert sha(b.PROPOSAL.read_bytes()) == PROPOSAL_HASH
    assert sha(Path(b.__file__).read_bytes()) == BOOTSTRAP_SHA
    assert sha(b.SOURCE.read_bytes()) == SUPPORT_SHA
    assert proposal["bootstrap_sha256"] == BOOTSTRAP_SHA
    assert proposal["support_source_sha256"] == SUPPORT_SHA
    assert proposal["native_base_id"] == [4004218753, 65536, 1113770]
    assert proposal["native_parents"] == b.PARENTS
    assert proposal["selected_head"] == b.HEAD
    assert proposal["target_release"] == b.V8
    assert proposal["selected_release"] == b.V7
    assert proposal["selected"] is False
    assert proposal["allow_selection"] is False
    assert proposal["allow_install"] is True
    assert proposal["paper_startup"] is False
    assert proposal["financial_authority"] is False
    assert proposal["provider_connections"] is False
    manifest = json.loads(b.MANIFEST.read_bytes())
    assert sha(b.MANIFEST.read_bytes()) == b.MANIFEST_SHA
    assert hashlib.sha256(b.ARCHIVE.read_bytes()).hexdigest() == b.ARCHIVE_SHA
    assert support.support_clock_profile(manifest) == support.V7_NTP_CLOCK_PROFILE
    m, files = support.prepare(manifest, b.ARCHIVE, b.MANIFEST_SHA)
    assert m == manifest
    assert sha(files["scripts/support_deployment.py"]) == SUPPORT_SHA


def test_unreviewed_proposal_hash_refuses_before_installed_python_or_clock():
    with pytest.raises(ValueError, match="V8_BOOTSTRAP_PROPOSAL_HASH_MISMATCH"):
        b.admit_proposal(args("0"*64))
    with pytest.raises(SystemExit):
        b.admit_proposal(["--review-proposal", str(b.PROPOSAL),
                          "--proposal-sha256", PROPOSAL_HASH, "--select-v8"])


@pytest.mark.parametrize("key,wrong", [
    ("selected", True),
    ("allow_selection", True),
    ("paper_startup", True),
    ("financial_authority", True),
    ("provider_connections", True),
    ("native_base_id", [0, 1, 2]),
    ("selected_head", "f"*64),
    ("target_release", "f"*40),
    ("support_source_sha256", "f"*64),
    ("bootstrap_sha256", "f"*64),
    ("manifest_sha256", "f"*64),
])
def test_forged_proposal_fields_refuse_before_native_access(monkeypatch, tmp_path, key, wrong):
    fake = json.loads(b.PROPOSAL.read_bytes())
    fake[key] = wrong
    test_path = tmp_path / "proposal.json"
    raw=(json.dumps(fake, sort_keys=True, separators=(",", ":"))+"\n").encode()
    test_path.write_bytes(raw)
    monkeypatch.setattr(b, "PROPOSAL", test_path)
    with pytest.raises(ValueError, match="V8_BOOTSTRAP_EXACT_NONFINANCIAL_SCOPE_REQUIRED"):
        b.admit_proposal(["--review-proposal", str(test_path),
                          "--proposal-sha256", sha(raw)])


def test_installed_v8_python_is_required_for_native_installer():
    with pytest.raises(ValueError, match="V8_INSTALLED_ISOLATED_PYTHON_REQUIRED"):
        b.require_installed_interpreter()
    assert Path(b.APP / "python/python.exe").is_file()
    assert b.APP.name == b.V8


def test_genuine_selected_v7_history_is_untouched():
    r = json.loads((b.SELECTOR / "r0011.json").read_bytes())["record"]
    assert r["revision"] == 11
    assert r["selected"]["release"] == b.V7
    assert digest(r) == b.HEAD
    assert not (b.SELECTOR / "r0012.json").exists()


def test_v8_support_target_absent_or_native_verified_after_code_only_install():
    m = json.loads(b.MANIFEST.read_bytes())
    destination, control = Path(m["destination"]), Path(m["control"])
    if destination.exists() or control.exists():
        assert destination.is_dir() and control.is_dir()
        receipt = support.verify_deployment(
            m, expected_receipt_sha256=hashlib.sha256(
                (control / "receipt.json").read_bytes()).hexdigest())
        assert receipt["selected"] is False and receipt["financial_actions"] == 0
    else:
        assert not destination.exists() and not control.exists()
    assert m["application"]["release"] == b.V8
    assert m["runtime"]["providers"] is False
    assert m["runtime"]["financial_writers"] is False


def test_source_code_never_contains_selection_or_financial_writer_execution():
    source=Path(b.__file__).read_text(encoding="utf-8-sig")
    assert "install_operational(" in source
    assert "select_release(" not in source
    assert "ReleaseSelector(" not in source
    assert "personal_paper_inception" not in source
    assert "allow_selection" in source
    assert 'clock = IndependentNtpClock(' in source
    assert "clock.revoke()" in source
    assert "V8_SUPPORT_ALREADY_INSTALLED_OR_PARTIAL_NO_RETRY" in source
    assert 'sys.flags.isolated and sys.flags.no_site' in source


def test_actual_installed_v8_isolated_readonly_bootstrap_executes_without_native_write():
    cmd = [str(b.APP/"python/python.exe"), "-I", "-B", "-S",
           str(Path(b.__file__)), *args()]
    out = subprocess.run(cmd, cwd=ROOT, capture_output=True,
                         timeout=90, text=True)
    m = json.loads(b.MANIFEST.read_bytes())
    if Path(m["control"]).exists() or Path(m["destination"]).exists():
        assert out.returncode != 0
        assert "V8_SUPPORT_ALREADY_INSTALLED_OR_PARTIAL_NO_RETRY" in out.stderr
    else:
        assert out.returncode == 0, out.stderr
        response=json.loads(out.stdout)
        assert response == {
            "status": "V8_REVIEW_ONLY_PASS",
            "installed": False,
            "selected": False,
            "financial_authority": False,
        }
        assert not out.stderr
