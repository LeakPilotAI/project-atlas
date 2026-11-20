"""Original native PAPER commissioning dependency map, planning only.

This corrects a real sequencing trap in the legacy 12-check read-only preview:
NativeOriginalTwoJournalPreinceptionPermit admits ONLY the two coordination
initializations before activation; original later-release activation at
PREINCEPTION_COORDINATION_READY admits ONLY READ_ONLY plus
INITIALIZE_SIMULATED_ACCOUNTS; original QD source genesis requires the separate
CONNECT_APPROVED_DATA action which cannot be granted by that pre-inception
activation. Therefore two genuine simulated accounts and a post-inception
data activation MUST precede original QD source archive genesis.

This module NEVER produces an issuer, activation, grant, original receipt,
financial file, provider connection, order, or actual PAPER run.
"""
from __future__ import annotations

SCHEMA = "ATLAS_ORIGINAL_TWO_LANE_FINANCIAL_COMMISSIONING_ORDER_V2"

# Preconditions are conservative: genuine market-source evidence and policy
# review before any financial native writer, independent of the original
# library's narrower mechanical ability to create account journals.
#
# Stage D uses the separate preactivation, once-only
# NativeOriginalTwoJournalPreinceptionPermit (not a PAPER activation).
# Stage E requires exact preinception READ_ONLY+INITIALIZE actions.
# Stage G requires a NEW postinception activation with CONNECT_APPROVED_DATA.
# Stage J requires a verified STOP-FIRST action grant; G is not a trade grant.
STAGES = (
    (
        "A_PREACTIVATION_ORIGINAL_SOURCE_POLICY",
        (),
        (
            "Independently review real original QD research and valuation "
            "methodology, Alpaca IEX rights, HL funding/settlement/fees; no "
            "source publication, provider trade login or financial write"
        ),
    ),
    (
        "B_SELECTED_ORIGINAL_JOB_NATIVE_CLOCK",
        (),
        (
            "Retain original selected release and native Windows Job/process "
            "handles, all twelve distinct original financial root IDs, "
            "5+7 writer roster and actual independent version-safe UTC"
        ),
    ),
    (
        "C_BOTH_FRESH_ACCOUNT_MANIFESTS_AND_SCOPE",
        (
            "A_PREACTIVATION_ORIGINAL_SOURCE_POLICY",
            "B_SELECTED_ORIGINAL_JOB_NATIVE_CLOCK",
        ),
        (
            "Prepare two original enrolled PAPER-only manifests with exact "
            "$1000 USD QD and 1000 USDC HL, original 5+7 writer roles, "
            "selected release and fresh native clock; no journal write"
        ),
    ),
    (
        "D_ORIGINAL_TWO_COORDINATION_JOURNALS",
        (
            "C_BOTH_FRESH_ACCOUNT_MANIFESTS_AND_SCOPE",
            "B_SELECTED_ORIGINAL_JOB_NATIVE_CLOCK",
        ),
        (
            "Only with separately approved one-shot "
            "INITIALIZE_TWO_COORDINATION_JOURNALS_ONLY operator scope, "
            "publish and verify two original initial immutable journals; "
            "ten other original roots must remain EMPTY"
        ),
    ),
    (
        "E_PREINCEPTION_READ_AND_INITIALIZE_ACTIVATION",
        ("D_ORIGINAL_TWO_COORDINATION_JOURNALS",),
        (
            "Original selected native activation in "
            "PREINCEPTION_COORDINATION_READY MUST contain exactly "
            "READ_ONLY + INITIALIZE_SIMULATED_ACCOUNTS (no CONNECT, AUTO_PAPER, "
            "SHUTDOWN_FLATTEN or live orders)"
        ),
    ),
    (
        "F_ORIGINAL_TWO_SIMULATED_ACCOUNT_INCEPTIONS",
        (
            "E_PREINCEPTION_READ_AND_INITIALIZE_ACTIVATION",
            "D_ORIGINAL_TWO_COORDINATION_JOURNALS",
        ),
        (
            "Original in-process issuer factory and two once-only native "
            "FS1/FS3 acknowledgements for $1000 USD Quality Dips and 1000 "
            "USDC Hyperliquid; owner enters INITIAL_READBACK_ONLY"
        ),
    ),
    (
        "G_POSTINCEPTION_DATA_ACTIVATION",
        ("F_ORIGINAL_TWO_SIMULATED_ACCOUNT_INCEPTIONS",),
        (
            "Issue/read back a DISTINCT original post-inception "
            "LOCAL_OPERATOR activation including CONNECT_APPROVED_DATA; "
            "do not reuse the preinception exact two-action record"
        ),
    ),
    (
        "H_QD_ORIGINAL_SOURCE_ARCHIVE_GENESIS",
        (
            "G_POSTINCEPTION_DATA_ACTIVATION",
            "A_PREACTIVATION_ORIGINAL_SOURCE_POLICY",
        ),
        (
            "Only now invoke the original NativePersonalSourceInstallAuthority "
            "with accepted CONNECT_APPROVED_DATA and exact native source "
            "root/first image; independently read back original immutable ACK"
        ),
    ),
    (
        "I_ORIGINAL_CURRENT_QD_SOURCE_PUBLICATION",
        (
            "H_QD_ORIGINAL_SOURCE_ARCHIVE_GENESIS",
            "A_PREACTIVATION_ORIGINAL_SOURCE_POLICY",
        ),
        (
            "Original installed operator-owned current QD issuer with "
            "authenticated and independently checked upstream provenance, "
            "current fresh quote/valuation policy and exact native CAS "
            "readback; verified multi-epoch rollover needed for 30-second "
            "source freshness beyond 127 native publications; no synthetic "
            "receipt or digest-as-issuer"
        ),
    ),
    (
        "J_POSTINCEPTION_PAPER_STOP_ACTIVATION",
        (
            "I_ORIGINAL_CURRENT_QD_SOURCE_PUBLICATION",
            "F_ORIGINAL_TWO_SIMULATED_ACCOUNT_INCEPTIONS",
        ),
        (
            "Independently approved postinception action scope for "
            "READ_ONLY, AUTO_PAPER and SHUTDOWN_FLATTEN, native activation "
            "identity/clock, accepted QD and HL financial input rights"
        ),
    ),
    (
        "K_ORIGINAL_STOP_FIRST_FINANCIAL_RUNTIME",
        (
            "J_POSTINCEPTION_PAPER_STOP_ACTIVATION",
            "I_ORIGINAL_CURRENT_QD_SOURCE_PUBLICATION",
        ),
        (
            "Verify both genuine current financial source cuts, original "
            "owned Stop-first desktop runtime, simulated flatten, durable "
            "financial ACK and deterministic crash/restart reconciliation"
        ),
    ),
    (
        "L_EXTENDED_SUPERVISED_FORWARD_PAPER",
        ("K_ORIGINAL_STOP_FIRST_FINANCIAL_RUNTIME",),
        (
            "Independently accept real market-hours QD plus 24/7 HL "
            "supervised multi-session PAPER runs and extended soak. No "
            "release/code-only or test fixture can substitute for this"
        ),
    ),
)

# PAPER production readiness means being ready to START supervised PAPER.
# Extended performance is post-PAPER evidence for potential future LIVE review.
# It must NOT become a prerequisite to starting PAPER itself.
PAPER_PRELAUNCH_STAGES = tuple(item[0] for item in STAGES[:-1])
POST_PAPER_VALIDATION_STAGES = ("L_EXTENDED_SUPERVISED_FORWARD_PAPER",)

LEGACY_READONLY_ONLY = frozenset((
    "OPERATIONAL_QD_SOURCE_PUBLICATION",
    "FINANCIAL_INCEPTION",
    "RUNTIME_AUTHORIZATION",
))


def plan(*, authentic_native_accepted=None, legacy_preflight=None):
    """Show dependencies, never turn caller assertions into original authority.

    Even a fabricated full list of accepted stage names MUST NOT grant
    a financial effect; only authentic installed native issuer/clock/owner/Stop
    classes may establish their own verified rights elsewhere.
    """
    if authentic_native_accepted is None:
        authentic_native_accepted = ()
    names = tuple(x[0] for x in STAGES)
    if (type(authentic_native_accepted) not in (tuple, list)
            or any(type(v) is not str or v not in names for v in authentic_native_accepted)
            or len(set(authentic_native_accepted)) != len(authentic_native_accepted)):
        raise ValueError("ATLAS_COMMISSIONING_AUTHENTIC_STAGE_NAMES_REQUIRED")
    if legacy_preflight is not None:
        if (type(legacy_preflight) is not dict
                or legacy_preflight.get("schema") != "ATLAS_QD_COMMISSIONING_PREFLIGHT_V1"
                or legacy_preflight.get("financial_mutations") is not False
                or legacy_preflight.get("live_orders") is not False
                or legacy_preflight.get("pilot_started") is not False
                or type(legacy_preflight.get("checks")) is not list):
            raise ValueError("ATLAS_COMMISSIONING_EXACT_READONLY_PREFLIGHT_REQUIRED")
        checks = legacy_preflight["checks"]
        keys = [x.get("check") for x in checks if type(x) is dict]
        if (len(keys) != len(checks) or len(set(keys)) != len(keys)
                or any(type(x) is not dict or x.get("status") not in ("PASS", "BLOCKED")
                       for x in checks)
                or not LEGACY_READONLY_ONLY <= set(keys)):
            raise ValueError("ATLAS_COMMISSIONING_LEGACY_PREFLIGHT_MALFORMED")
    accepted = set(authentic_native_accepted)
    rows = []
    for name, dependencies, action in STAGES:
        if name in accepted and not set(dependencies) <= accepted:
            raise ValueError("ATLAS_COMMISSIONING_OUT_OF_ORDER_NATIVE_STAGE_CLAIM")
        blocked = [dep for dep in dependencies if dep not in accepted]
        rows.append({
            "stage": name,
            "requires": list(dependencies),
            "dependency_ready": not blocked,
            "missing_upstream": blocked,
            "observed_accepted": name in accepted,
            "lifecycle": (
                "PAPER_COMMISSIONING_PRELAUNCH"
                if name in PAPER_PRELAUNCH_STAGES
                else "POST_PAPER_LIVE_ELIGIBILITY_EVALUATION"
            ),
            "next_original_evidence": action,
        })
    return {
        "schema": SCHEMA,
        "status": "NONFINANCIAL_DEPENDENCY_PLAN_ONLY",
        "stages": rows,
        "claimed_external_prerequisites": len(accepted),
        "stages_without_claimed_proof": len(rows) - len(accepted),
        # These are user-supplied stage claims, NOT native financial proofs.
        "prelaunch_stage_count": len(PAPER_PRELAUNCH_STAGES),
        "prelaunch_stages_without_claimed_proof": sum(
            name not in accepted for name in PAPER_PRELAUNCH_STAGES
        ),
        "post_paper_evaluation_stage_count": len(POST_PAPER_VALIDATION_STAGES),
        "post_paper_evaluation_stages_without_claimed_proof": sum(
            name not in accepted for name in POST_PAPER_VALIDATION_STAGES
        ),
        "months_of_paper_required_before_starting_paper": False,
        "months_of_paper_required_before_considering_live": True,
        "next_possible_stages": [
            x["stage"] for x in rows
            if x["dependency_ready"] and not x["observed_accepted"]
        ],
        "legacy_preflight_financial_rejections_are_nonauthorizing": True,
        "initial_two_journals_precede_account_activation": True,
        "initial_exact_two_action_activation_precedes_simulated_inception": True,
        "source_archive_genesis_requires_postinception_data_activation": True,
        "preactivation_research_is_not_native_source_publication": True,
        "postinception_source_activation_is_not_stop_or_paper_authority": True,
        "claimed_stages_are_not_original_native_proof": True,
        "independent_financial_start_review_accepted": False,
        "financial_native_files_written": False,
        "paper_startup_authorized": False,
        "live_trading_authorized": False,
    }
