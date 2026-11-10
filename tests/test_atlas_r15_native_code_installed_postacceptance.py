"""Read-only post-install R15 native evidence, without code selection.

The original one-shot native installer already completed its isolated full
native child readback. These checks confirm the durable receipt/journal and
current native R14 selector, without re-copying 263 MB of installed files.
"""
import hashlib
import json
from pathlib import Path

import pytest

from scripts import atlas_r15_code_only_installer as installer
from scripts import atlas_r15_selection_handoff as handoff
from scripts import atlas_r15_code_only_selection_publisher as publisher
from scripts.observation_runtime.atlas_r14_selected_paper_readiness import (
    collect_selected_reference,
)
from scripts import release_selection


RECEIPT_SHA = "b313a20f0a747c4a2ac81a2c1ae11b50901786008ce75f84202bf2f2435e741c"
ARTIFACT = "6db8cae881cd0f331b3f0aae78c92f27dbff860c658bb67ab1cfe91a6b8465e6"
PROPOSED = "274f5b00ee0e2f6271c6dd1dc5316f7d9124e932483038a6d93ef62ddbd2cd25"
APPROVAL_SHA = "0746bcf799af2a5b6069511b2de15ead45650f58db97eff729ce37154148986a"
SOURCE_SHA = "7a16b28b5a7df2d26fc508a3d7b00dab453f61dfe08951bb736cdb2e3612c103"


@pytest.fixture(scope="module")
def accepted():
    if not installer.TARGET.is_dir() or not installer.RECEIPT.is_file():
        pytest.skip("R15 native code-only installation not present on this host")
    payload=installer.RECEIPT.read_bytes()
    return json.loads(payload),payload,handoff.inspect()


def test_genuine_r15_install_receipt_is_exact_complete_nonfinancial(accepted):
    receipt,raw,handoff_report=accepted
    assert hashlib.sha256(raw).hexdigest()==RECEIPT_SHA
    assert receipt["source_commit"]==installer.SOURCE_COMMIT
    assert receipt["archive_sha256"]==installer.ARCHIVE_SHA
    assert receipt["inventory_sha256"]==installer.INVENTORY_SHA
    assert receipt["release_path"]==str(installer.TARGET)
    assert receipt["artifact_digest"]==ARTIFACT
    assert len(receipt["files"])==10526
    assert len(receipt["directories"])==912
    assert receipt["stage"]=="D_RUNTIME_LAYOUT_VERIFIED"
    assert all(receipt[k] is False for k in (
        "selected","financial_effects","provider_connections",
        "operational_acceptance"))
    assert receipt["layout"]["version"]==[3,12]


def test_durable_final_install_ack_matches_real_unchanged_receipt(accepted):
    receipt,raw,handoff_report=accepted
    bytes_journal=installer.RECEIPT.with_suffix(".pending.jsonl").read_bytes()
    assert len(bytes_journal.splitlines())==2
    last=release_selection.strict(bytes_journal.splitlines()[-1])
    assert last=={
        "stage":"UNSELECTED_CODE_INSTALL_VERIFIED",
        "receipt_sha256":RECEIPT_SHA,
    }
    assert release_selection.validate_native_install_ack(
        handoff_report["proposed_row"]["selected"],receipt,bytes_journal)


def test_selected_release_remains_r14_with_r15_only_proposed(accepted):
    receipt,raw,handoff_report=accepted
    s=collect_selected_reference()
    assert s["revision"]==13
    assert s["native_r13_envelope_sha256"]==(
        "6b1e04b8f733d46421c81a5d158dbafbecf052e6f3a8e8289d175caca96d4e31")
    assert s["selected_release"]=="7ff9d3dba2eabe110f843c13efac49464805de2a"
    assert handoff_report["status"]==(
        "SOURCE_ONLY_CANDIDATE_REQUIRES_NATIVE_HANDLE_VERIFIER_AND_ONE_SHOT_SELECTION_APPROVAL")
    assert handoff_report["proposed_row_digest"]==PROPOSED
    assert handoff_report["proposed_row"]["previous"]==(
        "3fd8e1972b559a5de90627a303fc663b11928f8b43e84621a6796e9f3dbe9383")
    assert handoff_report["proposed_row"]["revision"]==14
    assert handoff_report["new_selection_record_written"] is False
    assert not (handoff.SELECTION_ROOT/"r0014.json").exists()
    assert not (handoff.SELECTION_ROOT/"r0014.pending").exists()


def test_exact_install_approval_record_retained_and_execution_pin_revoked(accepted):
    assert installer.APPROVAL_SHA256 is None
    assert installer.APPROVAL.is_file()
    raw=installer.APPROVAL.read_bytes()
    assert hashlib.sha256(raw).hexdigest()==APPROVAL_SHA
    assert installer.approval_source_sha256()==SOURCE_SHA
    row=json.loads(raw)
    assert installer.validate_operator_decision(row,sid=row["operator_sid"])==row
    assert row["one_shot"] is True
    assert all(row[k] is False for k in (
        "selection_allowed","financial_authority","paper_accounts",
        "provider_access","startup_authorized","paper_orders_authorized",
        "live_orders_authorized"))
    with pytest.raises(ValueError,match="APPROVAL_NOT_PINNED"):
        installer.require_separate_consent()


def test_separate_code_selection_is_unapproved_after_install(accepted):
    report=publisher.inspect()
    assert report["status"]=="PROPOSAL_REVIEW_ONLY_AWAITING_EXACT_APPROVAL"
    assert report["proposed_head"]==PROPOSED
    assert report["proposed_row_available"] is True
    assert report["native_installed_child_readback_completed"] is False
    assert report["native_selection_published"] is False
    assert report["exact_one_shot_operator_approval_pinned"] is False
    assert publisher.APPROVAL_SHA256 is None
    assert all(report[k] is False for k in (
        "financial_authority","paper_accounts_enrolled",
        "provider_access","paper_start_authorized",
        "live_orders_authorized"))


def test_post_install_preflight_refuses_to_reuse_target(accepted):
    with pytest.raises(ValueError,match="NATIVE_TARGET_OR_RECEIPT_ALREADY_OCCUPIED"):
        installer.inspect()
    with pytest.raises(ValueError,match="APPROVAL_NOT_PINNED"):
        installer.install(execute_approved=True,clock=None)
