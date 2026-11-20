"""R15 exact financial acceptance requirements inventory (never gate issuer)."""
import copy
import pytest

from scripts.observation_runtime import atlas_r15_nine_gate_evidence_inventory as inv
from scripts.observation_runtime import atlas_r15_paper_offline_commissioning as r15
from scripts.observation_runtime.personal_existing_native_resource_evidence import inspect_two_lane_native_roots
from scripts.observation_runtime.personal_native_commissioning_inventory import inspect as personal
from scripts.observation_runtime.quality_dips_source_inventory import inspect as qd
from scripts.observation_runtime.hyperliquid_native_preflight import inspect as hl
from scripts.observation_runtime.atlas_r15_two_account_enrollment_handoff import inspect as handoff
from scripts.windows.atlas_paper_readiness_check import inspect as desktop


@pytest.fixture(scope="module")
def source():
    return {
        "selected":r15.selected_code(),
        "financial":r15.inspect(),
        "roots":inspect_two_lane_native_roots(),
        "personal":personal(),
        "qd":qd(),
        "hl":hl(),
        "desktop":desktop(root=r15.ROOT),
        "handoff":handoff(),
    }


def test_selected_windows_r15_nine_financial_gate_original_readbacks_still_no_go(source):
    original=copy.deepcopy(source)
    r=inv.evaluate(**source)
    assert source==original
    assert r["schema"]==inv.SCHEMA
    assert r["decision"]=="NO_GO"
    assert r["source_release"]=="R15"
    assert r["selected_native_head"]==r15.SELECTED_HEAD
    assert r["independently_accepted_gate_count"]==0
    assert r["independently_accepted_gate_total"]==len(r15.GATES)==9
    assert [x["gate"] for x in r["financial_gates"]]==list(r15.GATES)
    assert all(x["accepted"] is False and x["independent_readbacks_accepted"]==0
               for x in r["financial_gates"])
    assert all(x["status"]=="BLOCKED_INDEPENDENT_NATIVE_FINANCIAL_ACCEPTANCE_MISSING"
               for x in r["financial_gates"])
    assert r["unaccepted_financial_gate_readbacks"]==[
        requirement for req in inv.REQUIREMENTS.values() for requirement in req]
    assert len(r["unaccepted_financial_gate_readbacks"])==20
    assert r["native_candidate_preconditions_present"]==4
    assert r["native_candidate_screen_count"]==10
    assert r["financial_gate_acceptance_authority_installed"] is False
    assert r["financial_gate_evidence_can_be_supplied_as_unsigned_json"] is False
    assert r["paper_start_authorized"] is False
    assert r["real_money_trading_authorized"] is False
    assert r["financial_writes"]==0 and r["provider_requests"]==0


@pytest.mark.parametrize("section,key,value",[
    ("selected","revision",13),
    ("selected","selected_native_head","0"*64),
    ("selected","financial_authority",True),
    ("selected","selected_native_record_sha256","0"*64),
    ("financial","decision","GO"),
    ("financial","paper_start_authorized",True),
    ("financial","financial_operating_gates_independently_accepted",1),
    ("financial","financial_operating_gates_total",10),
    ("roots","native_root_total",11),
    ("roots","existing_empty_root_namespaces",11),
    ("roots","all_twelve_distinct_and_empty",False),
    ("roots","writer_ownership_verified",True),
    ("roots","operator_account_enrollment_verified",True),
    ("roots","native_activation_record_verified",True),
    ("personal","native_activation_verified",True),
    ("personal","account_enrollment_verified",True),
    ("personal","paper_start_authorized",True),
    ("qd","operational_publication_verified",True),
    ("hl","native_writer_ownership","INDEPENDENTLY_VERIFIED"),
    ("hl","provider_rights_and_current_market_data","INDEPENDENTLY_VERIFIED"),
    ("hl","paper_startup_authorized",True),
    ("desktop","decision","GO"),
    ("desktop","paper_startup_authorized",True),
    ("handoff","native_root_count_handle_verified",11),
    ("handoff","account_enrollment_accepted",True),
    ("handoff","both_financial_inceptions_published",True),
    ("handoff","paper_start_authorized",True),
    ("handoff","selected_r15_artifact_digest","0"*64),
])
def test_unverified_native_gate_boolean_does_not_count_as_acceptance(source,section,key,value):
    data=copy.deepcopy(source)
    data[section][key]=value
    with pytest.raises((ValueError,TypeError,KeyError),match="R15_FINANCIAL_INVENTORY_"):
        inv.evaluate(**data)


@pytest.mark.parametrize("damage",[
    "extra_financial_gate","relabel_financial_gate","fake_gate_accepted",
    "missing_native_lane","extra_native_lane","extra_native_role",
    "modified_native_id","missing_held_root","writer_identity_claim",
    "fake_native_acceptance","new_release","changed_native_root",
    "fake_issuer_accepted","missing_source_reader","native_activation_candidate_not_authority",
])
def test_gate_inventory_rejects_forged_readers_and_acceptance(source,damage):
    data=copy.deepcopy(source)
    if damage=="extra_financial_gate":
        data["financial"]["gates"].append({"gate":"F10","accepted":False,"status":"NOT_INDEPENDENTLY_ACCEPTED"})
    elif damage=="relabel_financial_gate":
        data["financial"]["gates"][0]["gate"]="B1_FAKE"
    elif damage=="fake_gate_accepted":
        data["financial"]["gates"][0]["accepted"]=True
    elif damage=="missing_native_lane":
        data["roots"]["lanes"].pop("HYPERLIQUID")
    elif damage=="extra_native_lane":
        data["roots"]["lanes"]["OTHER"]={"epoch":"wrong","roots":{}}
    elif damage=="extra_native_role":
        data["roots"]["lanes"]["QUALITY_DIPS"]["roots"]["FAKE"]={}
    elif damage=="modified_native_id":
        data["roots"]["lanes"]["QUALITY_DIPS"]["roots"]["report"]["native_id"][2]+=1
    elif damage=="missing_held_root":
        data["roots"]["lanes"]["QUALITY_DIPS"]["roots"]["source"]["native_identity_verified"]=False
    elif damage=="writer_identity_claim":
        data["handoff"]["accounts"]["HYPERLIQUID"][
            "provisional_r15_native_enrollment_unaccepted"]["writers"]={"source":"FAKE"}
    elif damage=="fake_native_acceptance":
        data["handoff"]["accounts"]["QUALITY_DIPS"][
            "provisional_r15_native_enrollment_unaccepted"]["acceptance_id"]="FAKE"
    elif damage=="new_release":
        data["handoff"]["accounts"]["QUALITY_DIPS"][
            "provisional_r15_native_enrollment_unaccepted"]["release_digest"]="0"*64
    elif damage=="changed_native_root":
        data["handoff"]["accounts"]["HYPERLIQUID"][
            "provisional_r15_native_enrollment_unaccepted"]["resources"]["custody"]["path"]="D:\\foreign"
    elif damage=="fake_issuer_accepted":
        data["qd"]["operational_publication_verified"]=True
    elif damage=="missing_source_reader":
        data["hl"].pop("provider_rights_and_current_market_data")
    elif damage=="native_activation_candidate_not_authority":
        # A candidate file can be a clue but cannot promote any gate:
        # current native activation remains explicitly unverified.
        data["personal"]["ordinary_activation_file_candidates"]=["unaccepted"]
        result=inv.evaluate(**data)
        assert result["current_native_candidate_screen"][
            "PERSONAL_ACTIVATION_FILE_CANDIDATE_PRESENT"] is True
        assert result["independently_accepted_gate_count"]==0
        assert result["paper_start_authorized"] is False
        return
    with pytest.raises((ValueError,TypeError,KeyError),match="R15_FINANCIAL_INVENTORY_"):
        inv.evaluate(**data)


def test_actual_windows_no_go_readback_is_never_external_gate_authority():
    current=inv.inspect()
    assert current["independently_accepted_gate_count"]==0
    assert current["financial_gate_acceptance_authority_installed"] is False
    assert len(current["financial_gates"])==9
    assert len(current["unaccepted_financial_gate_readbacks"])==20
    assert current["paper_start_authorized"] is False
