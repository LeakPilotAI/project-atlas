"""Fail-closed post-journal original R26 recovery classification: memory-only."""
import copy
import pytest
from scripts.observation_runtime.personal_r26_postjournal_recovery_decision import (
    SCHEMA, NEXT, classify_postjournal_original,
)

D = {"QUALITY_DIPS": "a"*64, "HYPERLIQUID": "b"*64}


def good():
    return {
        "selected_revision": 26,
        "original_journal_receipts": {
            lane: {"native_initial_revision": 1, "verified": True,
                   "account_digest": key, "account_inception_rows": 0,
                   "pending_publications": 0}
            for lane, key in D.items()
        },
        "original_roots": {
            "native_roots_verified": 12, "empty_roots": 10,
            "coordination_nonempty": 2,
            "source_projection_report_control_custody_empty": True,
        },
        "original_activation": {
            "origin": "LOCAL_OPERATOR",
            "actions": ["READ_ONLY", "INITIALIZE_SIMULATED_ACCOUNTS"],
            "accounts": copy.deepcopy(D), "original_only": True,
        },
        "original_failure": {
            "phase": "ORIGINAL_STAGE_D_E_F_ONCE_POSSIBLY_IRREVERSIBLE",
            "error": "PERSONAL_TECHNICAL_CHECKS_FAILED",
            "replay_reserved": True,
        },
        "last_writer_excluded": True,
        "expected_account_digests": copy.deepcopy(D),
    }


def test_exact_original_interrupted_cut_requires_new_authority_without_writes():
    case=good()
    before=copy.deepcopy(case)
    out=classify_postjournal_original(**case)
    assert case==before
    assert out["schema"]==SCHEMA
    assert out["next_required"]==NEXT
    assert out["original_coordination_journals_verified"]==2
    assert out["original_financial_account_publications"]==0
    assert out["original_empty_noncoordination_roots"]==10
    for key in (
        "same_epoch_initialization_replay_permitted",
        "old_operator_approval_reusable_for_successor",
        "old_journal_overwrite_or_delete_permitted",
        "new_activation_issued", "new_financial_account_issued",
        "paper_start_authorized", "live_trading_authorized",
    ):
        assert out[key] is False


@pytest.mark.parametrize("damage", [
    "release", "live_process", "missing_lane", "extra_lane",
    "old_journal_revision", "unverified_journal", "account_digest_changed",
    "already_created_account", "pending_publication", "same_account_digest",
    "unknown_native_root", "one_coordination_only", "source_root_populated",
    "wrong_operator", "wrong_activation_action", "foreign_activation_accounts",
    "old_approval_reuse", "wrong_phase", "different_error", "replay_not_reserved",
])
def test_refuses_recovery_decision_on_uncertain_native_financial_cut(damage):
    case=good()
    if damage=="release":case["selected_revision"]=27
    elif damage=="live_process":case["last_writer_excluded"]=False
    elif damage=="missing_lane":case["original_journal_receipts"].pop("QUALITY_DIPS")
    elif damage=="extra_lane":case["original_journal_receipts"]["FOREIGN"]=dict(case["original_journal_receipts"]["QUALITY_DIPS"])
    elif damage=="old_journal_revision":case["original_journal_receipts"]["HYPERLIQUID"]["native_initial_revision"]=2
    elif damage=="unverified_journal":case["original_journal_receipts"]["QUALITY_DIPS"]["verified"]=False
    elif damage=="account_digest_changed":case["original_journal_receipts"]["QUALITY_DIPS"]["account_digest"]="z"*64
    elif damage=="already_created_account":case["original_journal_receipts"]["QUALITY_DIPS"]["account_inception_rows"]=1
    elif damage=="pending_publication":case["original_journal_receipts"]["HYPERLIQUID"]["pending_publications"]=1
    elif damage=="same_account_digest":case["expected_account_digests"]["HYPERLIQUID"]=case["expected_account_digests"]["QUALITY_DIPS"]
    elif damage=="unknown_native_root":case["original_roots"]["native_roots_verified"]=11
    elif damage=="one_coordination_only":case["original_roots"]["coordination_nonempty"]=1
    elif damage=="source_root_populated":case["original_roots"]["source_projection_report_control_custody_empty"]=False
    elif damage=="wrong_operator":case["original_activation"]["origin"]="ADMIN_BYPASS"
    elif damage=="wrong_activation_action":case["original_activation"]["actions"]=["AUTO_PAPER"]
    elif damage=="foreign_activation_accounts":case["original_activation"]["accounts"]["QUALITY_DIPS"]="c"*64
    elif damage=="old_approval_reuse":case["original_activation"]["original_only"]=False
    elif damage=="wrong_phase":case["original_failure"]["phase"]="UNKNOWN"
    elif damage=="different_error":case["original_failure"]["error"]="SYNTHETIC_SUCCESS"
    elif damage=="replay_not_reserved":case["original_failure"]["replay_reserved"]=False
    with pytest.raises(ValueError,match="POSTJOURNAL"):
        classify_postjournal_original(**case)


def test_missing_tech_fields_never_make_inception_permissible():
    case=good()
    case["original_journal_receipts"]["QUALITY_DIPS"].pop("pending_publications")
    with pytest.raises(ValueError,match="POSTJOURNAL"):
        classify_postjournal_original(**case)
