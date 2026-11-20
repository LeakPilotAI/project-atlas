"""The source-only structural prelaunch report never grants PAPER authority."""
from __future__ import annotations

import copy

import pytest

from scripts.observation_runtime import (
    atlas_selected_paper_prelaunch_evidence as preflight,
)

ORIGIN = {
    "schema": "ATLAS_NATIVE_SELECTED_FINANCIAL_ACTIVATION_SOURCE_BINDING_V1",
    "installed_source_and_process_path_bound": True,
    "selected_artifact_digest_bound": True,
    "financial_writer_lease_issued": False,
    "paper_start_authorized": False,
}
EMPTY = {
    "native_root_total": 12,
    "native_root_ids_verified": 12,
    "existing_empty_root_namespaces": 12,
    "all_twelve_distinct_and_empty": True,
}


@pytest.mark.parametrize("installed_watch,installed_epoch", [
    (False, False), (True, False), (False, True), (True, True),
])
def test_original_empty_financial_roots_are_not_a_financial_start_grant(
    installed_watch, installed_epoch,
):
    r = preflight._classify(
        origin=copy.deepcopy(ORIGIN),
        roots=copy.deepcopy(EMPTY),
        newer_watch=installed_watch,
        newer_epoch=installed_epoch,
    )
    assert r["schema"] == preflight.SCHEMA
    assert r["source_origin_native_verified"] is True
    assert r["native_original_root_count"] == 12
    assert r["native_empty_root_count"] == 12
    assert r["native_roots_preinception_empty"] is True
    assert r["native_original_preinception_journals_verified"] is False
    assert r["native_simulated_account_inceptions_verified"] is False
    assert r["postinception_operator_activation_verified"] is False
    assert r["new_watch_only_source_module_installed"] is installed_watch
    assert r["new_source_epoch_readback_module_installed"] is installed_epoch
    assert r["quality_dips_127_publication_rollover_operationally_accepted"] is False
    assert r["hyperliquid_signed_settlement_oracle_accepted"] is False
    assert r["paper_startup_authorized"] is False
    assert r["live_trading_authorized"] is False
    assert r["financial_journals_created_by_this_report"] is False
    assert r["legacy_checker_gate_count"] == 9
    assert r["legacy_checker_is_a_progress_percentage"] is False


@pytest.mark.parametrize("danger", [
    "populated_financial_root", "only_11_ids", "changed_root_total",
])
def test_original_nonempty_root_is_unknown_not_permission_to_retry(danger):
    roots = copy.deepcopy(EMPTY)
    if danger == "populated_financial_root":
        roots["existing_empty_root_namespaces"] = 11
        roots["all_twelve_distinct_and_empty"] = False
    elif danger == "only_11_ids":
        roots["native_root_ids_verified"] = 11
    else:
        roots["native_root_total"] = 11
    if danger == "populated_financial_root":
        r = preflight._classify(
            origin=copy.deepcopy(ORIGIN),
            roots=roots, newer_watch=True, newer_epoch=True,
        )
        assert "RECONCILIATION" in r["native_financial_state"]
        assert r["ready_to_issue_financial_first_journals"] is False
        assert r["paper_startup_authorized"] is False
    else:
        with pytest.raises(ValueError, match="EXACT_NATIVE_EVIDENCE"):
            preflight._classify(
                origin=copy.deepcopy(ORIGIN),
                roots=roots, newer_watch=True, newer_epoch=True,
            )


@pytest.mark.parametrize("damage", [
    "missing_origin", "wrong_origin_schema", "missing_native_bound",
    "missing_artifact_bound", "roots_missing", "bool_ids",
    "negative_empty", "too_many_empty", "fake_bool_watch",
    "fake_bool_epoch",
])
def test_untrusted_or_inconsistent_original_evidence_refused(damage):
    origin, roots = copy.deepcopy(ORIGIN), copy.deepcopy(EMPTY)
    watch, epoch = True, True
    if damage == "missing_origin":
        origin = {}
    elif damage == "wrong_origin_schema":
        origin["schema"] = "UNTRUSTED"
    elif damage == "missing_native_bound":
        origin["installed_source_and_process_path_bound"] = False
    elif damage == "missing_artifact_bound":
        origin["selected_artifact_digest_bound"] = False
    elif damage == "roots_missing":
        roots = {}
    elif damage == "bool_ids":
        roots["existing_empty_root_namespaces"] = True
    elif damage == "negative_empty":
        roots["existing_empty_root_namespaces"] = -1
    elif damage == "too_many_empty":
        roots["existing_empty_root_namespaces"] = 13
    elif damage == "fake_bool_watch":
        watch = "TRUE"
    else:
        epoch = "TRUE"
    with pytest.raises(ValueError, match="EXACT_NATIVE_EVIDENCE"):
        preflight._classify(
            origin=origin, roots=roots,
            newer_watch=watch, newer_epoch=epoch,
        )


def test_legacy_nine_gate_desktop_checker_is_not_a_live_acceptance_progress_score():
    from scripts.windows.atlas_paper_readiness_check import inspect

    old = inspect()
    assert old["schema"] == "ATLAS_PAPER_DESKTOP_READINESS_V1"
    assert old["decision"] == "NO_GO"
    assert old["unverified_gate_count"] == 9
    assert len(old["acceptance"]) == 9
    assert all(v == "NOT_INDEPENDENTLY_VERIFIED"
               for v in old["acceptance"].values())
    assert old["paper_startup_authorized"] is False
    assert old["live_trading_authorized"] is False
    r = preflight._classify(
        origin=copy.deepcopy(ORIGIN),
        roots=copy.deepcopy(EMPTY),
        newer_watch=True, newer_epoch=True,
    )
    assert r["legacy_nine_gate_checker_is_constant_no_go_sentinel"] is True
    assert r["legacy_checker_is_a_progress_percentage"] is False
    assert r["paper_startup_authorized"] is False
