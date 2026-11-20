"""Selected R18+ historical draft readback; NEVER a financial enrollment."""
from __future__ import annotations

from copy import deepcopy

import pytest
from app.services.paper_daily_report import validate_scope
from app.services.paper_financial_replay import digest, validate_manifest
from app.services.perp_operational_contract import validate_enrollment as validate_hl
from app.services.quality_dips_autonomous_enrollment import (
    validate_enrollment as validate_qd,
)

from scripts.observation_runtime import (
    personal_current_selected_dual_account_draft as handoff,
)
from scripts.observation_runtime.atlas_r15_two_account_enrollment_handoff import (
    build_handoff,
    legacy_proposal,
)
from scripts.observation_runtime.personal_existing_native_resource_evidence import (
    inspect_two_lane_native_roots,
)


@pytest.fixture(scope="module")
def original_selected():
    # Real Windows original selected record & immutable R18 installed files.
    selected, head, historic = handoff.selected_and_historical()
    roots = inspect_two_lane_native_roots()
    before = deepcopy(roots)
    original = build_handoff(
        legacy_proposal(), selected=historic, roots=roots)
    assert inspect_two_lane_native_roots() == before
    return original, selected, head, roots


def test_selected_r18_native_chain_and_accounts_stay_only_drafts(original_selected):
    original, selected, head, roots = original_selected
    report = handoff.rebind(
        original=original, selected=selected, head=head, roots=roots)
    assert report["schema"] == handoff.SCHEMA
    assert report["native_revision"] == 17
    assert report["status"] == "TWO_CURRENT_RELEASE_ACCOUNT_DRAFTS_UNACCEPTED_NO_FINANCE"
    assert report["selected_source_commit"] == (
        "1389683b2a38a9accc0381c207d36abb2ce21e11")
    assert report["selected_artifact_digest"] == (
        "66ce29256b5230e9abfee076ec73bef36ff69d734c21bc69a8e092dc7b4c72e3")
    assert report["original_native_root_count"] == 12
    assert roots["all_twelve_distinct_and_empty"] is True
    assert report["native_account_inceptions_published"] == 0
    assert report["operator_financial_approval_accepted"] is False
    assert report["provider_rights_accepted"] is False
    assert report["financial_issuer_present"] is False
    assert report["paper_start_authorized"] is False
    assert report["live_trading_authorized"] is False
    assert report["filesystem_writes"] == 0
    assert report["network_requests"] == 0
    assert set(report["accounts"]) == {"QUALITY_DIPS", "HYPERLIQUID"}
    assert len(report["missing_real_financial_prerequisites"]) >= 6


def test_true_original_historical_drafts_rebind_both_fs3_profiles(
        original_selected):
    original, selected, head, roots = original_selected
    input_copy = deepcopy((original, selected, head, roots))
    report = handoff.rebind(
        original=original, selected=selected, head=head, roots=roots)
    real_native_ids = set()
    for lane in handoff.LANES:
        row = report["accounts"][lane]
        params = row["unaccepted_historical_parameters"]
        enrollment = row["unaccepted_historical_enrollment"]
        scope = row["unaccepted_historical_report_scope"]
        assert params["release"] == selected["artifact_digest"]
        assert params["opening_cash"] == "1000"
        assert params["opened_at"] == original["accounts"][lane][
            "provisional_r15_parameters"]["opened_at"]
        assert enrollment["release_digest"] == selected["artifact_digest"]
        assert enrollment["inception_digest"] == digest(params)
        assert enrollment["writers"] is None
        assert enrollment["acceptance_id"] is None
        assert scope["policy_digest"] == digest(params)
        assert row["fee_rights_unreviewed"] is True
        assert row["opening_timestamp_historical_stale"] is True
        assert row["writer_process_not_accepted"] is True
        assert row["operator_approval_unissued"] is True
        assert row["operational_market_rights_unaccepted"] is True
        validate_manifest(params)
        validate_scope(scope, params)
        with pytest.raises((ValueError, TypeError)):
            (validate_qd if lane == "QUALITY_DIPS" else validate_hl)(enrollment)
        for role in handoff.ROLES:
            n = tuple(enrollment["resources"][role]["native_id"])
            assert n not in real_native_ids
            real_native_ids.add(n)
    assert len(real_native_ids) == 12
    assert (original, selected, head, roots) == input_copy
    assert inspect_two_lane_native_roots() == roots


@pytest.mark.parametrize("mutation", [
    "forged_historic_acceptance", "claimed_inception", "forged_paper_start",
    "foreign_selected_source", "selected_head_mismatch", "wrong_revision",
    "wrong_root_count", "nonempty_original_root", "foreign_native_root",
    "duplicated_root", "foreign_historical_release", "changed_opening_time",
    "changed_fee", "fake_writer", "fake_operator_approval", "fake_provider_rights",
    "changed_report_scope", "duplicate_account_id", "duplicate_epoch",
])
def test_pure_draft_malformation_never_becomes_financially_accepted(
        original_selected, mutation):
    original, selected, head, roots = deepcopy(original_selected)
    q = original["accounts"]["QUALITY_DIPS"]
    h = original["accounts"]["HYPERLIQUID"]
    if mutation == "forged_historic_acceptance":
        original["account_enrollment_accepted"] = True
    elif mutation == "claimed_inception":
        original["both_financial_inceptions_published"] = True
    elif mutation == "forged_paper_start":
        original["paper_start_authorized"] = True
    elif mutation == "foreign_selected_source":
        selected["release"] = handoff.R17_RELEASE
    elif mutation == "selected_head_mismatch":
        head["selected"]["artifact_digest"] = "f" * 64
    elif mutation == "wrong_revision":
        head["revision"] = 16
    elif mutation == "wrong_root_count":
        roots["native_root_total"] = 11
    elif mutation == "nonempty_original_root":
        roots["all_twelve_distinct_and_empty"] = False
    elif mutation == "foreign_native_root":
        roots["lanes"]["HYPERLIQUID"]["roots"]["report"]["native_id"] = [1, 2, 3]
    elif mutation == "duplicated_root":
        roots["lanes"]["QUALITY_DIPS"]["roots"]["source"]["native_id"] = (
            roots["lanes"]["HYPERLIQUID"]["roots"]["source"]["native_id"])
    elif mutation == "foreign_historical_release":
        q["provisional_r15_parameters"]["release"] = "f" * 64
    elif mutation == "changed_opening_time":
        q["provisional_r15_parameters"]["opened_at"] += 1
    elif mutation == "changed_fee":
        h["provisional_r15_parameters"]["perp_policy"]["taker_bps"] = "99"
    elif mutation == "fake_writer":
        q["provisional_r15_native_enrollment_unaccepted"]["writers"] = {}
    elif mutation == "fake_operator_approval":
        q["provisional_r15_native_enrollment_unaccepted"]["acceptance_id"] = "fake"
    elif mutation == "fake_provider_rights":
        h["operational_source_rights_accepted"] = True
    elif mutation == "changed_report_scope":
        h["provisional_report_scope_unaccepted"]["timezone"] = "America/Chicago"
    elif mutation == "duplicate_account_id":
        h["provisional_r15_native_enrollment_unaccepted"]["account_id"] = (
            q["provisional_r15_native_enrollment_unaccepted"]["account_id"])
    elif mutation == "duplicate_epoch":
        h["provisional_r15_native_enrollment_unaccepted"]["epoch"] = (
            q["provisional_r15_native_enrollment_unaccepted"]["epoch"])
    with pytest.raises((ValueError, TypeError, KeyError)):
        handoff.rebind(
            original=original, selected=selected,
            head=head, roots=roots)
