"""R15 evidence-driven technical progress, separate from financial acceptance.

Never uses a historical receipt as a financial gate grant. Real Windows tests
are bounded nonfinancial process probes; all tests preserve PAPER NO_GO.
"""
import copy

import pytest

from scripts.observation_runtime import (
    atlas_r15_verified_technical_progress as progress,
)
from scripts.observation_runtime import (
    atlas_r15_paper_offline_commissioning as r15,
)
from scripts.observation_runtime.atlas_r15_two_account_enrollment_handoff import (
    inspect as handoff_inspect,
)
from scripts.observation_runtime.personal_existing_native_resource_evidence import (
    inspect_two_lane_native_roots,
)
from scripts.observation_runtime.atlas_r15_disposable_writer_process_audit import (
    inspect_two_lane_native_root_handles,
)
from scripts.observation_runtime.atlas_r15_native_job_admission_preflight import (
    inspect as job_inspect,
)


@pytest.fixture(scope="module")
def verified():
    return {
        "selected":r15.selected_code(),
        "ports":r15.selected_ports(),
        "roots":inspect_two_lane_native_roots(),
        "handoff":handoff_inspect(),
        "held":inspect_two_lane_native_root_handles(),
        "job":job_inspect(),
        "financial":r15.inspect(),
    }


def test_actual_native_r15_technical_prechecks_and_financial_gates_are_distinct(verified):
    copy_before=copy.deepcopy(verified)
    report=progress.evaluate(**verified)
    assert verified==copy_before
    assert report["schema"]==progress.SCHEMA
    assert report["installed_release"]=="R15"
    assert report["decision"]=="TECHNICAL_PREREQUISITES_VERIFIED_FINANCIAL_NO_GO"
    assert report["technical_prerequisites_verified"]==6
    assert report["technical_prerequisites_total"]==6
    assert len(report["technical_checks"])==6
    assert set(x["name"] for x in report["technical_checks"])==set(progress.TECHNICAL_NAMES)
    assert all(x["verified"] is True for x in report["technical_checks"])
    assert report["financial_operating_gates_accepted"]==0
    assert report["financial_operating_gates_total"]==9
    assert report["financial_gate_acceptance_evaluator_installed"] is False
    assert report["financial_percent_complete_estimate_available"] is False
    assert len(report["unmet_financial_requirements"])==6
    assert report["technical_prechecks_not_financial_gate_promotions"] is True
    assert all(x["accepted"] is False
               for x in report["financial_operating_gates_from_legacy_offline_inspector"])
    for key in ("paper_start_authorized","live_trading_authorized",
                "persistent_paper_writer_enrolled"):
        assert report[key] is False
    for key in ("native_financial_account_files_written","provider_requests",
                "paper_orders_created","real_money_orders_created"):
        assert report[key]==0


@pytest.mark.parametrize("part,field,value",[
    ("selected","revision",13),
    ("selected","selected_native_head","0"*64),
    ("selected","selected_native_record_sha256","f"*64),
    ("selected","financial_authority",True),
    ("selected","independent_live_financial_clock_lease_accepted",True),
    ("selected","native_clock_own_release_source_admitted",False),
    ("ports","backend/app/services/unified_writer_roster.py",None),
    ("roots","native_root_ids_verified",11),
    ("roots","existing_empty_root_namespaces",11),
    ("roots","all_twelve_distinct_and_empty",False),
    ("roots","writer_ownership_verified",True),
    ("roots","operator_account_enrollment_verified",True),
    ("roots","native_activation_record_verified",True),
    ("handoff","selected_native_head","f"*64),
    ("handoff","selected_r15_record_sha256","0"*64),
    ("handoff","native_root_count_handle_verified",11),
    ("handoff","account_enrollment_accepted",True),
    ("handoff","both_financial_inceptions_published",True),
    ("handoff","paper_start_authorized",True),
    ("held","actual_existing_native_roots_verified",11),
    ("held","sample_count_while_process_alive",2),
    ("held","all_twelve_root_ids_unchanged_after_exit",False),
    ("held","child_exited_and_handles_closed",False),
    ("held","financial_writer_process_enrolled",True),
    ("held","financial_writer_lease_active",True),
    ("held","paper_start_authorized",True),
    ("job","selected_native_head","0"*64),
    ("job","status","PAPER_ACCEPTED"),
    ("job","active_children_after_check",1),
    ("job","persistent_writer_enrolled",True),
    ("job","paper_start_authorized",True),
    ("job","native_financial_writes",1),
    ("financial","selected_native_release","R14"),
    ("financial","decision","GO"),
    ("financial","financial_operating_gates_independently_accepted",1),
    ("financial","paper_start_authorized",True),
    ("financial","native_qd_forward_writer_enrolled",True),
    ("financial","native_hyperliquid_forward_writer_enrolled",True),
    ("financial","native_financial_ledger_accepted",True),
    ("financial","current_iex_equity_quotes_verified",True),
])
def test_independently_measured_r15_technical_report_refuses_fake_promotion(
        verified,part,field,value):
    sample=copy.deepcopy(verified)
    if part=="ports":
        sample[part][field]["native_installed_source_present"]=False
    else:
        sample[part][field]=value
    with pytest.raises((ValueError,KeyError,TypeError),match="R15_MILESTONES_"):
        progress.evaluate(**sample)


@pytest.mark.parametrize("damage",[
    "qd_real_enrollment","hl_fake_writer_lease",
    "extra_financial_gate","accepted_financial_gate",
    "wrong_financial_gate","job_unexpected_mode",
    "job_exit_not_stopped","job_exit_not_normal",
    "root_extra_lane","handoff_hidden_issuer",
])
def test_r15_milestone_aggregation_never_promotes_stale_ownership(
        verified,damage):
    sample=copy.deepcopy(verified)
    if damage=="qd_real_enrollment":
        sample["handoff"]["accounts"]["QUALITY_DIPS"]["real_enrollment_accepted"]=True
    elif damage=="hl_fake_writer_lease":
        sample["handoff"]["accounts"]["HYPERLIQUID"]["writer_process_observed_and_leased"]=True
    elif damage=="extra_financial_gate":
        sample["financial"]["gates"].append({"gate":"F10","accepted":False,"status":"NOT_INDEPENDENTLY_ACCEPTED"})
    elif damage=="accepted_financial_gate":
        sample["financial"]["gates"][1]["accepted"]=True
    elif damage=="wrong_financial_gate":
        sample["financial"]["gates"][0]["gate"]="E1_NOT_EARNED"
    elif damage=="job_unexpected_mode":
        sample["job"]["runs"][1]["mode"]="PAPER_TRADE"
    elif damage=="job_exit_not_stopped":
        sample["job"]["runs"][1]["exit_code"]=0
    elif damage=="job_exit_not_normal":
        sample["job"]["runs"][0]["exit_code"]=1
    elif damage=="root_extra_lane":
        sample["roots"]["lanes"]["FAKE"]={"epoch":"forged","roots":{}}
        # Outer root validator only covers witnessed count, so this detects
        # cross-check requirements once we extend exact lane identity.
    elif damage=="handoff_hidden_issuer":
        sample["handoff"]["accounts"]["QUALITY_DIPS"]["real_enrollment_accepted"]=True
    with pytest.raises((ValueError,KeyError,TypeError),match="R15_MILESTONES_"):
        progress.evaluate(**sample)


def test_actual_native_r15_inspect_repeat_replays_operational_evidence():
    result=progress.inspect()
    assert result["technical_prerequisites_verified"]==6
    assert result["financial_operating_gates_accepted"]==0
    assert result["paper_start_authorized"] is False
    assert result["real_money_orders_created"]==0
