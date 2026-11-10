"""R15 SOURCE-ONLY frozen archive, separate from installed R14 release.

Read-only checksum/zip verification. The archived source SHA is intentionally
fixed to the pre-documentation commit and must NOT be rewritten on later
roadmap commits. No release installation, source extraction, or network.
"""
import hashlib
import json
import zipfile
from pathlib import Path

import pytest

from scripts.build_release_candidate import verify_candidate


ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "logs/diagnostics/atlas-r15-source-only-20261110-r01"
ARCHIVE = ARTIFACT / "package/atlas-source.zip"
REVIEW = ARTIFACT / "source-freeze-readonly-result.json"
SELECTION = ARTIFACT / "source-selection.json"
SOURCE = "2c79a8d846d6b33669008114732ae5896153812a"
SHA = "f6cb597a53373efee929c306ae42537e16abcbcf6e57f7bd23ee92e8570160c0"
INVENTORY = "31df928fd182f4508ff84d4342eff5dc4ce6acb5cea68adc9f20265b23a8bb82"
EXTRAS = {
    "scripts/atlas_r14_low_impact_installer.py",
    "scripts/atlas_r14_selection_proposal.py",
    "scripts/atlas_r14_selection_publisher.py",
    "scripts/observation_runtime/atlas_r14_hyperliquid_public_book_probe.py",
    "scripts/observation_runtime/atlas_r14_selected_paper_readiness.py",
    "scripts/observation_runtime/atlas_r14_two_lane_source_preflight.py",
    "scripts/observation_runtime/native_install_host_admission.py",
}
PINNED_SOURCE_BYTES = {
    "backend/app/services/unified_writer_roster.py":
        "d26f821afee33855c8543f649f40f9f2fe25529043770dce59ecb8105945f697",
    "scripts/observation_runtime/personal_version_safe_release_clock.py":
        "7357b0d537a2e4b7728b896337bfee48f8856ced5b6e2410c56c623191ea17c5",
    "scripts/observation_runtime/alpaca_iex_probe.py":
        "6d3756c6307ca2b980968791c7f45288cb2cd41acac98f63c751340b2eccf33d",
    "scripts/observation_runtime/atlas_r14_hyperliquid_public_book_probe.py":
        "51b1b0738e5fe3f7a31e9193a569da11aaad28b9a58a91e75e191c01d3bece26",
}


@pytest.fixture(scope="module")
def local_source():
    if not ARCHIVE.is_file() or not REVIEW.is_file() or not SELECTION.is_file():
        pytest.skip("Frozen R15 source-only diagnostic artifact is not mounted on this host")
    return json.loads(REVIEW.read_bytes()), json.loads(SELECTION.read_bytes())


def test_selected_source_manifest_is_exact_nonfinancial_candidate(local_source):
    review, selection = local_source
    assert review["schema"] == "ATLAS_R15_SOURCE_ONLY_FROZEN_CANDIDATE_V1"
    assert review["status"] == "ARCHIVE_SOURCE_BYTES_VERIFIED_NO_INSTALL_OR_SELECTION"
    assert review["selected_native_predecessor"] == (
        "7ff9d3dba2eabe110f843c13efac49464805de2a")
    assert review["source_commit"] == selection["source_commit"] == SOURCE
    assert review["inventory_sha256"] == selection["inventory_digest"] == INVENTORY
    assert review["archive_sha256"] == SHA
    assert review["archive_bytes"] == ARCHIVE.stat().st_size == 4_887_669
    assert review["source_files"] == len(selection["files"]) == 960
    assert review["additional_tracked_runtime_files"] == len(EXTRAS) == 7
    assert selection["schema"] == "ATLAS_SOURCE_SELECTION_V1"
    items = selection["files"]
    names = [r["path"] for r in items]
    assert names == sorted(names)
    assert len(names) == len(set(names))
    assert EXTRAS.issubset(names)
    for key in (
        "native_installation_authorized", "native_release_installed",
        "release_selection_authorized", "financial_paper_authorized",
        "provider_access_authorized", "paper_orders_authorized",
        "live_orders_authorized", "startup_authorized",
    ):
        assert review[key] is False


def test_archive_verification_and_no_activation(local_source):
    confirmed = verify_candidate(ARCHIVE, expected_sha256=SHA)
    assert confirmed == {
        "schema": "ATLAS_SOURCE_CANDIDATE_VERIFICATION_V1",
        "archive_sha256": SHA,
        "source_files": 960,
        "supplied_bytes_consistent": True,
        "source_authenticated": False,
        "installation_verified": False,
        "activation_approved": False,
    }


def test_frozen_archive_contains_critical_corrected_source_bytes(local_source):
    _, selection = local_source
    tracked = {r["path"]:r for r in selection["files"]}
    with zipfile.ZipFile(ARCHIVE) as bundle:
        for path, expected in PINNED_SOURCE_BYTES.items():
            raw = bundle.read(path)
            assert hashlib.sha256(raw).hexdigest() == expected
            assert tracked[path]["sha256"] == expected
            assert tracked[path]["bytes"] == len(raw)
        payload = json.loads(bundle.read("release-manifest.json"))
        assert payload["contract"] == "R7E46O_SOURCE_V1"
        assert payload["head"] == SOURCE
        assert payload["activation_approved"] is False
        assert set(bundle.namelist()) == (
            {r["path"] for r in payload["files"]}
            | {"release-manifest.json", "requirements-observed.txt"})


def test_modified_or_wrong_archive_hash_is_refused_before_extraction(local_source):
    with pytest.raises(ValueError, match="Archive SHA256 mismatch"):
        verify_candidate(ARCHIVE, expected_sha256="0"*64)


def test_archive_never_licenses_live_financial_runtime(local_source):
    review, _ = local_source
    assert review["verified"]["installation_verified"] is False
    assert review["verified"]["source_authenticated"] is False
    assert review["verified"]["activation_approved"] is False
    assert review["verified"]["supplied_bytes_consistent"] is True
