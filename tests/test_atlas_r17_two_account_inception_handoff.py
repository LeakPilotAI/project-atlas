"""Current selected R17 two independent PAPER account drafts: never authority."""
from __future__ import annotations

from copy import deepcopy

import pytest
from app.services.paper_daily_report import validate_scope
from app.services.paper_financial_replay import digest, validate_manifest
from app.services.perp_operational_contract import (
    validate_enrollment as validate_hl,
)
from app.services.quality_dips_autonomous_enrollment import (
    validate_enrollment as validate_qd,
)

from scripts.observation_runtime import atlas_r17_two_account_inception_handoff as r17
from scripts.observation_runtime.atlas_r15_two_account_enrollment_handoff import (
    build_handoff as r15_build,
)
from scripts.observation_runtime.atlas_r15_two_account_enrollment_handoff import (
    legacy_proposal,
)
from scripts.observation_runtime.atlas_r17_alpaca_iex_rest_probe import (
    require_selected_r17_nonfinancial,
)
from scripts.observation_runtime.personal_existing_native_resource_evidence import (
    inspect_two_lane_native_roots,
)


@pytest.fixture(scope="module")
def source():
    roots = inspect_two_lane_native_roots()
    before = deepcopy(roots)
    selected = require_selected_r17_nonfinancial()
    historical = r15_build(
        legacy_proposal(), selected=r17.historical_r15_ref(),
        roots=roots,
    )
    out = r17.rebind(original=historical, selected=selected, roots=roots)
    assert inspect_two_lane_native_roots() == before
    return historical, selected, roots, out


def test_real_selected_revision16_original_r15_and_native_roots(source):
    _, selected, roots, out = source
    assert selected["release"] == r17.SOURCE
    assert selected["artifact_digest"] == r17.ARTIFACT
    assert out["schema"] == r17.SCHEMA
    assert out["native_revision"] == 16
    assert out["native_head"] == r17.HEAD
    assert out["original_r15_handoff_digest"] == r17.HISTORICAL_R15_HANDOFF_DIGEST
    assert out["original_historical_unaccepted_v5_sha256"] == r17.LEGACY_SHA
    assert out["original_root_count"] == 12
    assert roots["all_twelve_distinct_and_empty"] is True
    assert set(out["accounts"]) == set(r17.LANES)
    assert out["financial_writer_enrollments_accepted"] == 0
    assert out["native_account_fs1_fs3_inceptions_published"] == 0
    assert out["provider_rights_accepted"] is False
    assert out["financial_issuer_present"] is False
    assert out["paper_start_authorized"] is False
    assert out["live_trading_authorized"] is False
    assert out["filesystem_writes"] == 0
    assert out["network_requests"] == 0


def test_both_native_account_drafts_remain_deliberately_unaccepted(source):
    historical, _, roots, out = source
    real_ids = set()
    for lane in r17.LANES:
        x = out["accounts"][lane]
        manifest = x["provisional_parameters_historical_open_time"]
        enrollment = x["provisional_enrollment_unaccepted"]
        scope = x["provisional_report_scope_unaccepted"]
        assert manifest["release"] == r17.ARTIFACT
        assert manifest["opening_cash"] == "1000"
        assert manifest["timezone"] == (
            "America/New_York" if lane == "QUALITY_DIPS" else "UTC"
        )
        assert manifest["opened_at"] == historical["accounts"][lane][
            "provisional_r15_parameters"]["opened_at"]
        assert enrollment["writers"] is None
        assert enrollment["acceptance_id"] is None
        assert enrollment["release_digest"] == r17.ARTIFACT
        assert enrollment["inception_digest"] == digest(manifest)
        assert scope["policy_digest"] == digest(manifest)
        assert x["provisional_manifest_digest"] == digest(manifest)
        assert x["operator_account_approval_unissued"] is True
        assert x["opening_time_historical_not_currently_accepted"] is True
        assert x["fees_historical_not_currently_accepted"] is True
        assert x["account_fs1_fs3_not_published"] is True
        assert x["market_source_rights_unaccepted"] is True
        validate_manifest(manifest)
        validate_scope(scope, manifest)
        with pytest.raises(ValueError):
            (validate_qd if lane == "QUALITY_DIPS" else validate_hl)(enrollment)
        for root in enrollment["resources"].values():
            assert tuple(root["native_id"]) not in real_ids
            real_ids.add(tuple(root["native_id"]))
    assert len(real_ids) == 12
    assert inspect_two_lane_native_roots() == roots


def test_current_real_selected_16_chain_historical_rev14_is_verified():
    reference = r17.historical_r15_ref()
    assert reference["revision"] == 14
    assert reference["selected_native_head"] == r17.R15_HEAD
    assert reference["installed_receipt_sha256"] == r17.R15_RECEIPT_SHA
    assert reference["financial_authority"] is False
    assert reference["independent_live_financial_clock_lease_accepted"] is False


def test_pure_rebound_does_not_modify_original_or_current_native_evidence(source):
    original, selected, roots, expected = source
    snapshot = deepcopy((original, selected, roots))
    assert r17.rebind(original=original, selected=selected, roots=roots) == expected
    assert r17.rebind(original=original, selected=selected, roots=roots) == expected
    assert (original, selected, roots) == snapshot


@pytest.mark.parametrize("mutation", [
    "foreign_release", "wrong_artifact", "changed_history", "fake_account_acceptance",
    "fake_fs1_fs3_ack", "fake_original_paper_start", "wrong_root_count",
    "wrong_root_native_id", "missing_root", "nonempty_real_root",
    "writer_pid_invented", "qd_acceptance_id_invented", "wrong_held_release",
    "historical_opening_cash", "historical_fee_policy", "historical_root_path",
    "historical_account_alias", "historical_scope_changed",
    "historical_open_time_changed", "changed_historical_release",
])
def test_mutated_source_cannot_become_accepted_financial_inception(source, mutation):
    original, selected, roots, _ = deepcopy(source)
    if mutation == "foreign_release":
        selected["release"] = "foreign"
    elif mutation == "wrong_artifact":
        selected["artifact_digest"] = "f" * 64
    elif mutation == "changed_history":
        original["status"] = "ACCEPTED"
    elif mutation == "fake_account_acceptance":
        original["account_enrollment_accepted"] = True
    elif mutation == "fake_fs1_fs3_ack":
        original["both_financial_inceptions_published"] = True
    elif mutation == "fake_original_paper_start":
        original["paper_start_authorized"] = True
    elif mutation == "wrong_root_count":
        roots["native_root_total"] = 11
    elif mutation == "wrong_root_native_id":
        roots["lanes"]["QUALITY_DIPS"]["roots"]["source"]["native_id"] = [8, 8, 8]
    elif mutation == "missing_root":
        roots["lanes"]["HYPERLIQUID"]["roots"].pop("report")
    elif mutation == "nonempty_real_root":
        roots["all_twelve_distinct_and_empty"] = False
    elif mutation == "writer_pid_invented":
        original["accounts"]["QUALITY_DIPS"][
            "provisional_r15_native_enrollment_unaccepted"]["writers"] = {"source": 5}
    elif mutation == "qd_acceptance_id_invented":
        original["accounts"]["QUALITY_DIPS"][
            "provisional_r15_native_enrollment_unaccepted"]["acceptance_id"] = "fake"
    elif mutation == "wrong_held_release":
        original["accounts"]["HYPERLIQUID"][
            "provisional_r15_parameters"]["release"] = "0" * 64
    elif mutation == "historical_opening_cash":
        original["accounts"]["QUALITY_DIPS"][
            "provisional_r15_parameters"]["opening_cash"] = "10000"
    elif mutation == "historical_fee_policy":
        original["accounts"]["QUALITY_DIPS"][
            "provisional_r15_parameters"]["fees_bps"] = "99"
    elif mutation == "historical_root_path":
        original["accounts"]["QUALITY_DIPS"][
            "provisional_r15_native_enrollment_unaccepted"]["resources"][
                "source"]["path"] = r"C:\Fake"
    elif mutation == "historical_account_alias":
        original["accounts"]["HYPERLIQUID"][
            "provisional_r15_native_enrollment_unaccepted"]["account_id"] = (
                original["accounts"]["QUALITY_DIPS"][
                    "provisional_r15_native_enrollment_unaccepted"]["account_id"]
            )
    elif mutation == "historical_scope_changed":
        original["accounts"]["HYPERLIQUID"][
            "provisional_report_scope_unaccepted"]["timezone"] = "America/Chicago"
    elif mutation == "historical_open_time_changed":
        original["accounts"]["QUALITY_DIPS"][
            "provisional_r15_parameters"]["opened_at"] += 1
    elif mutation == "changed_historical_release":
        original["selected_r15_artifact_digest"] = "a" * 64
    with pytest.raises((ValueError, KeyError, TypeError)):
        r17.rebind(original=original, selected=selected, roots=roots)


def test_exact_public_inspect_has_no_effect_and_does_not_mint_accounts(source):
    out = r17.inspect()
    assert out == source[3]
    assert out["native_account_fs1_fs3_inceptions_published"] == 0
    assert out["financial_writer_enrollments_accepted"] == 0
    assert out["paper_start_authorized"] is False
