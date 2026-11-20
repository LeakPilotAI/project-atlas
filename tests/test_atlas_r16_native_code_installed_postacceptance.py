"""R16 actual native installed code and selected-revision-15 readback.

The original Windows file-handle verifier reopens installed immutable R16
without modifying code files, selector, approval or financial accounts.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from scripts import atlas_r16_code_only_installer as installer
from scripts import atlas_r16_selection_handoff as handoff
from scripts.release_selection import NativeInstalledReleaseVerifier
from scripts.observation_runtime.atlas_r16_selected_code_readback import (
    selected_code, inspect as r16_readiness,
)
from scripts.observation_runtime.personal_existing_native_resource_evidence import (
    inspect_two_lane_native_roots,
)
from scripts.volume_inspector.windows_output import current_sid

RECEIPT_SHA = "bee5534c894959f70ddcea75b9c7c419274029fedb8c275169fbd4567bf9516e"
JOURNAL_SHA = "6ee6dc4ea34605f38b3d855d6cbdb2a329f36f5034a43ee2b1ea8ca7fe1612a7"
APPROVAL_SHA = "f89112cdd8456eb5eff4fda6989229d01c91bee586a7e0d9759bd22c5c2a9613"
SOURCE_PIN = "d5b70bed8cfca240fb43e2882cb233081da78c214ef23f7648449af6833d33a6"
ARTIFACT = "48c8192aa378526a319c3d2808f35f7e4662e47e69cde4daafbd4ba4115a8bd9"
PROPOSED_HEAD = "1244c614ccc9e89e436d90df77cebb6e44a57edcb44972660940ed29ebfcd593"


@pytest.fixture(scope="module")
def installed():
    if not installer.TARGET.is_dir() or not installer.RECEIPT.is_file():
        pytest.skip("R16 create-only installed native release not present here")
    journal = installer.RECEIPT.with_suffix(".pending.jsonl")
    receipt_raw = installer.RECEIPT.read_bytes()
    journal_raw = journal.read_bytes()
    assert hashlib.sha256(receipt_raw).hexdigest() == RECEIPT_SHA
    assert hashlib.sha256(journal_raw).hexdigest() == JOURNAL_SHA
    receipt = json.loads(receipt_raw)
    return receipt, journal_raw


def test_exact_r16_original_native_receipt_and_durable_two_stage_ack(installed):
    receipt, journal = installed
    assert receipt["source_commit"] == installer.SOURCE_COMMIT
    assert receipt["release_path"] == str(installer.TARGET)
    assert receipt["archive_sha256"] == installer.ARCHIVE_SHA
    assert receipt["inventory_sha256"] == installer.INVENTORY_SHA
    assert receipt["artifact_digest"] == ARTIFACT
    assert len(receipt["files"]) == 10549
    assert len(receipt["directories"]) == 912
    assert all(receipt[k] is False for k in (
        "selected", "financial_effects", "provider_connections",
        "operational_acceptance"))
    proposal = handoff.candidate_from_receipt(
        receipt=receipt,
        receipt_bytes=installer.RECEIPT.read_bytes(),
        journal_bytes=journal,
    )
    assert proposal["revision"] == 15
    assert proposal["previous"] == handoff.SELECTED_HEAD
    assert proposal["selected"]["artifact_digest"] == ARTIFACT


def test_independent_original_windows_native_handle_verifier_for_r16(installed):
    receipt, journal = installed
    row = handoff.candidate_from_receipt(
        receipt=receipt, receipt_bytes=installer.RECEIPT.read_bytes(),
        journal_bytes=journal)
    assert handoff.selection.digest(row) == PROPOSED_HEAD
    assert selected_code()["selected_native_head"] == PROPOSED_HEAD
    # The real installed Windows native handles, not a synthetic receipt,
    # must still match the selected release's exact file identities.
    with NativeInstalledReleaseVerifier().open(row["selected"]) as observed:
        assert observed["source_commit"] == installer.SOURCE_COMMIT
        assert observed["artifact_digest"] == ARTIFACT
        assert len(observed["files"]) == 10549
        assert len(observed["directories"]) == 912
        assert observed["selected"] is False
        assert observed["operational_acceptance"] is False
        assert observed["provider_connections"] is False
        assert observed["financial_effects"] is False


def test_one_shot_install_approval_is_consumed_source_pin_revoked(installed):
    receipt, _ = installed
    assert installer.APPROVAL_SHA256 is None
    assert hashlib.sha256(installer.APPROVAL.read_bytes()).hexdigest() == APPROVAL_SHA
    assert installer.approval_source_sha256() == SOURCE_PIN
    archived = json.loads(installer.APPROVAL.read_bytes())
    assert archived["installer_source_sha256"] == SOURCE_PIN
    assert archived["scope"] == installer.SCOPE
    assert archived["source_commit"] == receipt["source_commit"]
    assert archived["selection_allowed"] is False
    assert archived["financial_authority"] is False
    assert archived["provider_access"] is False
    assert archived["paper_accounts"] is False
    assert archived["live_orders_authorized"] is False
    assert installer.validate_operator_decision(archived, sid=current_sid()) == archived
    with pytest.raises(ValueError, match="R16_FRESH_ONE_SHOT_CODE_INSTALL_APPROVAL_NOT_PINNED"):
        installer.require_separate_consent()


def test_r16_native_selector_is_revision_15_but_paper_remains_no_go(installed):
    assert installed[0]["selected"] is False
    code = selected_code()
    assert code["selected_revision"] == 15
    assert code["selected_native_record_sha256"] == (
        "d8ea7097008019426d64f96ca717878082644d3ec7592d26ce0428607988cc6f")
    assert (handoff.SELECTION_ROOT / "r0015.json").is_file()
    assert (handoff.SELECTION_ROOT / "r0015.pending").is_file()
    personal = inspect_two_lane_native_roots()
    assert personal["native_root_total"] == 12
    assert personal["all_twelve_distinct_and_empty"] is True
    assert personal["financial_inception_verified"] is False
    assert personal["paper_start_authorized"] is False
    readiness = r16_readiness()
    assert readiness["decision"] == "NO_GO"
    assert readiness["financial_operating_gates_independently_accepted"] == 0
    assert readiness["financial_writer_roles_enrolled"] == 0
    assert readiness["paper_start_authorized"] is False
    assert readiness["live_trading_authorized"] is False
