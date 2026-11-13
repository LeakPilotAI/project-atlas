"""Original R20+ native phase-order tests; entirely synthetic observations."""
from __future__ import annotations

import copy

import pytest

from scripts.observation_runtime import atlas_paper_actual_commissioning_order as stages


def _names():
    return [r[0] for r in stages.STAGES]


def _legacy():
    return {
        "schema": "ATLAS_QD_COMMISSIONING_PREFLIGHT_V1",
        "financial_mutations": False,
        "live_orders": False,
        "pilot_started": False,
        "checks": [
            {"check": name, "status": "BLOCKED"}
            for name in sorted(stages.LEGACY_READONLY_ONLY)
        ],
    }


def test_original_native_stage_order_has_no_cycle_and_separate_financial_actions():
    names = _names()
    assert len(names) == len(set(names)) == 12
    for i, (_, prerequisites, description) in enumerate(stages.STAGES):
        assert description and all(name in names[:i] for name in prerequisites)
    ix = names.index
    assert (
        ix("A_PREACTIVATION_ORIGINAL_SOURCE_POLICY")
        < ix("D_ORIGINAL_TWO_COORDINATION_JOURNALS")
        < ix("E_PREINCEPTION_READ_AND_INITIALIZE_ACTIVATION")
        < ix("F_ORIGINAL_TWO_SIMULATED_ACCOUNT_INCEPTIONS")
        < ix("G_POSTINCEPTION_DATA_ACTIVATION")
        < ix("H_QD_ORIGINAL_SOURCE_ARCHIVE_GENESIS")
        < ix("I_ORIGINAL_CURRENT_QD_SOURCE_PUBLICATION")
        < ix("J_POSTINCEPTION_PAPER_STOP_ACTIVATION")
        < ix("K_ORIGINAL_STOP_FIRST_FINANCIAL_RUNTIME")
        < ix("L_EXTENDED_SUPERVISED_FORWARD_PAPER")
    )
    assert "G_POSTINCEPTION_DATA_ACTIVATION" in stages.STAGES[ix(
        "H_QD_ORIGINAL_SOURCE_ARCHIVE_GENESIS"
    )][1]
    assert "D_ORIGINAL_TWO_COORDINATION_JOURNALS" in stages.STAGES[ix(
        "E_PREINCEPTION_READ_AND_INITIALIZE_ACTIVATION"
    )][1]
    assert "F_ORIGINAL_TWO_SIMULATED_ACCOUNT_INCEPTIONS" in stages.STAGES[ix(
        "G_POSTINCEPTION_DATA_ACTIVATION"
    )][1]


def test_planning_legacy_readonly_is_no_financial_grant():
    old = _legacy()
    frozen = copy.deepcopy(old)
    p = stages.plan(legacy_preflight=old)
    assert old == frozen
    assert p["schema"] == stages.SCHEMA
    assert p["stages_without_claimed_proof"] == 12
    assert p["claimed_external_prerequisites"] == 0
    assert p["status"] == "NONFINANCIAL_DEPENDENCY_PLAN_ONLY"
    assert p["next_possible_stages"] == [
        "A_PREACTIVATION_ORIGINAL_SOURCE_POLICY",
        "B_SELECTED_ORIGINAL_JOB_NATIVE_CLOCK",
    ]
    assert p["source_archive_genesis_requires_postinception_data_activation"] is True
    assert p["initial_two_journals_precede_account_activation"] is True
    assert p["initial_exact_two_action_activation_precedes_simulated_inception"] is True
    assert p["preactivation_research_is_not_native_source_publication"] is True
    assert p["postinception_source_activation_is_not_stop_or_paper_authority"] is True
    for field in (
        "financial_native_files_written",
        "paper_startup_authorized",
        "live_trading_authorized",
        "independent_financial_start_review_accepted",
    ):
        assert p[field] is False


@pytest.mark.parametrize("bad", [
    "A_PREACTIVATION_ORIGINAL_SOURCE_POLICY", [None], [True], [""],
    ["FAKE_PAPER_APPROVED"],
    ["B_SELECTED_ORIGINAL_JOB_NATIVE_CLOCK", "B_SELECTED_ORIGINAL_JOB_NATIVE_CLOCK"],
    [{"stage": "A_PREACTIVATION_ORIGINAL_SOURCE_POLICY"}],
])
def test_untrusted_claimed_stage_form_never_authorizes(bad):
    with pytest.raises(ValueError, match="AUTHENTIC_STAGE_NAMES_REQUIRED"):
        stages.plan(authentic_native_accepted=bad)


@pytest.mark.parametrize("prefix_count", range(1, 12))
def test_no_downstream_stage_can_be_claimed_without_prerequisites(prefix_count):
    accepted = _names()[:prefix_count]
    later = _names()[prefix_count:]
    for name in later:
        prerequisites = next(deps for stage, deps, _ in stages.STAGES if stage == name)
        if not set(prerequisites) <= set(accepted):
            with pytest.raises(ValueError, match="OUT_OF_ORDER_NATIVE_STAGE_CLAIM"):
                stages.plan(authentic_native_accepted=accepted + [name])


def test_even_all_claimed_stages_do_not_issue_a_financial_grant():
    p = stages.plan(authentic_native_accepted=_names())
    assert p["stages_without_claimed_proof"] == 0
    assert p["next_possible_stages"] == []
    assert p["claimed_external_prerequisites"] == len(stages.STAGES)
    assert p["claimed_stages_are_not_original_native_proof"] is True
    for field in (
        "independent_financial_start_review_accepted",
        "financial_native_files_written",
        "paper_startup_authorized",
        "live_trading_authorized",
    ):
        assert p[field] is False


@pytest.mark.parametrize("damage", [
    "schema", "financial_mutations", "live_orders", "pilot_started",
    "missing_checks", "duplicate_check", "wrong_status", "missing_source",
])
def test_bad_legacy_preflight_cannot_authenticate_paper_activation(damage):
    old = _legacy()
    if damage == "schema":
        old["schema"] = "OPERATIONAL_REVIEW"
    elif damage == "financial_mutations":
        old["financial_mutations"] = True
    elif damage == "live_orders":
        old["live_orders"] = True
    elif damage == "pilot_started":
        old["pilot_started"] = True
    elif damage == "missing_checks":
        old.pop("checks")
    elif damage == "duplicate_check":
        old["checks"].append(copy.deepcopy(old["checks"][0]))
    elif damage == "wrong_status":
        old["checks"][0]["status"] = "ACCEPTED"
    else:
        old["checks"] = [
            v for v in old["checks"]
            if v["check"] != "OPERATIONAL_QD_SOURCE_PUBLICATION"
        ]
    with pytest.raises(ValueError, match="EXACT_READONLY_PREFLIGHT|LEGACY_PREFLIGHT_MALFORMED"):
        stages.plan(legacy_preflight=old)


def test_fully_reviewed_research_is_not_source_publication_or_account_inception():
    p = stages.plan(
        authentic_native_accepted=["A_PREACTIVATION_ORIGINAL_SOURCE_POLICY"],
        legacy_preflight=_legacy(),
    )
    assert p["next_possible_stages"] == ["B_SELECTED_ORIGINAL_JOB_NATIVE_CLOCK"]
    assert all(row["observed_accepted"] is False
               for row in p["stages"] if row["stage"] not in
               ("A_PREACTIVATION_ORIGINAL_SOURCE_POLICY",))
    assert p["paper_startup_authorized"] is False


def test_source_pub_cannot_be_declared_before_second_original_activation():
    prefixes = [
        "A_PREACTIVATION_ORIGINAL_SOURCE_POLICY",
        "B_SELECTED_ORIGINAL_JOB_NATIVE_CLOCK",
        "C_BOTH_FRESH_ACCOUNT_MANIFESTS_AND_SCOPE",
        "D_ORIGINAL_TWO_COORDINATION_JOURNALS",
        "E_PREINCEPTION_READ_AND_INITIALIZE_ACTIVATION",
        "F_ORIGINAL_TWO_SIMULATED_ACCOUNT_INCEPTIONS",
    ]
    with pytest.raises(ValueError, match="OUT_OF_ORDER_NATIVE_STAGE_CLAIM"):
        stages.plan(authentic_native_accepted=prefixes + [
            "H_QD_ORIGINAL_SOURCE_ARCHIVE_GENESIS"
        ])
    p = stages.plan(authentic_native_accepted=prefixes)
    assert p["next_possible_stages"] == ["G_POSTINCEPTION_DATA_ACTIVATION"]
    assert p["paper_startup_authorized"] is False


def test_proof_of_connect_data_does_not_equal_paper_stop_or_source_cas():
    claims = _names()[:7]
    p = stages.plan(authentic_native_accepted=claims)
    assert p["next_possible_stages"] == ["H_QD_ORIGINAL_SOURCE_ARCHIVE_GENESIS"]
    assert p["paper_startup_authorized"] is False
    assert p["live_trading_authorized"] is False



def test_actual_installed_phase_action_constants_do_not_conflict_with_plan():
    import inspect

    from scripts.observation_runtime.personal_activation_commission import (
        retain_activation_writer_guard,
    )
    from scripts.observation_runtime.personal_original_preinception_journal_permit import (
        ACTION as JOURNAL_ONLY_ACTION,
    )
    from scripts.observation_runtime.personal_original_preinception_journal_permit import (
        NativeOriginalTwoJournalPreinceptionPermit,
    )
    from scripts.observation_runtime.personal_selected_two_account_issuer_factory import (
        ACTIONS as INITIAL_ACCOUNT_ACTIONS,
    )
    from scripts.observation_runtime.personal_source_install_authority import (
        NativePersonalSourceInstallAuthority,
    )

    assert JOURNAL_ONLY_ACTION == "INITIALIZE_TWO_COORDINATION_JOURNALS_ONLY"
    assert INITIAL_ACCOUNT_ACTIONS == frozenset(
        ("READ_ONLY", "INITIALIZE_SIMULATED_ACCOUNTS")
    )
    permit = inspect.getsource(
        NativeOriginalTwoJournalPreinceptionPermit.publish_both_original_journals_once
    )
    assert "observe_preinception_coordination" in permit
    native_guard = inspect.getsource(retain_activation_writer_guard)
    assert "PREINCEPTION_COORDINATION_READY" in native_guard
    assert "READ_ONLY', 'INITIALIZE_SIMULATED_ACCOUNTS" in native_guard
    source_auth = inspect.getsource(NativePersonalSourceInstallAuthority._check)
    assert "CONNECT_APPROVED_DATA" in source_auth
    assert _names().index("G_POSTINCEPTION_DATA_ACTIVATION") > _names().index(
        "F_ORIGINAL_TWO_SIMULATED_ACCOUNT_INCEPTIONS"
    )



def test_months_forward_paper_are_postlaunch_live_evaluation_not_launch_gate():
    plan = stages.plan(legacy_preflight=_legacy())
    assert plan["prelaunch_stage_count"] == 11
    assert plan["prelaunch_stages_without_claimed_proof"] == 11
    assert plan["post_paper_evaluation_stage_count"] == 1
    assert plan["post_paper_evaluation_stages_without_claimed_proof"] == 1
    assert plan["months_of_paper_required_before_starting_paper"] is False
    assert plan["months_of_paper_required_before_considering_live"] is True
    assert plan["stages"][-1]["lifecycle"] == (
        "POST_PAPER_LIVE_ELIGIBILITY_EVALUATION"
    )
    assert all(row["lifecycle"] == "PAPER_COMMISSIONING_PRELAUNCH"
               for row in plan["stages"][:-1])
    assert plan["paper_startup_authorized"] is False


def test_11_unauthenticated_stage_claims_cannot_grant_paper_or_live():
    # Stage labels alone are not evidence. Distinguish the LIVE-review soak
    # from PAPER-commissioning obligations, without optimistic authorization.
    plan = stages.plan(authentic_native_accepted=list(stages.PAPER_PRELAUNCH_STAGES))
    assert plan["prelaunch_stages_without_claimed_proof"] == 0
    assert plan["post_paper_evaluation_stages_without_claimed_proof"] == 1
    assert plan["stages_without_claimed_proof"] == 1
    assert plan["next_possible_stages"] == ["L_EXTENDED_SUPERVISED_FORWARD_PAPER"]
    assert plan["claimed_stages_are_not_original_native_proof"] is True
    assert plan["independent_financial_start_review_accepted"] is False
    assert plan["paper_startup_authorized"] is False
    assert plan["live_trading_authorized"] is False
