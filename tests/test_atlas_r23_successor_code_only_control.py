"""R23->R24 one-shot code-only controller guard and review tests. No actions."""
import copy
import hashlib
import json
from pathlib import Path

import pytest

from scripts import atlas_r23_successor_code_only_control as ctl

ROOT = Path(r"D:\Work\Project Atlas")
PROPOSAL = ROOT / ("logs/diagnostics/"
    "atlas-single-successor-r23-to-r24-20261118-r01/proposal.json")
PIN = "f5c59942203e0f89479d961b4654e1c6db0471edf2b34874df9315f296f2847d"


@pytest.fixture
def original():
    assert hashlib.sha256(PROPOSAL.read_bytes()).hexdigest() == PIN
    return json.loads(PROPOSAL.read_bytes())


def test_exact_nonfinancial_source_and_native_artifact_pins(original):
    assert ctl.R23_SOURCE == "8463f1da3786647677629ae10da5e95c8940e688"
    assert ctl.R23_HEAD == "90ccd9a9b700c553deaf2c16ce2c3469fd986512c19abbb5815ce47c10dde39e"
    assert ctl.R23_ARTIFACT == "b7b21a66cd6487f7f2e5de05b3135c47338186d3ae621e0ef2afc50a0c3d5766"
    assert ctl.FROZEN_SUCCESSOR_SOURCE == "5c3970b7150fd448f5f3c5a25f424687c704a2f9"
    assert ctl.FROZEN_ARCHIVE_SHA == "23f14c12e264dca19094958f63263de63ce8bb91ae751571c6af784d0ae4233b"
    assert ctl.FROZEN_SOURCE_INVENTORY_SHA == "6aee9171b76a2c3b387252cd7f22ba0a78fd671daaee276dee7091edfd3dbdee"
    assert ctl.FROZEN_NATIVE_FILES == 10809 and ctl.FROZEN_NATIVE_BYTES == 267966246
    assert ctl.FROZEN_SOURCE_FILES == 1243 and ctl.FROZEN_DEPENDENCY_FILES == 9566
    assert original["expected_content_sha256"] == "4efd59ba8113ccd5d5d56e86a0070efe0d2a678ba540226f27c89a61f20e7244"
    assert ctl.INSTALL_SCOPE != ctl.SELECT_SCOPE
    assert hashlib.sha256((ROOT/"scripts/atlas_r22_successor_code_only_control.py").read_bytes()).hexdigest() == (
        "5dbd30268fbe1bb8bb64ab1375defe2ea77dc0d59a723b88818ea834fdc4145a")


def test_proposal_exact_and_current_r23_original_state(original):
    assert ctl.proposal(PROPOSAL, PIN) == original
    assert ctl.original_state(original) is True
    for key in ("review_only", "old_decision_not_authorized_for_this_proposal",
                "old_controller_consumed_decisions_not_redeemable",
                "old_controller_source_unchanged"):
        assert original[key] is True
    for key in ("installation_authorized", "selection_authorized",
                "paper_start_authorized", "provider_access",
                "account_creation_authorized", "live_trading_authorized",
                "local_operator_install_decision_created", "local_operator_select_decision_created",
                "new_native_selection_created", "native_target_installed"):
        assert original[key] is False
    assert not (PROPOSAL.parent / "local-install-decision.json").exists()
    assert not (PROPOSAL.parent / "local-select-decision.json").exists()
    assert not Path(r"D:\AtlasRuntime\selection\r0024.json").exists()


def test_original_prepared_content_plan_exact(original):
    plan = ctl.prepared(original)
    assert len(plan["names"]) == 10809
    assert len(plan["runtime"]) == 1243
    assert len(plan["dependencies"]) == 9566
    assert plan["total"] == 267966246
    assert plan["verified"]["activation_approved"] is False
    assert not Path(original["destination"]).exists()


@pytest.mark.parametrize("field,bad", [
    ("schema", "ATLAS_R22_TO_R23_CODE_ONLY_PROPOSAL_V1"),
    ("source_commit", ctl.R23_SOURCE),
    ("archive_sha256", "f"*64),
    ("source_inventory_sha256", "f"*64),
    ("source_files", 1236),
    ("dependency_files", 9565),
    ("native_files", 10802),
    ("native_directories", 916),
    ("native_bytes", 267966247),
    ("destination", r"D:\AtlasRuntime\releases\untrusted"),
    ("control_source_sha256", "f"*64),
    ("control_source", r"D:\Work\Project Atlas\scripts\atlas_r22_successor_code_only_control.py"),
    ("previous_head", "f"*64),
    ("installation_authorized", True),
    ("selection_authorized", True),
    ("financial_authority", True),
    ("paper_start_authorized", True),
    ("provider_access", True),
    ("live_trading_authorized", True),
    ("account_creation_authorized", True),
    ("automatic_startup", True),
    ("new_account_namespaces_initialized", True),
    ("native_target_installed", True),
    ("new_native_selection_created", True),
    ("old_decision_not_authorized_for_this_proposal", False),
    ("old_controller_consumed_decisions_not_redeemable", False),
    ("review_only", False),
    ("local_operator_install_decision_created", True),
    ("local_operator_select_decision_created", True),
    ("required_explicit_local_install_scope", "APPROVE_ALL"),
    ("required_distinct_explicit_local_select_scope", "APPROVE_ALL"),
])
def test_mutated_code_only_proposal_never_admitted(monkeypatch,original,field,bad):
    forged=copy.deepcopy(original)
    forged[field]=bad
    monkeypatch.setattr(ctl,"checked",
       lambda *_args,**_kwargs:json.dumps(forged,sort_keys=True).encode())
    with pytest.raises(ValueError,match="SUCCESSOR_EXACT_CODE_ONLY_PROPOSAL_REQUIRED"):
        ctl.proposal(PROPOSAL,PIN)


@pytest.mark.parametrize("mode",["execute-install","execute-select"])
def test_no_unreviewed_execution_allowed(mode):
    with pytest.raises(ValueError,match="SUCCESSOR_LOCAL_DECISION_PIN_REQUIRED"):
        ctl.main(["--proposal",str(PROPOSAL),"--proposal-sha256",PIN,"--mode",mode])


@pytest.mark.parametrize("kind",["install","select"])
def test_nonvisible_operator_cannot_approve(monkeypatch,kind):
    def no_visible_console():
        raise ValueError("SUCCESSOR_VISIBLE_WINDOWS_LOCAL_OPERATOR_REQUIRED")
    monkeypatch.setattr(ctl,"visible_local_console",no_visible_console)
    with pytest.raises(ValueError,match="SUCCESSOR_VISIBLE_WINDOWS_LOCAL_OPERATOR_REQUIRED"):
        ctl.decide(PROPOSAL,PIN,kind)
    assert not ctl.decision_path(PROPOSAL,kind).exists()


def test_altered_original_r23_receipt_cannot_be_adopted(original):
    altered=copy.deepcopy(original)
    altered["previous_spec"]["artifact_digest"]="0"*64
    with pytest.raises(ValueError,match="SUCCESSOR_ORIGINAL_R23_REVISION23_REQUIRED"):
        ctl.original_state(altered)


def test_altered_original_financial_root_binding_refuses(original):
    altered=copy.deepcopy(original)
    altered["original_roots"]["HYPERLIQUID"]["roots"]["source"]["native_id"][0]=0
    with pytest.raises(ValueError,match="SUCCESSOR_TWELVE_ORIGINAL_EMPTY_FINANCIAL_ROOTS_REQUIRED"):
        ctl.original_state(altered)
