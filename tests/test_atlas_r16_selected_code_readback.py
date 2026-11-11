"""Real selected R16 native revision-15 code and PAPER NO-GO readback.

Read-only tests do not infer financial authority from valid CODE selection.
"""
import hashlib
from pathlib import Path

import pytest

from scripts.observation_runtime import atlas_r16_selected_code_readback as check
from scripts import atlas_r16_code_only_selection_publisher as publisher
from scripts.volume_inspector.windows_output import current_sid

APPROVAL_SHA256 = "7f17dd9e34e56b38cc5259960309d76164660349424c2035dc897ddeb113ed03"
PUBLISHER_SOURCE_SHA = "996bc74f7b53b120374e573e13edbfa2b5a69f9d7cf60d8e2bc9f963133c58b7"


def test_real_native_selected_r16_15_record_chain_and_initial_financial_no_go():
    r=check.inspect()
    assert r["decision"]=="NO_GO"
    assert r["schema"]=="ATLAS_R16_CODE_SELECTED_PAPER_OFFLINE_READINESS_V1"
    assert r["financial_operating_gates_independently_accepted"]==0
    assert r["financial_operating_gates_total"]==9
    assert r["financial_writer_roles_enrolled"]==0
    assert r["financial_writer_roles_required"]==12
    assert r["native_existing_root_total"]==12
    assert r["native_financial_account_inception_accepted"] is False
    assert r["paper_start_authorized"] is False
    assert r["live_trading_authorized"] is False
    c=r["selected_code"]
    assert c["code_selection_accepted"] is True
    assert c["selected_revision"]==15
    assert c["selected_release"]==check.SOURCE
    assert c["selected_native_head"]==check.R16_HEAD
    assert c["selected_native_record_sha256"]==check.R16_RECORD_SHA
    assert c["installed_receipt_sha256"]==check.RECEIPT_SHA
    assert c["native_selection_append_only_chain_verified"] is True
    assert c["native_receipt_and_install_ack_verified"] is True
    assert c["installed_original_handles_reverified_in_this_call"] is False
    assert c["financial_clock_operational_accepted"] is False
    assert c["provider_source_operational_accepted"] is False
    assert c["financial_writer_operational_accepted"] is False
    assert c["paper_start_authorized"] is False
    assert c["live_trading_authorized"] is False


def test_selected_r16_real_original_installed_file_handles_still_verify():
    r=check.selected_code(verify_original_installed_handles=True)
    assert r["installed_original_handles_reverified_in_this_call"] is True
    assert r["selected_revision"]==15
    assert r["financial_writer_operational_accepted"] is False
    assert r["paper_start_authorized"] is False


def test_native_selected_record_hardlink_receipt_and_archive_hashes_still_pinned():
    for path,sha in [
        (check.SELECTION/"r0014.json",check.R15_SHA),
        (check.SELECTION/"r0014.pending",check.R15_SHA),
        (check.SELECTION/"r0015.json",check.R16_RECORD_SHA),
        (check.SELECTION/"r0015.pending",check.R16_RECORD_SHA),
        (check.RECEIPT,check.RECEIPT_SHA),
        (check.JOURNAL,check.JOURNAL_SHA),
    ]:
        assert path.is_file()
        assert hashlib.sha256(path.read_bytes()).hexdigest()==sha


def test_selected_r16_code_acceptance_does_not_reuse_selection_approval():
    assert publisher.APPROVAL_SHA256 is None
    assert publisher.APPROVAL.is_file()
    assert hashlib.sha256(publisher.APPROVAL.read_bytes()).hexdigest()==APPROVAL_SHA256
    assert publisher.approval_source_sha256()==PUBLISHER_SOURCE_SHA
    with pytest.raises(ValueError,match="R16_SELECTION_ONE_SHOT_OPERATOR_APPROVAL_NOT_PINNED"):
        publisher.require_operator_approval({"proposed_row":{}})
    from scripts import release_selection as rs
    record=rs.strict(publisher.APPROVAL.read_bytes())
    assert record["publisher_source_sha256"]==PUBLISHER_SOURCE_SHA
    assert record["source_commit"]==check.SOURCE
    assert record["native_selection_revision"]==15
    assert record["proposed_head"]==check.R16_HEAD
    assert record["operator_sid"]==current_sid()
    assert record["one_shot"] is True
    assert record["selection_allowed"] is True
    for k in ("financial_authority","paper_accounts","provider_access",
              "paper_start_authorized","live_orders_authorized"):
        assert record[k] is False


def test_selected_native_record_bad_sha_refuses_not_auto_repaired(monkeypatch):
    monkeypatch.setattr(check,"R16_RECORD_SHA","0"*64)
    with pytest.raises(ValueError,match="R16_SELECTED_CODE_NATIVE_HASH_CHANGED"):
        check.selected_code()


def test_selected_native_still_refuses_synthetic_bool_scope_and_missing_file(tmp_path):
    with pytest.raises(ValueError,match="R16_SELECTED_CODE_EXPLICIT_READBACK_SCOPE_REQUIRED"):
        check.selected_code(verify_original_installed_handles=1)
    wrong=tmp_path/"missing.json"
    with pytest.raises(ValueError,match="R16_SELECTED_CODE_NATIVE_RECEIPT_OR_RECORD_REQUIRED"):
        check._pin(wrong,"0"*64,maximum=1024)
    wrong.write_text("FOREIGN")
    with pytest.raises(ValueError,match="R16_SELECTED_CODE_NATIVE_HASH_CHANGED"):
        check._pin(wrong,"0"*64,maximum=1024)


def test_fake_operating_account_inception_refuses_code_readiness(monkeypatch):
    old=check.inspect_two_lane_native_roots
    def forged():
        evidence=old()
        evidence["financial_inception_verified"]=True
        return evidence
    monkeypatch.setattr(check,"inspect_two_lane_native_roots",forged)
    with pytest.raises(ValueError,match="R16_SELECTED_CODE_PREINCEPTION_NATIVE_ROOTS_CHANGED"):
        check.inspect()
