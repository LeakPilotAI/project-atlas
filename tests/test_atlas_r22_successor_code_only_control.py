"""R22 -> R23 code-only controller, pinned original-native refusal tests.

No installation, selector publication, account, data-provider, or trading effects.
The sole genuine review invocation is intentionally read-only.
"""
import copy
import hashlib
import json
from pathlib import Path

import pytest

from scripts import atlas_r22_successor_code_only_control as ctl

ROOT = Path(r"D:\Work\Project Atlas")
PROPOSAL = ROOT / (
    "logs/diagnostics/atlas-single-successor-r22-to-r23-20261118-r02/proposal.json"
)
PIN = "0b69b2a9a69e556e33841203887968d6225651265b0b59b86d25a67aafe78529"


@pytest.fixture
def original():
    assert hashlib.sha256(PROPOSAL.read_bytes()).hexdigest() == PIN
    return json.loads(PROPOSAL.read_bytes())


def test_controller_is_one_new_release_and_not_the_consumed_old_controller():
    assert ctl.R22_SOURCE == "2f0fcfd9741b8fd524f2e5921a79998373a689c9"
    assert ctl.R22_HEAD == "86649902c02cfe99be2e5714091d8d4e6ff9b483df6cfa645566e44d40e7f92b"
    assert ctl.FROZEN_SUCCESSOR_SOURCE == "8463f1da3786647677629ae10da5e95c8940e688"
    assert ctl.FROZEN_NATIVE_FILES == 10802
    assert ctl.FROZEN_NATIVE_BYTES == 267897262
    assert ctl.FROZEN_SOURCE_FILES == 1236
    assert ctl.FROZEN_DEPENDENCY_FILES == 9566
    assert hashlib.sha256(
        (ROOT / "scripts/atlas_single_successor_control.py").read_bytes()
    ).hexdigest() == "d47e74e84b0ad843e593ff6d24834f44e5925bda892c21afd1189154391c0dc2"
    assert ctl.INSTALL_SCOPE != ctl.SELECT_SCOPE


def test_genuine_pinned_review_proposal_and_original_state(original):
    assert ctl.proposal(PROPOSAL, PIN) == original
    assert ctl.original_state(original) is True
    assert original["review_only"] is True
    assert original["installation_authorized"] is False
    assert original["selection_authorized"] is False
    assert original["financial_authority"] is False
    assert original["paper_start_authorized"] is False
    assert original["provider_access"] is False


def test_genuine_pinned_selected_source_archive_plan(original):
    prepared = ctl.prepared(original)
    assert len(prepared["names"]) == 10802
    assert len(prepared["runtime"]) == 1236
    assert len(prepared["dependencies"]) == 9566
    assert prepared["total"] == 267897262
    assert prepared["verified"]["activation_approved"] is False
    assert not (Path(original["destination"])).exists()
    assert not Path(r"D:\AtlasRuntime\selection\r0023.json").exists()


@pytest.mark.parametrize("name,new_value", [
    ("schema", "ATLAS_SINGLE_SUCCESSOR_CODE_ONLY_PROPOSAL_V3"),
    ("source_commit", ctl.R22_SOURCE),
    ("archive_sha256", "0" * 64),
    ("source_inventory_sha256", "0" * 64),
    ("source_files", 1207),
    ("dependency_files", 9565),
    ("native_files", 10773),
    ("native_directories", 916),
    ("native_bytes", 267897263),
    ("previous_head", "0" * 64),
    ("destination", r"D:\AtlasRuntime\releases\forged"),
    ("control_source_sha256", "0" * 64),
    ("control_source", r"D:\Work\Project Atlas\scripts\atlas_single_successor_control.py"),
    ("installation_authorized", True),
    ("selection_authorized", True),
    ("paper_start_authorized", True),
    ("provider_access", True),
    ("financial_authority", True),
    ("live_trading_authorized", True),
    ("account_creation_authorized", True),
    ("automatic_startup", True),
    ("old_decision_not_authorized_for_this_proposal", False),
    ("old_controller_consumed_decisions_not_redeemable", False),
    ("old_controller_source_unchanged", False),
    ("review_only", False),
    ("local_operator_install_decision_created", True),
    ("local_operator_select_decision_created", True),
    ("native_target_installed", True),
    ("new_native_selection_created", True),
    ("new_account_namespaces_initialized", True),
    ("required_explicit_local_install_scope", "APPROVE_ALL"),
    ("required_distinct_explicit_local_select_scope", "APPROVE_ALL"),
])
def test_wrong_or_unsafe_proposal_refuses_before_any_operation(
        monkeypatch, original, name, new_value):
    forged = copy.deepcopy(original)
    forged[name] = new_value
    monkeypatch.setattr(
        ctl, "checked",
        lambda _path, _pin, maximum=8 * 1024**2:
        json.dumps(forged, sort_keys=True, separators=(",", ":")).encode(),
    )
    with pytest.raises(ValueError, match="SUCCESSOR_EXACT_CODE_ONLY_PROPOSAL_REQUIRED"):
        ctl.proposal(PROPOSAL, PIN)


def test_original_predecessor_artifact_mutation_refuses(original):
    altered = copy.deepcopy(original)
    altered["previous_spec"]["artifact_digest"] = "0" * 64
    with pytest.raises(ValueError, match="SUCCESSOR_ORIGINAL_R22_REVISION22_REQUIRED"):
        ctl.original_state(altered)


def test_original_namespace_identity_mutation_refuses(original):
    altered = copy.deepcopy(original)
    altered["original_roots"]["HYPERLIQUID"]["roots"]["source"]["native_id"][0] = 0
    with pytest.raises(ValueError, match="SUCCESSOR_TWELVE_ORIGINAL_EMPTY_FINANCIAL_ROOTS_REQUIRED"):
        ctl.original_state(altered)


@pytest.mark.parametrize("kind", ["execute-install", "execute-select"])
def test_no_execution_without_new_exact_local_decision_pin(kind):
    with pytest.raises(ValueError, match="SUCCESSOR_LOCAL_DECISION_PIN_REQUIRED"):
        ctl.main(["--proposal", str(PROPOSAL), "--proposal-sha256", PIN,
                  "--mode", kind])
    assert not Path(r"D:\AtlasRuntime\selection\r0023.json").exists()


@pytest.mark.parametrize("kind", ["install", "select"])
def test_local_decision_refuses_nonvisible_operator_terminal(monkeypatch,kind):
    def no_console():
        raise ValueError("SUCCESSOR_VISIBLE_WINDOWS_LOCAL_OPERATOR_REQUIRED")
    monkeypatch.setattr(ctl,"visible_local_console",no_console)
    with pytest.raises(ValueError,match="SUCCESSOR_VISIBLE_WINDOWS_LOCAL_OPERATOR_REQUIRED"):
        ctl.decide(PROPOSAL,PIN,kind)
    assert not ctl.decision_path(PROPOSAL,kind).exists()


def test_install_intent_missing_and_no_new_release_was_created(original):
    assert not Path(original["receipt"]).exists()
    assert not Path(original["receipt"]).with_suffix(".pending.jsonl").exists()
    assert not Path(original["destination"]).exists()
    assert not (PROPOSAL.parent / "local-install-decision.json").exists()
    assert not (PROPOSAL.parent / "local-select-decision.json").exists()
    assert not (PROPOSAL.parent / "local-install-attempt.json").exists()
    assert not (PROPOSAL.parent / "local-select-attempt.json").exists()


def test_genuine_readonly_cli_return_value_has_no_financial_authority():
    got=ctl.main(["--proposal",str(PROPOSAL),"--proposal-sha256",PIN,
                  "--mode","review"])
    assert got["status"]=="SOURCE_AND_DEPENDENCY_PLAN_ONLY_NO_OPERATIONAL_MUTATION"
    assert got["files"]==10802
    assert got["source_commit"]==ctl.FROZEN_SUCCESSOR_SOURCE
    assert got["financial_authority"] is False


def test_wrong_proposal_hash_refuses_before_plan():
    with pytest.raises(ValueError,match="SUCCESSOR_PINNED_INPUT_CHANGED"):
        ctl.main(["--proposal",str(PROPOSAL),"--proposal-sha256","0"*64,
                  "--mode","review"])
