"""R26 original post-journal interrupted-inception recovery decision.

No financial side effects. This gate prevents a post-journal failure being
misclassified as virgin preinception or already-initialized financial PAPER.
It does not mint a new owner, enrollment, activation, journal, account or scope.
"""
from __future__ import annotations

from app.services.paper_financial_replay import body, strict

SCHEMA = "ATLAS_R26_POSTJOURNAL_RECOVERY_DECISION_V1"
LANES = ("QUALITY_DIPS", "HYPERLIQUID")
ALLOWED_ACTIONS = ("READ_ONLY", "INITIALIZE_SIMULATED_ACCOUNTS")
PHASE = "ORIGINAL_STAGE_D_E_F_ONCE_POSSIBLY_IRREVERSIBLE"
FAILED = "PERSONAL_TECHNICAL_CHECKS_FAILED"
NEXT = "FRESH_VERSION_SAFE_FINANCIAL_RECOVERY_RELEASE_WITH_SEPARATE_EXPLICIT_OPERATOR_ADMISSION"


def classify_postjournal_original(
    *, selected_revision, original_journal_receipts,
    original_roots, original_activation, original_failure,
    last_writer_excluded, expected_account_digests,
):
    """Classify observed facts ONLY. Refuse ambiguous/partial financial state.

    The caller must acquire native, handle-bound evidence independently.
    No caller-provided dict here constitutes a signed financial permission.
    """
    if type(selected_revision) is not int or selected_revision != 26:
        raise ValueError("POSTJOURNAL_SELECTED_RELEASE_NOT_R26")
    if (type(last_writer_excluded) is not bool or not last_writer_excluded):
        raise ValueError("POSTJOURNAL_ORIGINAL_NATIVE_WRITER_EXIT_NOT_ESTABLISHED")
    if (type(original_journal_receipts) is not dict
            or set(original_journal_receipts) != set(LANES)
            or type(expected_account_digests) is not dict
            or set(expected_account_digests) != set(LANES)):
        raise ValueError("POSTJOURNAL_BOTH_ORIGINAL_ACCOUNT_RECEIPTS_REQUIRED")
    for lane in LANES:
        j = original_journal_receipts[lane]
        d = expected_account_digests[lane]
        if (type(j) is not dict or set(j) != {
                "native_initial_revision", "verified", "account_digest",
                "account_inception_rows", "pending_publications"}
                or type(d) is not str or len(d) != 64
                or any(c not in "0123456789abcdef" for c in d)
                or type(j["native_initial_revision"]) is not int
                or j["native_initial_revision"] != 1
                or j["verified"] is not True or j["account_digest"] != d
                or type(j["account_inception_rows"]) is not int
                or j["account_inception_rows"] != 0
                or type(j["pending_publications"]) is not int
                or j["pending_publications"] != 0):
            raise ValueError("POSTJOURNAL_ORIGINAL_UNCERTAIN_NATIVE_FINANCIAL_CUT:" + lane)
    if expected_account_digests[LANES[0]] == expected_account_digests[LANES[1]]:
        raise ValueError("POSTJOURNAL_CROSS_LANE_ACCOUNT_DIGEST_ALIAS")
    if (type(original_roots) is not dict or set(original_roots) != {
            "native_roots_verified", "empty_roots", "coordination_nonempty",
            "source_projection_report_control_custody_empty",
        } or original_roots["native_roots_verified"] != 12
            or original_roots["empty_roots"] != 10
            or original_roots["coordination_nonempty"] != 2
            or original_roots["source_projection_report_control_custody_empty"] is not True):
        raise ValueError("POSTJOURNAL_ORIGINAL_NATIVE_ROOTS_NOT_EXACT_INITIAL_CUT")
    if (type(original_activation) is not dict or set(original_activation) != {
            "origin", "actions", "accounts", "original_only"}
            or original_activation["origin"] != "LOCAL_OPERATOR"
            or original_activation["actions"] != list(ALLOWED_ACTIONS)
            or original_activation["accounts"] != expected_account_digests
            or original_activation["original_only"] is not True):
        raise ValueError("POSTJOURNAL_INITIALIZATION_APPROVAL_CHANGED")
    if (type(original_failure) is not dict or set(original_failure) != {
            "phase", "error", "replay_reserved"}
            or original_failure["phase"] != PHASE
            or original_failure["error"] != FAILED
            or original_failure["replay_reserved"] is not True):
        raise ValueError("POSTJOURNAL_EXACT_FIRST_ATTEMPT_FAILURE_REQUIRED")

    # No D->F resume or post-inception writer-generation acceptance:
    # original process identity is gone; old journals bind that old process.
    # Any future recovery must have independent new native cohort authority
    # and explicitly prove what happens to this immutable historical cut.
    return strict(body({
        "schema": SCHEMA,
        "status": "ORIGINAL_R26_INTERRUPTED_AFTER_TWO_JOURNALS_BEFORE_ACCOUNT_INCEPTION",
        "original_coordination_journals_verified": 2,
        "original_financial_account_publications": 0,
        "original_empty_noncoordination_roots": 10,
        "original_writer_excluded": True,
        "same_epoch_initialization_replay_permitted": False,
        "old_operator_approval_reusable_for_successor": False,
        "old_journal_overwrite_or_delete_permitted": False,
        "new_activation_issued": False,
        "new_financial_account_issued": False,
        "paper_start_authorized": False,
        "live_trading_authorized": False,
        "next_required": NEXT,
    }))
