"""Exact V4 unselected code-copy proposal review only: never installs code."""

import hashlib
import json
import os
from pathlib import Path

import pytest

from scripts.build_release_candidate import source_bytes, verify_candidate
from scripts.install_verified_release import (
    installation_target,
    main,
    validate_proposal,
)
from scripts.native_install_plan import prepare_install_inputs

ROOT = Path(__file__).resolve().parents[1]
PROPOSAL = ROOT / "docs/QD_UNSELECTED_CODE_INSTALL_PROPOSAL_V4_2026-11-08.json"
EXPECTED_ARCHIVE_SHA = "3f366b14f85d6dfce990ff98ca2b573176e1a838b3054b957894b04a060f2855"
EXPECTED_COMMIT = "fc07ba532f9b88a2b6d281a4f5c60ef2b72deaed"


def load_proposal():
    return validate_proposal(json.loads(PROPOSAL.read_bytes()))


def test_v4_exact_proposal_is_not_permission_to_start_financial_runtime():
    p = load_proposal()
    assert p["source_commit"] == EXPECTED_COMMIT
    assert p["archive_sha256"] == EXPECTED_ARCHIVE_SHA
    assert p["status"] == "PROPOSAL_NOT_PERMISSION"
    assert all(p[k] is False for k in (
        "selected", "financial_enrollment", "provider_activation", "paper_startup", "promotion"))


def test_proposal_archive_and_dependency_are_independently_verifiable_without_copy():
    p = load_proposal()
    archive = Path(p["archive"])
    assert archive.is_file()
    assert hashlib.sha256(archive.read_bytes()).hexdigest() == EXPECTED_ARCHIVE_SHA
    verify_candidate(archive, expected_sha256=p["archive_sha256"])
    dep = json.loads(Path(p["dependency_receipt"]).read_bytes())
    prepared = prepare_install_inputs(
        archive=archive, archive_sha256=p["archive_sha256"],
        source_commit=p["source_commit"], inventory_digest=p["inventory_sha256"],
        dependency_receipt=dep, dependency_digest=p["dependency_sha256"], require_tracked=True,
    )
    assert len(prepared["names"]) == 10482
    # The same reviewed proposal remains testable before and after its one-time
    # create-only installation. Once installed, the guard must refuse a retry.
    destination = Path(p["destination"])
    receipt = Path(p["receipt_path"])
    journal = receipt.with_suffix(".pending.jsonl")
    if any(os.path.lexists(path) for path in (destination, receipt, journal)):
        with pytest.raises(ValueError, match="INSTALLATION_ALREADY_EXISTS_PRESERVE_NO_RETRY"):
            installation_target(p["source_commit"], p["receipt_path"])
    else:
        planned_destination, planned_receipt = installation_target(
            p["source_commit"], p["receipt_path"]
        )
        assert planned_destination == destination
        assert planned_receipt == receipt


def test_adapter_code_pins_exact_reviewed_sources():
    p = load_proposal()
    assert set(p["adapter_source_sha256"]) == {
        "scripts/install_verified_release.py",
        "scripts/native_install_candidate.py",
        "scripts/native_install_plan.py",
    }
    for name, digest in p["adapter_source_sha256"].items():
        actual = source_bytes(ROOT, name, maximum_bytes=65536).replace(b"\r\n", b"\n")
        assert hashlib.sha256(actual).hexdigest() == digest


def test_missing_separate_install_approval_refuses_before_any_mutation():
    with pytest.raises(SystemExit, match="separately reviewed exact installation invocation required"):
        main(["--proposal", str(PROPOSAL)])


def test_unsupported_or_unsafe_proposals_are_rejected_offline():
    p = load_proposal()
    p["paper_startup"] = True
    with pytest.raises(ValueError, match="UNSELECTED_CODE_SCOPE_REQUIRED"):
        validate_proposal(p)
    p = load_proposal()
    p["destination"] = "D:/AtlasPaper/QualityDips/future-financial-epoch"
    with pytest.raises(ValueError, match="EXACT_INSTALL_DESTINATION_REQUIRED"):
        validate_proposal(p)
