"""R15 offline closeout is a read-only refusal, never financial approval."""
import copy
import json

import pytest

from scripts.observation_runtime import atlas_r15_offline_closeout as mod


@pytest.fixture(scope="module")
def actual():
    return mod.inspect()


def baseline():
    return {
        "selected":{
            "decision":"NO_GO","selected_code_verified":True,
            "selected_code_identity":{"revision":13},
            "accepted_financial_operating_gates":0,
            "total_financial_operating_gates":9,
            "desktop_one_click_paper_ready":False,
            "paper_start_authorized":False,
        },
        "install_plan":{
            "status":"SOURCE_AND_DEPENDENCY_PLAN_VERIFIED_NOT_INSTALL_AUTHORIZATION",
            "source_commit":"2c79a8d846d6b33669008114732ae5896153812a",
            "source_archive_sha256":mod.inspect.__module__,
            "native_installation_authorized":False,
            "native_installation_executed":False,
            "financial_paper_start_authorized":False,
            "planned_native_files":10526,
            "planned_native_bytes":263545933,
        },
        "sources":{
            "decision":"NO_GO","selected_code_revision":13,
            "source_rights_independently_accepted":False,
            "paper_startup_authorized":False,
            "quality_dips":{
                "operational_source_publication_verified":False,
                "catalog_symbols":13487},
            "hyperliquid":{"native_financial_writer_verified":False},
        },
        "iex":{
            "selected_revision":13,"provider_connected":False,
            "private_credentials_accessed":False,
            "sample_already_verified":False,"trading_authorized":False,
        },
        "hl":{
            "selected_code_revision":13,
            "financial_execution_authorized":False,
            "market_book_observed":False,
            "provider_connection_opened":False,
            "paper_startup_authorized":False,
            "existing_request_budget":{"remaining":2},
        },
        "personal":{
            "schema":"ATLAS_PERSONAL_NATIVE_COMMISSIONING_INVENTORY_V1",
            "native_activation_verified":False,"account_enrollment_verified":False,
            "paper_start_authorized":False,"ordinary_activation_file_candidates":[],
        },
        "kalshi":{
            "target_paper_strategy":"NEWLY_LISTED_SINGLE_YES_NO_PRICE_DISCOVERY_V1",
            "legacy_repricing_paper_entry_enabled":False,
            "target_new_listing_paper_entry_commissioned":False,
            "yes_no_single_leg_only":True,"combos_allowed":False,
            "parlays_allowed":False,"live_execution":False,
        },
        "differences":{
            k:{"selected_native_contains_successor_fix":False}
            for k in mod.CHANGED_SELECTED_RUNTIME
        },
    }


def test_actual_integrated_closeout_is_no_go_without_any_provider_access(actual):
    assert actual["schema"]=="ATLAS_R15_OFFLINE_PREPRODUCTION_CLOSEOUT_V1"
    assert actual["decision"]=="NO_GO"
    assert actual["selected_native_release"]=="R14"
    assert actual["frozen_successor_source_candidate_verified"] is True
    assert actual["successor_code_only_install_plan_verified"] is True
    assert actual["successor_native_plan_files"]==10526
    assert actual["successor_native_plan_bytes"]==263545933
    assert actual["quality_dips_research_assets"]==13487
    assert actual["hyperliquid_public_request_attempts_remaining"]==2
    assert actual["personal_paper_native_activation_candidates"]==0
    assert actual["kalshi_new_listing_paper_engine_commissioned"] is False
    assert actual["financial_operating_gates_accepted"]==0
    assert actual["financial_operating_gates_total"]==9
    assert len(actual["not_blocked_by_stock_market_hours_but_requires_separate_permission"])==4
    assert len(actual["blocked_on_real_provider_data_or_operational_evidence"])==5
    for key in (
        "successor_code_only_install_authorized",
        "successor_native_installation_executed",
        "successor_code_selection_authorized",
        "quality_dips_current_quotes_verified",
        "quality_dips_forward_paper_writer_enrolled",
        "hyperliquid_current_book_verified",
        "hyperliquid_forward_paper_writer_enrolled",
        "personal_paper_native_account_enrollment_verified",
        "legacy_desktop_launcher_ready",
        "live_trading_authorized","paper_trading_authorized",
        "automated_desktop_start_stop_certified",
        "provider_connections_opened","credentials_accessed","orders_submitted",
        "native_installation_modified","selected_release_modified",
        "financial_gate_override",
    ):
        assert actual[key] is False


@pytest.mark.parametrize("part,key,value",[
    ("selected","decision","GO"),
    ("selected","accepted_financial_operating_gates",1),
    ("selected","paper_start_authorized",True),
    ("install_plan","native_installation_authorized",True),
    ("install_plan","native_installation_executed",True),
    ("install_plan","financial_paper_start_authorized",True),
    ("sources","source_rights_independently_accepted",True),
    ("sources","paper_startup_authorized",True),
    ("iex","private_credentials_accessed",True),
    ("iex","provider_connected",True),
    ("hl","market_book_observed",True),
    ("hl","financial_execution_authorized",True),
    ("personal","native_activation_verified",True),
    ("personal","account_enrollment_verified",True),
    ("kalshi","legacy_repricing_paper_entry_enabled",True),
    ("kalshi","target_new_listing_paper_entry_commissioned",True),
    ("kalshi","combos_allowed",True),
    ("kalshi","live_execution",True),
])
def test_offline_readiness_refuses_forged_financial_or_data_promotion(part,key,value):
    reports=baseline()
    reports[part][key]=value
    with pytest.raises(ValueError,match="ATLAS_OFFLINE_"):
        mod.evaluate(**reports)


def test_offline_closeout_rejects_claim_that_installed_r14_has_workspace_fixes():
    reports=baseline()
    row=next(iter(reports["differences"].values()))
    row["selected_native_contains_successor_fix"]=True
    with pytest.raises(ValueError,match="PENDING_NATIVE_FIX_INVENTORY_INVALID"):
        mod.evaluate(**reports)


def test_offline_closeout_pure_decision_refuses_financial_start():
    result=mod.evaluate(**baseline())
    assert result["decision"]=="NO_GO"
    assert result["paper_trading_authorized"] is False
    assert result["automated_desktop_start_stop_certified"] is False
    assert result["successor_code_only_install_authorized"] is False


def test_offline_cli_report_is_mandatory_inspect_only(capsys):
    assert mod.main(["--inspect"])==2
    doc=json.loads(capsys.readouterr().out)
    assert doc["financial_operating_gates_accepted"]==0
    assert doc["orders_submitted"] is False
    with pytest.raises(SystemExit):
        mod.main(["--start"])
    with pytest.raises(SystemExit):
        mod.main(["--authorize-install"])
