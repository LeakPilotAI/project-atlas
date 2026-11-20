"""R16 native code-only preflight and one-shot installer fail-closed tests.

No native installation is approved, no clock/network/market source, no real
account inception. The real R15 selected native chain is READ ONLY.
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import atlas_r16_code_only_installer as installer
from scripts.observation_runtime import atlas_r16_code_install_plan_preflight as plan

SID = "S-1-5-21-SYNTHETIC-TEST-ONLY"


@pytest.fixture(scope="module")
def actual():
    # Preinstallation-only preview intentionally refuses once the exact
    # create-only target exists. Postacceptance tests independently verify
    # the installed native files and durable ACK instead.
    if plan.TARGET.exists() or plan.RECEIPT.exists():
        pytest.skip("R16 already installed: use native postacceptance readback")
    return plan.inspect()


def fake_decision():
    return {
        "schema": "ATLAS_R16_CODE_ONLY_NATIVE_INSTALL_APPROVAL_V1",
        "decision": installer.OPERATION,
        "scope": installer.SCOPE,
        "source_commit": plan.SOURCE_COMMIT,
        "source_archive_sha256": plan.ARCHIVE_SHA,
        "source_inventory_sha256": plan.INVENTORY_SHA,
        "target": str(plan.TARGET),
        "receipt": str(plan.RECEIPT),
        "dependency_inventory_sha256": plan.DEPENDENCY_INVENTORY_SHA256,
        "selected_r15_head": installer.SELECTED_HEAD,
        "selected_r15_record_sha256": installer.SELECTED_SHA,
        "installer_source_sha256": installer.approval_source_sha256(),
        "operator_sid": SID, "one_shot": True,
        "selection_allowed": False, "financial_authority": False,
        "provider_access": False, "paper_accounts": False,
        "startup_authorized": False, "paper_orders_authorized": False,
        "live_orders_authorized": False,
    }


def test_real_selected_r15_and_frozen_r16_read_only_plan(actual):
    assert actual["schema"] == "ATLAS_R16_SOURCE_ONLY_NATIVE_INSTALL_PROPOSAL_V1"
    assert actual["status"] == "SOURCE_AND_DEPENDENCY_PLAN_VERIFIED_NOT_INSTALL_AUTHORIZATION"
    assert actual["native_selected_predecessor"] == plan.SELECTED_R15_RELEASE
    assert actual["native_selected_predecessor_head"] == installer.SELECTED_HEAD
    assert actual["planned_runtime_source_files"] == 983
    assert actual["planned_dependency_files"] == 9566
    assert actual["planned_native_files"] == 10549
    assert actual["planned_native_directories"] == 912
    assert actual["planned_native_bytes"] == 263892205
    assert actual["source_archive_sha256"] == plan.ARCHIVE_SHA
    assert actual["native_installation_executed"] is False
    assert actual["native_selection_changed"] is False
    assert actual["financial_writer_enrolled"] is False
    assert actual["paper_orders_authorized"] is False
    assert actual["live_trading_authorized"] is False
    assert actual["financial_operating_gates_accepted"] == 0


def test_low_impact_r16_inspect_remains_unselected_and_not_approved(actual):
    observed=installer.inspect()
    assert observed["schema"] == "ATLAS_R16_CODE_ONLY_LOW_IMPACT_INSTALLER_PREVIEW_V1"
    assert observed["planned_native_files"] == actual["planned_native_files"]
    assert observed["planned_native_bytes"] == actual["planned_native_bytes"]
    assert observed["new_install_target"] == str(plan.TARGET)
    assert observed["operator_approval_pinned"] is False
    assert observed["installation_authorized"] is False
    assert observed["installed"] is False
    assert observed["selection_authorized"] is False
    assert observed["live_orders_authorized"] is False
    assert installer.main(["--inspect"]) == observed


def test_source_pin_normalization_stable_and_separate_approval_default_unpinned():
    sha=installer.approval_source_sha256()
    assert len(sha)==64 and all(c in "0123456789abcdef" for c in sha)
    assert installer.APPROVAL_SHA256 is None
    assert "r16" in installer.APPROVAL.name.lower()
    assert "r15" not in installer.APPROVAL.name.lower()


def test_synthetic_correct_decision_is_only_structural_validation():
    x=fake_decision()
    assert installer.validate_operator_decision(x,sid=SID) is x
    assert x["financial_authority"] is False
    # Valid structure is NOT installed or a file-based SID approval.
    with pytest.raises(ValueError,match="R16_FRESH_ONE_SHOT_CODE_INSTALL_APPROVAL_NOT_PINNED"):
        installer.require_separate_consent()


@pytest.mark.parametrize("key", [
    "schema", "decision", "scope", "source_commit", "source_archive_sha256",
    "source_inventory_sha256", "target", "receipt", "dependency_inventory_sha256",
    "selected_r15_head", "selected_r15_record_sha256",
    "installer_source_sha256", "operator_sid", "one_shot",
])
def test_nonmatching_one_shot_operator_decision_field_refuses(key):
    x=fake_decision()
    x[key]=False if key=="one_shot" else "UNTRUSTED"
    with pytest.raises(ValueError,match="R16_EXACT_SID_BOUND_ONE_SHOT_INSTALL_DECISION_REQUIRED"):
        installer.validate_operator_decision(x,sid=SID)


@pytest.mark.parametrize("key", [
    "selection_allowed", "financial_authority", "provider_access",
    "paper_accounts", "startup_authorized",
    "paper_orders_authorized", "live_orders_authorized",
])
def test_broad_authority_cannot_hide_in_r16_code_only_approval(key):
    x=fake_decision()
    x[key]=True
    with pytest.raises(ValueError,match="R16_EXACT_SID_BOUND_ONE_SHOT_INSTALL_DECISION_REQUIRED"):
        installer.validate_operator_decision(x,sid=SID)


def test_foreign_or_additional_approval_fields_and_sid_refuse():
    x=fake_decision()
    x["hidden_financial_grant"]=True
    with pytest.raises(ValueError,match="R16_EXACT_SID_BOUND_ONE_SHOT_INSTALL_DECISION_REQUIRED"):
        installer.validate_operator_decision(x,sid=SID)
    x.pop("hidden_financial_grant")
    with pytest.raises(ValueError,match="R16_EXACT_SID_BOUND_ONE_SHOT_INSTALL_DECISION_REQUIRED"):
        installer.validate_operator_decision(x,sid="S-1-5-21-OTHER")


def test_r16_exec_refused_before_ntp_native_copy_or_install_receipt(monkeypatch):
    from scripts.observation_runtime import atlas_independent_ntp_clock as ntp
    from scripts import native_install_candidate as copy
    def forbidden(*a,**k):
        pytest.fail("R16_UNAPPROVED_MUST_NOT_START_NTP_COPY_OR_WRITE")
    monkeypatch.setattr(ntp, "IndependentNtpClock", forbidden)
    monkeypatch.setattr(copy, "_copy_prepared_code", forbidden)
    with pytest.raises(ValueError,match="R16_FRESH_ONE_SHOT_CODE_INSTALL_APPROVAL_NOT_PINNED"):
        installer.main(["--execute-one-shot-code-install","--confirm-scope",installer.SCOPE])
    with pytest.raises(ValueError,match="R16_EXPLICIT_CODE_ONLY_INSTALL_EXECUTION_REQUIRED"):
        installer.install()
    with pytest.raises(ValueError,match="R16_EXACT_ONE_SHOT_SCOPE_CONFIRMATION_REQUIRED"):
        installer.main(["--execute-one-shot-code-install","--confirm-scope","OTHER"])
    # A consumed installation keeps the same refusal but preserves its
    # immutable target and receipt; never rewrite history to pass a test.
    assert plan.TARGET.exists() == plan.RECEIPT.exists()


def original_selected_r15_synthetic_anchored_reference():
    """Historic R15 installation admission contract, not CURRENT selector."""
    return {
        "revision":14,
        "selected_release":plan.SELECTED_R15_RELEASE,
        "selected_native_head":installer.SELECTED_HEAD,
        "selected_native_record_sha256":installer.SELECTED_SHA,
        "native_clock_own_release_source_admitted":True,
        "independent_live_financial_clock_lease_accepted":False,
        "financial_authority":False,
    }


@pytest.mark.parametrize("fault", [
    "revision", "selected_release", "selected_native_head",
    "selected_native_record_sha256", "native_clock_own_release_source_admitted",
    "independent_live_financial_clock_lease_accepted", "financial_authority",
])
def test_selected_r15_native_chain_cannot_be_forged(fault):
    value=copy.deepcopy(original_selected_r15_synthetic_anchored_reference())
    value[fault]=True if value[fault] is False else "FORGED"
    with pytest.raises(ValueError,match="R16_GENUINE_NATIVE_SELECTED_R15_ANCHOR_REQUIRED"):
        plan.validate_selected_r15(value)


@pytest.mark.parametrize("field", [
    "source_commit", "source_archive_sha256", "selected_source_inventory_sha256",
    "source_files", "dependency_files", "native_files_planned",
    "native_directories_planned", "native_bytes_planned",
    "selected_r15_selection_record_sha256", "selected_r15_unchanged",
    "financial_authority", "native_installation_executed",
    "native_release_selection_authorized", "paper_orders_authorized",
    "financial_operating_gates_accepted",
])
def test_modified_source_review_or_financial_flag_refuses(field):
    review=json.loads(plan.FREEZE.read_text(encoding="utf-8"))
    synthetic={
        "selected_digest":plan.INVENTORY_SHA,
        "verified":{"source_files":983,"activation_approved":False,
                    "installation_verified":False},
        "runtime":{i:None for i in range(983)},
        "dependencies":{i:None for i in range(9566)},
        "names":[None]*10549, "directories":[None]*911,
        "total":263892205,
    }
    review[field]= "FORGED" if field!="financial_authority" else True
    with pytest.raises(ValueError,match="R16_PINNED_SOURCE_FREEZE_REVIEW_REQUIRED"):
        plan.evaluate(selected=original_selected_r15_synthetic_anchored_reference(),
                      prepared=synthetic,freeze=review)


def test_create_only_target_and_future_receipt_occupied_refuse(tmp_path,monkeypatch):
    proposed=tmp_path/"releases"/"r16"; proposed.parent.mkdir()
    receipt=tmp_path/"r16.json"
    monkeypatch.setattr(plan,"TARGET",proposed)
    monkeypatch.setattr(plan,"RECEIPT",receipt)
    assert plan.require_new_native_target(path=proposed) is True
    proposed.mkdir()
    with pytest.raises(ValueError,match="R16_NATIVE_TARGET_OR_RECEIPT_ALREADY_OCCUPIED"):
        plan.require_new_native_target(path=proposed)
    proposed.rmdir()
    receipt.write_text("partial irreversible receipt")
    with pytest.raises(ValueError,match="R16_NATIVE_TARGET_OR_RECEIPT_ALREADY_OCCUPIED"):
        plan.require_new_native_target(path=proposed)
    receipt.unlink()
    receipt.with_suffix(".pending.jsonl").write_text("partial intent")
    with pytest.raises(ValueError,match="R16_NATIVE_TARGET_OR_RECEIPT_ALREADY_OCCUPIED"):
        plan.require_new_native_target(path=proposed)


def test_final_native_install_ack_only_nonfinancial_vetted_receipt():
    source={"source_commit":plan.SOURCE_COMMIT,
            "release_path":str(plan.TARGET),"selected":False,
            "financial_effects":False,"provider_connections":False,
            "operational_acceptance":False,"stage":"D_RUNTIME_LAYOUT_VERIFIED",
            "artifact_digest":"a"*64}
    result=installer.final_native_install_ack(source)
    expected=hashlib.sha256(json.dumps(source,sort_keys=True,allow_nan=False).encode()).hexdigest()
    assert result=={"stage":"UNSELECTED_CODE_INSTALL_VERIFIED","receipt_sha256":expected}
    for key in ("selected","financial_effects","provider_connections","operational_acceptance"):
        changed={**source,key:True}
        with pytest.raises(ValueError,match="R16_FINAL_NONFINANCIAL_RECEIPT_REQUIRED"):
            installer.final_native_install_ack(changed)


def test_native_copy_refusal_and_future_clock_ineligible_without_pinned_consent(monkeypatch):
    calls=[]
    def no_clock_or_host(*args,**kwargs):
        calls.append(True)
        raise AssertionError("NO_CLOCK_OR_HOST_BEFORE_CONSENT")
    monkeypatch.setattr(installer,"require_code_install_host_ready",no_clock_or_host)
    with pytest.raises(ValueError,match="R16_FRESH_ONE_SHOT_CODE_INSTALL_APPROVAL_NOT_PINNED"):
        installer.install(execute_approved=True,clock=object())
    assert calls==[]
