"""Selected R16 nine-gate financial acceptance inventory, actual native-only.

No real gate is promoted merely by a selected code file, existing native
storage, staged account draft, pending operator JSON or parked owner Job.
"""
from __future__ import annotations

import copy

import pytest

from scripts.observation_runtime import (
    atlas_r16_nine_gate_evidence_inventory as report,
)
from scripts.observation_runtime.atlas_r16_selected_code_readback import (
    selected_code, inspect as selected_inspect,
)
from scripts.observation_runtime.atlas_r16_two_account_enrollment_handoff import (
    inspect as draft_inspect,
)
from scripts.observation_runtime.personal_existing_native_resource_evidence import (
    inspect_two_lane_native_roots,
)
from scripts.observation_runtime.personal_native_commissioning_inventory import (
    inspect as personal_inspect,
)
from scripts.observation_runtime.quality_dips_source_inventory import (
    inspect as qd_inspect,
)
from scripts.observation_runtime.hyperliquid_native_preflight import (
    inspect as hl_inspect,
)
from scripts.windows.atlas_paper_readiness_check import (
    inspect as desktop_inspect,
)


@pytest.fixture(scope="module")
def evidence():
    return {
        "selected": selected_code(),
        "readiness": selected_inspect(),
        "draft": draft_inspect(),
        "roots": inspect_two_lane_native_roots(),
        "personal": personal_inspect(),
        "qd": qd_inspect(),
        "hl": hl_inspect(),
        "desktop": desktop_inspect(root=report.ROOT),
    }


def test_actual_selected_r16_nine_gate_inventory_has_independent_scope(evidence):
    frozen = copy.deepcopy(evidence)
    v = report.evaluate(**evidence)
    assert evidence == frozen
    assert v["schema"] == report.SCHEMA
    assert v["decision"] == "NO_GO"
    assert v["source_release"] == "R16"
    assert v["selected_revision"] == 15
    assert v["selected_native_head"] == report.R16_HEAD
    assert v["selected_record_sha256"] == report.R16_RECORD_SHA
    assert v["selected_release_artifact_digest"] == report.ARTIFACT_DIGEST
    assert v["historical_r15_readback_used_for_current_selection"] is False
    assert v["unaccepted_two_account_draft_digest"] == report.PINNED_PROPOSAL_DIGEST
    assert v["native_original_empty_roots_verified"] == 12
    assert v["candidate_preconditions_present"] == 4
    assert v["candidate_screen_count"] == 10
    assert set(v["candidate_screen"]) == set(report.SCREENED)
    assert all(v["candidate_screen"][name] for name in report.SCREENED[:4])
    assert not any(v["candidate_screen"][name] for name in report.SCREENED[4:])
    assert v["independently_accepted_gate_count"] == 0
    assert v["independently_accepted_gate_total"] == 9
    assert len(v["financial_gates"]) == 9
    assert [g["gate"] for g in v["financial_gates"]] == list(report.GATES)
    assert len(v["missing_independent_financial_readbacks"]) == 20
    assert v["missing_independent_financial_readback_count"] == 20
    assert v["missing_independent_financial_readbacks"] == [
        token for gate in report.GATES for token in report.REQUIREMENTS[gate]]
    assert all(
        g["accepted"] is False
        and g["independent_readbacks_accepted"] == 0
        and g["code_or_review_only_draft_is_not_operational_acceptance"] is True
        and g["status"] == "BLOCKED_INDEPENDENT_FINANCIAL_ACCEPTANCE_MISSING"
        for g in v["financial_gates"]
    )
    assert v["financial_gate_issuer_present"] is False
    assert v["unsigned_operator_or_provider_json_can_authorize"] is False
    assert v["paper_start_authorized"] is False
    assert v["real_money_trading_authorized"] is False
    assert v["native_financial_account_writes"] == 0
    assert v["provider_requests"] == 0


def test_real_machine_readonly_r16_inventory_matches_individual_evidence(evidence):
    actual = report.inspect()
    assert actual == report.evaluate(**evidence)
    assert actual["source_release"] == "R16"
    assert actual["candidate_preconditions_present"] == 4
    assert actual["independently_accepted_gate_count"] == 0
    assert evidence["selected"]["selected_revision"] == 15
    assert evidence["roots"]["all_twelve_distinct_and_empty"] is True
    assert evidence["personal"]["native_activation_verified"] is False
    assert evidence["hl"]["provider_rights_and_current_market_data"] == (
        "NOT_INDEPENDENTLY_VERIFIED")


@pytest.mark.parametrize("section,key,value", [
    ("selected", "selected_revision", 14),
    ("selected", "selected_native_head", "0"*64),
    ("selected", "selected_native_record_sha256", "0"*64),
    ("selected", "selected_release", "0"*40),
    ("selected", "installed_artifact_digest", "0"*64),
    ("selected", "installed_receipt_sha256", "0"*64),
    ("selected", "financial_clock_operational_accepted", True),
    ("selected", "provider_source_operational_accepted", True),
    ("selected", "financial_writer_operational_accepted", True),
    ("selected", "paper_start_authorized", True),
    ("readiness", "decision", "GO"),
    ("readiness", "financial_operating_gates_independently_accepted", 1),
    ("readiness", "financial_writer_roles_enrolled", 12),
    ("readiness", "native_financial_account_inception_accepted", True),
    ("readiness", "independent_current_provider_rights_accepted", True),
    ("readiness", "financial_operating_gates_total", 8),
    ("draft", "status", "FINANCIAL_ACCOUNTS_ACCEPTED"),
    ("draft", "selected_native_revision", 14),
    ("draft", "selected_r16_artifact_digest", "f"*64),
    ("draft", "historical_r15_rebind_digest", "f"*64),
    ("draft", "native_original_empty_root_count_verified", 11),
    ("draft", "actual_financial_writer_roles_enrolled", 12),
    ("draft", "native_financial_inceptions_published", 2),
    ("draft", "accepted_financial_operating_gates", 1),
    ("draft", "financial_paper_start_authorized", True),
    ("roots", "native_root_total", 11),
    ("roots", "native_root_ids_verified", 11),
    ("roots", "existing_empty_root_namespaces", 11),
    ("roots", "all_twelve_distinct_and_empty", False),
    ("roots", "writer_ownership_verified", True),
    ("roots", "native_activation_record_verified", True),
    ("roots", "financial_inception_verified", True),
    ("roots", "paper_start_authorized", True),
    ("personal", "native_activation_verified", True),
    ("personal", "account_enrollment_verified", True),
    ("personal", "financial_inception_authorized", True),
    ("personal", "paper_start_authorized", True),
    ("qd", "operational_publication_verified", True),
    ("hl", "native_writer_ownership", "INDEPENDENTLY_VERIFIED"),
    ("hl", "provider_rights_and_current_market_data", "INDEPENDENTLY_VERIFIED"),
    ("hl", "hyperliquid_native_account_inception", "INDEPENDENTLY_VERIFIED"),
    ("hl", "paper_startup_authorized", True),
    ("desktop", "decision", "GO"),
    ("desktop", "paper_startup_authorized", True),
    ("desktop", "unverified_gate_count", 0),
])
def test_forged_live_financial_acceptance_or_selected_state_refused(evidence, section, key, value):
    altered = copy.deepcopy(evidence)
    altered[section][key] = value
    with pytest.raises((ValueError, TypeError, KeyError), match="R16_GATE_"):
        report.evaluate(**altered)


@pytest.mark.parametrize("damage", [
    "missing_qd_lane", "extra_hl_lane", "forged_account_balance",
    "duplicate_native_root", "mismatched_native_id", "native_root_occupied",
    "draft_writer_claim", "draft_acceptance_claim", "account_release_changed",
    "manifest_digest_forged", "recomputed_nested_manifest",
    "report_scope_changed", "wrong_enrollment_epoch",
    "missing_native_role", "unknown_role",
    "not_historical_timestamp", "provider_rights_claim",
    "fake_daily_soak", "fake_current_financial_issuer",
    "current_selected_code_promoted",
])
def test_r16_native_financial_draft_and_source_tampering_never_promotes_a_gate(evidence, damage):
    altered = copy.deepcopy(evidence)
    qd = altered["draft"]["accounts"]["QUALITY_DIPS"]
    hl = altered["draft"]["accounts"]["HYPERLIQUID"]
    qd_roots = altered["roots"]["lanes"]["QUALITY_DIPS"]["roots"]
    hl_roots = altered["roots"]["lanes"]["HYPERLIQUID"]["roots"]
    if damage == "missing_qd_lane":
        altered["draft"]["accounts"].pop("QUALITY_DIPS")
    elif damage == "extra_hl_lane":
        altered["roots"]["lanes"]["MISSING"] = {}
    elif damage == "forged_account_balance":
        qd["provisional_r16_parameters"]["opening_cash"] = "10000"
    elif damage == "duplicate_native_root":
        hl_roots["source"]["native_id"] = qd_roots["source"]["native_id"][:]
    elif damage == "mismatched_native_id":
        qd["provisional_r16_enrollment_unaccepted"]["resources"][
            "report"]["native_id"] = [0, 0, 0]
    elif damage == "native_root_occupied":
        qd_roots["custody"]["existing_empty_namespace_verified"] = False
    elif damage == "draft_writer_claim":
        qd["provisional_r16_enrollment_unaccepted"]["writers"] = {"source": 123}
    elif damage == "draft_acceptance_claim":
        hl["provisional_r16_enrollment_unaccepted"]["acceptance_id"] = "FOREIGN"
    elif damage == "account_release_changed":
        hl["provisional_r16_enrollment_unaccepted"]["release_digest"] = "0"*64
    elif damage == "manifest_digest_forged":
        qd["provisional_r16_manifest_digest"] = "0"*64
    elif damage == "recomputed_nested_manifest":
        from app.services.paper_financial_replay import digest
        qd["provisional_r16_parameters"]["opening_cash"] = "10000"
        fresh = digest(qd["provisional_r16_parameters"])
        qd["provisional_r16_manifest_digest"] = fresh
        qd["provisional_r16_enrollment_unaccepted"]["inception_digest"] = fresh
        qd["provisional_r16_report_scope_unaccepted"]["policy_digest"] = fresh
    elif damage == "report_scope_changed":
        hl["provisional_r16_report_scope_unaccepted"]["timezone"] = "Europe/London"
    elif damage == "wrong_enrollment_epoch":
        qd["provisional_r16_enrollment_unaccepted"]["epoch"] = "OTHER_EPOCH"
    elif damage == "missing_native_role":
        hl_roots.pop("coordination")
    elif damage == "unknown_role":
        qd["provisional_r16_enrollment_unaccepted"]["resources"]["NEW"] = {}
    elif damage == "not_historical_timestamp":
        qd["opening_timestamp_historical_not_current"] = False
    elif damage == "provider_rights_claim":
        hl["provider_source_rights_accepted"] = True
    elif damage == "fake_daily_soak":
        altered["readiness"]["months_long_soak_accepted"] = True
    elif damage == "fake_current_financial_issuer":
        altered["personal"]["ordinary_activation_file_candidates"] = [123]
    elif damage == "current_selected_code_promoted":
        altered["readiness"]["selected_code"]["financial_writer_operational_accepted"] = True
    with pytest.raises((ValueError, TypeError, KeyError), match="R16_GATE_"):
        report.evaluate(**altered)


def test_native_activation_file_candidate_alone_does_not_promote_any_gate(evidence):
    altered = copy.deepcopy(evidence)
    altered["personal"]["ordinary_activation_file_candidates"] = [
        "an-unaccepted-local-json-file"]
    v = report.evaluate(**altered)
    assert v["candidate_screen"]["PERSONAL_ACTIVATION_FILE_CANDIDATE_PRESENT"] is True
    assert v["candidate_preconditions_present"] == 5
    assert v["independently_accepted_gate_count"] == 0
    assert v["financial_gate_issuer_present"] is False
    assert v["paper_start_authorized"] is False


def test_manifest_draft_is_not_writer_enrollment_or_financial_account(evidence):
    from app.services.quality_dips_autonomous_enrollment import validate_enrollment as qd_enrollment
    from app.services.perp_operational_contract import validate_enrollment as hl_enrollment
    for lane, validator in (
        ("QUALITY_DIPS", qd_enrollment),
        ("HYPERLIQUID", hl_enrollment),
    ):
        account = evidence["draft"]["accounts"][lane]
        unaccepted = account["provisional_r16_enrollment_unaccepted"]
        with pytest.raises(ValueError):
            validator(unaccepted)
        assert unaccepted["writers"] is None
        assert unaccepted["acceptance_id"] is None
        assert account["financial_inception_published"] is False
