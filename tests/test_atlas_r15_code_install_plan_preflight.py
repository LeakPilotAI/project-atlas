"""R15 native installation proposal is read-only and never permission."""
import copy
import json
from pathlib import Path

import pytest

from scripts.observation_runtime import atlas_r15_code_install_plan_preflight as mod


@pytest.fixture(scope="module")
def actual():
    return mod.inspect()


def inputs():
    selected = {
        "revision":13,
        "selected_release":mod.REQUIRED_SELECTED_RELEASE,
        "native_selection_head":mod.R14_HEAD,
        "native_selection_record_verified":True,
        "financial_authority":False,
    }
    prepared = {
        "selected_digest":mod.INVENTORY_SHA,
        "verified":{"source_files":960,"activation_approved":False,
                    "installation_verified":False},
        "runtime":dict.fromkeys(range(960)),
        "dependencies":dict.fromkeys(range(9566)),
        "names":[None]*10526,
        "directories":[None]*911,
        "total":mod.EXPECTED_BYTES,
    }
    freeze = {
        "schema":"ATLAS_R15_SOURCE_ONLY_FROZEN_CANDIDATE_V1",
        "status":"ARCHIVE_SOURCE_BYTES_VERIFIED_NO_INSTALL_OR_SELECTION",
        "source_commit":mod.SOURCE_COMMIT,
        "selected_native_predecessor":mod.REQUIRED_SELECTED_RELEASE,
        "source_files":960,
        "inventory_sha256":mod.INVENTORY_SHA,
        "archive_sha256":mod.ARCHIVE_SHA,
        "native_release_installed":False,
        "native_installation_authorized":False,
        "release_selection_authorized":False,
        "financial_paper_authorized":False,
    }
    return selected,prepared,freeze


def test_verified_actual_native_dependency_plan_remains_not_installed(actual):
    assert actual["schema"]=="ATLAS_R15_SOURCE_ONLY_NATIVE_INSTALL_PROPOSAL_V1"
    assert actual["status"]=="SOURCE_AND_DEPENDENCY_PLAN_VERIFIED_NOT_INSTALL_AUTHORIZATION"
    assert actual["planned_runtime_source_files"]==960
    assert actual["planned_dependency_files"]==9566
    assert actual["planned_native_files"]==10526
    assert actual["planned_native_directories"]==912
    assert actual["planned_native_bytes"]==263545933
    assert actual["source_archive_sha256"]==mod.ARCHIVE_SHA
    assert actual["dependency_receipt_sha256"]==mod.DEPENDENCY_RECEIPT_SHA256
    assert actual["new_create_only_release_target"]==str(mod.TARGET)
    assert actual["separate_exact_one_shot_code_install_authorization_required"] is True
    assert actual["separate_exact_one_shot_code_selection_authorization_required"] is True
    for key in (
        "native_installation_executed","native_installation_authorized",
        "source_authenticated_by_native_install","native_selection_changed",
        "financial_writer_enrolled","provider_connection_opened",
        "financial_paper_start_authorized","paper_orders_authorized",
        "live_trading_authorized",
    ):
        assert actual[key] is False
    assert actual["financial_operating_gates_accepted"]==0
    assert not mod.TARGET.exists()
    assert not mod.RECEIPT.exists()


def test_pure_plan_validation_remains_no_go_without_side_effects():
    selected,prepared,freeze=inputs()
    out=mod.evaluate(selected=selected,prepared=prepared,freeze=freeze)
    assert out["decision"]=="REVIEW_REQUIRED"
    assert out["native_installation_authorized"] is False


@pytest.mark.parametrize("key,value",[
    ("revision",12),("selected_release","f"*40),
    ("native_selection_head","0"*64),
    ("native_selection_record_verified",False),("financial_authority",True),
])
def test_refuse_wrong_selected_runtime_identity(key,value):
    selected,prepared,freeze=inputs()
    selected[key]=value
    with pytest.raises(ValueError,match="GENUINE_SELECTED_R14_PREDECESSOR_REQUIRED"):
        mod.evaluate(selected=selected,prepared=prepared,freeze=freeze)


@pytest.mark.parametrize("key,value",[
    ("source_commit","f"*40),("source_files",953),
    ("native_release_installed",True),
    ("native_installation_authorized",True),
    ("release_selection_authorized",True),
    ("financial_paper_authorized",True),
    ("inventory_sha256","0"*64),
    ("archive_sha256","0"*64),
])
def test_refuse_mutated_frozen_source_or_permissions(key,value):
    selected,prepared,freeze=inputs()
    freeze[key]=value
    with pytest.raises(ValueError,match="FROZEN_SOURCE_NONFINANCIAL_EVIDENCE_REQUIRED"):
        mod.evaluate(selected=selected,prepared=prepared,freeze=freeze)


@pytest.mark.parametrize("key,value",[
    ("total",0),("total",263545934),
    ("selected_digest","0"*64),
    ("names",[]),("runtime",{}),("dependencies",{}),
])
def test_refuse_changed_native_plan(key,value):
    selected,prepared,freeze=inputs()
    prepared[key]=value
    with pytest.raises(ValueError,match="EXACT_BOUNDED_NATIVE_INSTALL_PLAN_REFUSED"):
        mod.evaluate(selected=selected,prepared=prepared,freeze=freeze)


def test_no_reuse_or_partial_install_target(monkeypatch,tmp_path):
    for artifact in ("target","receipt","receipt.pending.jsonl"):
        temporary=tmp_path/artifact
        temporary.write_text("UNRELATED_SIMULATED_OWNER",encoding="utf-8")
    monkeypatch.setattr(mod,"TARGET",tmp_path/"target")
    with pytest.raises(ValueError,match="NATIVE_TARGET_OR_RECEIPT_ALREADY_OCCUPIED"):
        mod.require_new_native_target(mod.TARGET)


def test_refuse_existing_exact_target_in_isolated_simulated_namespaces(monkeypatch,tmp_path):
    simulated=tmp_path/"new_releases"
    simulated.mkdir()
    install=simulated/"next"
    audit=tmp_path/"next_receipt.json"
    monkeypatch.setattr(mod,"TARGET",install)
    monkeypatch.setattr(mod,"RECEIPT",audit)
    assert mod.require_new_native_target(install) is True
    install.mkdir()
    with pytest.raises(ValueError,match="ALREADY_OCCUPIED"):
        mod.require_new_native_target(install)


def test_readonly_cli_explicit_inspect_and_no_install(capsys):
    result=mod.main(["--inspect"])
    assert result==2
    data=json.loads(capsys.readouterr().out)
    assert data["status"]=="SOURCE_AND_DEPENDENCY_PLAN_VERIFIED_NOT_INSTALL_AUTHORIZATION"
    assert data["native_installation_executed"] is False
    with pytest.raises(SystemExit):
        mod.main(["--execute-install"])
