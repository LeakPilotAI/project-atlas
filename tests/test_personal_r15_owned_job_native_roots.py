"""R15 owned Job must bind 12 original, existing, EMPTY native roots.

Pure synthetic root-drift cases plus one genuine selected Windows Job child.
No activation, account file, provider request, PAPER order or live money.
"""
import copy
import sys

import pytest

from scripts.observation_runtime import personal_r15_owned_job_activation as gate


def fixture():
    roles = tuple(gate.ROLES)
    accounts = {}
    lanes = {}
    i = 0
    for lane, epoch in (
            ("QUALITY_DIPS", "qd-paper-preinception-test"),
            ("HYPERLIQUID", "hl-paper-preinception-test")):
        resources = {}
        roots = {}
        for role in roles:
            i += 1
            path = rf"D:\OfflineTest\{lane}\{epoch}\{role}"
            identity = [1, i + 100, 0]
            resources[role] = {"path": path, "native_id": identity}
            roots[role] = {
                "path": path, "native_id": copy.deepcopy(identity),
                "native_identity_verified": True,
                "existing_empty_namespace_verified": True,
            }
        accounts[lane] = {"epoch": epoch, "resources": resources}
        lanes[lane] = {"epoch": epoch, "roots": roots}
    evidence = {
        "schema": "ATLAS_TWO_LANE_EXISTING_NATIVE_ROOT_PRE_ENROLLMENT_V1",
        "lanes": lanes, "native_root_total": 12,
        "native_root_ids_verified": 12,
        "existing_empty_root_namespaces": 12,
        "all_twelve_distinct_and_empty": True,
        "operator_account_enrollment_verified": False,
        "writer_ownership_verified": False,
        "financial_inception_verified": False,
        "paper_start_authorized": False,
        "live_trading_authorized": False,
        "filesystem_writes": 0, "network_requests": 0,
    }
    return accounts, evidence


def verified(accounts, evidence):
    return gate.require_exact_r15_preinception_roots(
        accounts["QUALITY_DIPS"], accounts["HYPERLIQUID"], evidence)


def test_twelve_native_roots_exactly_match_both_enrollments():
    accounts, evidence = fixture()
    original_a, original_e = copy.deepcopy(accounts), copy.deepcopy(evidence)
    bound = verified(accounts, evidence)
    assert len(bound) == 12
    assert len(set(row[3] for row in bound)) == 12
    assert bound[0][0] == "QUALITY_DIPS"
    assert bound[-1][0] == "HYPERLIQUID"
    assert accounts == original_a and evidence == original_e
    assert all(type(row[3]) is tuple for row in bound)


@pytest.mark.parametrize("case", [
    "missing_lane", "extra_lane", "wrong_schema", "false_all_empty",
    "missing_verified_root", "missing_empty_root", "wrong_native_id",
    "wrong_path", "alias_native_id", "alias_path", "missing_resource",
    "extra_resource", "wrong_epoch", "account_inception_claim",
    "paper_start_claim", "live_money_claim", "writer_claim",
    "filesystem_writes", "network_requests", "missing_native_id",
    "boolean_native_id", "wrong_count", "duplicate_lane_root",
])
def test_mutated_native_root_or_financial_promotion_refuses_before_activation(case):
    accounts, evidence = fixture()
    qd, hl = evidence["lanes"]["QUALITY_DIPS"], evidence["lanes"]["HYPERLIQUID"]
    if case == "missing_lane":
        evidence["lanes"].pop("HYPERLIQUID")
    elif case == "extra_lane":
        evidence["lanes"]["FOREIGN"] = {}
    elif case == "wrong_schema":
        evidence["schema"] = "FORGED"
    elif case == "false_all_empty":
        evidence["all_twelve_distinct_and_empty"] = False
    elif case == "missing_verified_root":
        qd["roots"]["source"]["native_identity_verified"] = False
    elif case == "missing_empty_root":
        qd["roots"]["source"]["existing_empty_namespace_verified"] = False
    elif case == "wrong_native_id":
        qd["roots"]["source"]["native_id"] = [2, 300, 0]
    elif case == "wrong_path":
        hl["roots"]["source"]["path"] = r"D:\FOREIGN\source"
    elif case == "alias_native_id":
        hl["roots"]["report"]["native_id"] = qd["roots"]["report"]["native_id"]
        accounts["HYPERLIQUID"]["resources"]["report"]["native_id"] = qd["roots"]["report"]["native_id"]
    elif case == "alias_path":
        hl["roots"]["report"]["path"] = qd["roots"]["report"]["path"]
        accounts["HYPERLIQUID"]["resources"]["report"]["path"] = qd["roots"]["report"]["path"]
    elif case == "missing_resource":
        accounts["QUALITY_DIPS"]["resources"].pop("control")
    elif case == "extra_resource":
        accounts["QUALITY_DIPS"]["resources"]["UNAPPROVED"] = {}
    elif case == "wrong_epoch":
        evidence["lanes"]["HYPERLIQUID"]["epoch"] = "other"
    elif case == "account_inception_claim":
        evidence["financial_inception_verified"] = True
    elif case == "paper_start_claim":
        evidence["paper_start_authorized"] = True
    elif case == "live_money_claim":
        evidence["live_trading_authorized"] = True
    elif case == "writer_claim":
        evidence["writer_ownership_verified"] = True
    elif case == "filesystem_writes":
        evidence["filesystem_writes"] = 1
    elif case == "network_requests":
        evidence["network_requests"] = 1
    elif case == "missing_native_id":
        qd["roots"]["source"].pop("native_id")
    elif case == "boolean_native_id":
        qd["roots"]["source"]["native_id"] = [True, 1, 2]
        accounts["QUALITY_DIPS"]["resources"]["source"]["native_id"] = [True, 1, 2]
    elif case == "wrong_count":
        evidence["native_root_ids_verified"] = 11
    elif case == "duplicate_lane_root":
        hl["roots"].pop("custody")
    with pytest.raises(ValueError, match="R15_ACTIVATION_"):
        verified(accounts, evidence)


@pytest.mark.skipif(sys.platform != "win32", reason="Selected R15 native Windows Job required")
def test_actual_installed_r15_job_refuses_native_root_drift_and_owned_child_is_cleaned(monkeypatch):
    # This genuine installed-R15 Job rehearsal requires R15 to be CURRENTLY
    # selected. Once native revision 15 selects R16, retain the pure R15
    # root-identity tests but use the R16 owned-Job native lifecycle suite.
    from pathlib import Path
    if Path("D:/AtlasRuntime/selection/r0015.json").is_file():
        from scripts.observation_runtime.atlas_r16_selected_code_readback import (
            selected_code as r16_selected_code,
        )
        if r16_selected_code()["selected_revision"] == 15:
            pytest.skip("R15 original native Job is no longer selected; R16 owner tested separately")
    from scripts.observation_runtime import atlas_r15_parked_writer_owner as parked
    from scripts.observation_runtime.personal_existing_native_resource_evidence import (
        inspect_two_lane_native_roots,
    )
    actual = inspect_two_lane_native_roots()
    assert actual["native_root_total"] == 12
    assert actual["all_twelve_distinct_and_empty"] is True
    original = gate.inspect_two_lane_native_roots
    calls = []

    def changing_snapshot():
        current = original()
        calls.append(len(calls) + 1)
        if len(calls) >= 2:
            current["lanes"]["QUALITY_DIPS"]["roots"]["source"]["native_id"][1] += 1
        return current

    monkeypatch.setattr(gate, "inspect_two_lane_native_roots", changing_snapshot)
    with pytest.raises(ValueError, match="R15_ACTIVATION_NATIVE_ROOTS_CHANGED_DURING_OWNED_JOB"):
        parked.inspect()
    assert len(calls) >= 2
    assert inspect_two_lane_native_roots() == actual
    assert actual["paper_start_authorized"] is False


def populated_fixture():
    accounts, evidence = fixture()
    original = verified(accounts, evidence)
    # Only the pre-inception namespace flags change, not directory identities.
    for lane, role in (
        ("QUALITY_DIPS", "source"), ("QUALITY_DIPS", "coordination"),
        ("HYPERLIQUID", "source"), ("HYPERLIQUID", "report")):
        evidence["lanes"][lane]["roots"][role]["existing_empty_namespace_verified"] = False
    evidence["existing_empty_root_namespaces"] = 8
    evidence["all_twelve_distinct_and_empty"] = False
    return accounts, evidence, original


def postcheck(accounts, evidence, original):
    return gate.require_exact_r15_populated_root_identities(
        accounts["QUALITY_DIPS"], accounts["HYPERLIQUID"],
        evidence, original)


def test_same_original_twelve_file_identified_roots_allow_later_file_population_not_activation():
    accounts, evidence, original = populated_fixture()
    before = copy.deepcopy(evidence)
    assert postcheck(accounts, evidence, original) == original
    assert evidence == before
    with pytest.raises(ValueError, match="R15_ACTIVATION_"):
        verified(accounts, evidence)
    assert evidence["all_twelve_distinct_and_empty"] is False


@pytest.mark.parametrize("damage", [
    "source_native_id", "control_native_id", "report_path", "epoch",
    "original_binding", "missing_lane", "duplicate_root_identity",
    "duplicate_root_path", "missing_role", "foreign_role",
    "missing_native_id", "bad_type_native_id", "unknown_native_identity",
    "wrong_total", "wrong_verified_count", "negative_empty_count",
    "wrong_empty_count_type", "stale_empty_count", "forged_all_empty",
    "wrong_schema", "writer_acceptance",
    "financial_activation", "live_order", "filesystem_writes",
    "network_requests",
])
def test_populated_root_continuity_fail_closed_on_identity_or_authority_drift(damage):
    accounts, evidence, original = populated_fixture()
    qd = evidence["lanes"]["QUALITY_DIPS"]
    hl = evidence["lanes"]["HYPERLIQUID"]
    if damage == "source_native_id":
        qd["roots"]["source"]["native_id"][1] += 1
    elif damage == "control_native_id":
        hl["roots"]["control"]["native_id"][1] += 1
    elif damage == "report_path":
        hl["roots"]["report"]["path"] = "D:\\FOREIGN\\report"
    elif damage == "epoch":
        hl["epoch"] += "-FOREIGN"
    elif damage == "original_binding":
        original = original[::-1]
    elif damage == "missing_lane":
        evidence["lanes"].pop("QUALITY_DIPS")
    elif damage == "duplicate_root_identity":
        hl["roots"]["source"]["native_id"] = qd["roots"]["source"]["native_id"][:]
        accounts["HYPERLIQUID"]["resources"]["source"]["native_id"] = (
            qd["roots"]["source"]["native_id"][:])
    elif damage == "duplicate_root_path":
        hl["roots"]["source"]["path"] = qd["roots"]["source"]["path"]
        accounts["HYPERLIQUID"]["resources"]["source"]["path"] = qd["roots"]["source"]["path"]
    elif damage == "missing_role":
        qd["roots"].pop("custody")
    elif damage == "foreign_role":
        qd["roots"]["UNKNOWN"] = {}
    elif damage == "missing_native_id":
        qd["roots"]["source"].pop("native_id")
    elif damage == "bad_type_native_id":
        qd["roots"]["source"]["native_id"] = [True, 1, 0]
    elif damage == "unknown_native_identity":
        qd["roots"]["source"]["native_identity_verified"] = False
    elif damage == "wrong_total":
        evidence["native_root_total"] = 11
    elif damage == "wrong_verified_count":
        evidence["native_root_ids_verified"] = 11
    elif damage == "negative_empty_count":
        evidence["existing_empty_root_namespaces"] = -1
    elif damage == "wrong_empty_count_type":
        evidence["existing_empty_root_namespaces"] = True
    elif damage == "stale_empty_count":
        evidence["existing_empty_root_namespaces"] = 9
    elif damage == "forged_all_empty":
        evidence["all_twelve_distinct_and_empty"] = True
    elif damage == "wrong_schema":
        evidence["schema"] = "UNTRUSTED_SCHEMA"
    elif damage == "writer_acceptance":
        evidence["writer_ownership_verified"] = True
    elif damage == "financial_activation":
        evidence["financial_inception_verified"] = True
    elif damage == "live_order":
        evidence["live_trading_authorized"] = True
    elif damage == "filesystem_writes":
        evidence["filesystem_writes"] = 1
    elif damage == "network_requests":
        evidence["network_requests"] = 1
    with pytest.raises(ValueError, match="R15_POPULATED_"):
        postcheck(accounts, evidence, original)


def test_populated_root_observer_never_promotes_to_financial_owner(monkeypatch):
    from app.services.paper_financial_replay import digest
    accounts, evidence, original = populated_fixture()
    owner = object.__new__(gate.RetainedSelectedR15OwnerJob)
    owner._qd = digest(accounts["QUALITY_DIPS"])
    owner._perp = digest(accounts["HYPERLIQUID"])
    owner._original_qd = copy.deepcopy(accounts["QUALITY_DIPS"])
    owner._original_perp = copy.deepcopy(accounts["HYPERLIQUID"])
    owner._native_root_binding = original
    checked = []
    def fake_worker():
        checked.append(True)
        return True
    monkeypatch.setattr(gate.RetainedSelectedR15OwnerJob,
                        "_verify_owned_worker", lambda self:fake_worker())
    monkeypatch.setattr(gate,"inspect_two_lane_native_roots",
                        lambda:copy.deepcopy(evidence))
    view = owner.observe_original_roots_allowing_population(
        qd=accounts["QUALITY_DIPS"],perp=accounts["HYPERLIQUID"])
    assert checked == [True]
    assert view == {
        "schema": "ATLAS_R15_NATIVE_ROOT_IDENTITY_CONTINUITY_ONLY_V1",
        "selected_native_head": gate.SELECTED_HEAD,
        "original_root_count_native_identity_verified": 12,
        "original_job_and_process_still_owned": True,
        "empty_root_precondition_required_for_activation": True,
        "financial_file_contents_or_coordination_ledger_audited": False,
        "postinception_writer_lease_issued": False,
        "native_financial_inception_accepted": False,
        "paper_start_authorized": False,
        "live_trading_authorized": False,
    }
    with pytest.raises(ValueError,match="R15_POPULATED_NATIVE_ENROLLMENT_DRIFT"):
        owner.observe_original_roots_allowing_population(
            qd={"tampered":True},perp=accounts["HYPERLIQUID"])
