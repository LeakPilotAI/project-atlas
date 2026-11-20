"""R15 installer nonfinancial consent, native source and bounded-copy guards."""
import copy
import json
import os
import hashlib
from pathlib import Path

import pytest

from scripts import atlas_r15_code_only_installer as mod
from scripts.observation_runtime.atlas_r15_code_install_plan_preflight import (
    DEPENDENCY_INVENTORY_SHA256, R14_HEAD,
)


def sample_approval():
    return {
        "schema":"ATLAS_R15_CODE_ONLY_NATIVE_INSTALL_APPROVAL_V1",
        "decision":mod.OPERATION,
        "scope":mod.SCOPE,
        "source_commit":mod.SOURCE_COMMIT,
        "source_archive_sha256":mod.ARCHIVE_SHA,
        "source_inventory_sha256":mod.INVENTORY_SHA,
        "target":str(mod.TARGET),
        "receipt":str(mod.RECEIPT),
        "dependency_inventory_sha256":DEPENDENCY_INVENTORY_SHA256,
        "selected_r14_head":R14_HEAD,
        "installer_source_sha256":mod.approval_source_sha256(),
        "operator_sid":"S-1-5-21-1-2-3-1001",
        "one_shot":True,
        "selection_allowed":False,
        "financial_authority":False,
        "provider_access":False,
        "paper_accounts":False,
        "startup_authorized":False,
        "paper_orders_authorized":False,
        "live_orders_authorized":False,
    }


def test_pinned_install_scope_has_no_automatic_one_shot_approval():
    assert mod.APPROVAL_SHA256 is None
    assert not os.path.lexists(mod.APPROVAL)
    with pytest.raises(ValueError,match="APPROVAL_NOT_PINNED"):
        mod.require_separate_consent()


def test_complete_reviewed_install_approval_contract_is_not_install_permission():
    approved=mod.validate_operator_decision(
        sample_approval(),sid="S-1-5-21-1-2-3-1001")
    assert approved["selection_allowed"] is False
    assert approved["financial_authority"] is False
    assert approved["provider_access"] is False


@pytest.mark.parametrize("key,value",[
    ("one_shot",False),("selection_allowed",True),
    ("financial_authority",True),("provider_access",True),
    ("paper_accounts",True),("startup_authorized",True),
    ("paper_orders_authorized",True),("live_orders_authorized",True),
    ("source_commit","f"*40),("target","D:/other/release"),
    ("selected_r14_head","0"*64),("scope","ALL_TRADING"),
    ("dependency_inventory_sha256","1"*64),
])
def test_refuse_any_permission_escalation_or_foreign_source(key,value):
    row=sample_approval()
    row[key]=value
    with pytest.raises(ValueError,match="EXACT_SID_BOUND_ONE_SHOT"):
        mod.validate_operator_decision(row,sid="S-1-5-21-1-2-3-1001")


def test_wrong_sid_and_extra_fields_are_refused():
    row=sample_approval()
    with pytest.raises(ValueError,match="EXACT_SID_BOUND_ONE_SHOT"):
        mod.validate_operator_decision(row,sid="S-1-5-21-9-8-7-1001")
    row["ALLOW_ANY_ACCOUNT"]=True
    with pytest.raises(ValueError,match="EXACT_SID_BOUND_ONE_SHOT"):
        mod.validate_operator_decision(row,sid="S-1-5-21-1-2-3-1001")


def test_installer_inspection_never_grants_any_financial_or_native_write():
    out=mod.inspect()
    assert out["status"]=="READY_FOR_SEPARATE_EXACT_INSTALL_APPROVAL_NOT_APPROVED"
    assert out["planned_native_files"]==10526
    assert out["planned_native_bytes"]==263545933
    assert out["new_install_target"]==str(mod.TARGET)
    assert out["operator_approval_pinned"] is False
    assert out["idle_priority_required"] is True
    assert out["independent_180_second_two_peer_clock_required"] is True
    for key in ("installation_authorized","installed","selection_authorized",
                "provider_access","paper_accounts","startup_authorized",
                "paper_orders_authorized","live_orders_authorized"):
        assert out[key] is False
    assert not mod.TARGET.exists()
    assert not mod.RECEIPT.exists()


def test_install_api_without_exact_one_shot_scope_never_reaches_clock_or_target(monkeypatch):
    monkeypatch.setattr(mod,"require_code_install_host_ready",
                        lambda *_:pytest.fail("HOST_ADMISSION_MUST_NOT_RUN"))
    with pytest.raises(ValueError,match="EXPLICIT_CODE_ONLY_INSTALL_EXECUTION"):
        mod.install(clock=None)
    with pytest.raises(ValueError,match="APPROVAL_NOT_PINNED"):
        mod.install(execute_approved=True,clock=None)
    assert not mod.TARGET.exists()


def test_explicit_cli_cannot_bypass_nonexistent_pin_or_read_provider(monkeypatch):
    from scripts.observation_runtime import atlas_independent_ntp_clock as ntp
    monkeypatch.setattr(ntp,"IndependentNtpClock",
                        lambda *_args,**_kwargs:pytest.fail("NTP_NETWORK_UNAUTHORIZED"))
    with pytest.raises(ValueError,match="APPROVAL_NOT_PINNED"):
        mod.main(["--execute-one-shot-code-install","--confirm-scope",mod.SCOPE])
    with pytest.raises(ValueError,match="EXACT_ONE_SHOT_SCOPE_CONFIRMATION"):
        mod.main(["--execute-one-shot-code-install","--confirm-scope","LIVE_TRADING"])
    with pytest.raises(SystemExit):
        mod.main(["--start-paper"])
    assert not mod.TARGET.exists()


def test_actual_read_only_cli_and_scope_rejection(capsys):
    out=mod.main(["--inspect"])
    assert out["installed"] is False
    assert out["selection_authorized"] is False
    with pytest.raises(ValueError,match="INSPECT_MIXED_INSTALL_SCOPE_REFUSED"):
        mod.main(["--inspect","--confirm-scope",mod.SCOPE])


def test_native_selection_head_is_unchanged_and_source_not_installed():
    assert mod._r14_unchanged() is True
    assert not mod.TARGET.exists()


def test_active_copy_admission_does_not_rerun_empty_target_check(monkeypatch):
    """After intent journal, a new-target check would reject our own operation."""
    events=[]
    class FakeGuard:
        checks=0
        last_ntp_admission=None
        last_host_admission=None
        def tick(self):
            self.checks+=1
            return True
        def monotonic(self):
            return 123.0
    class FakeClock:
        def require_operational(self,identity):
            assert identity==mod.CLOCK_IDENTITY
            events.append("CLOCK")
    guard=FakeGuard()
    monkeypatch.setattr(mod,"require_code_install_host_ready",
                        lambda *_:events.append("HOST"))
    monkeypatch.setattr(mod,"_r14_unchanged",
                        lambda:events.append("R14_NATIVE"))
    monkeypatch.setattr(mod,"require_new_native_target",
                        lambda *_:pytest.fail("OWN_INTENT_JOURNAL_MUST_NOT_TRIGGER_NEW_TARGET_TEST"))
    assert mod._admit(clock=FakeClock(),guard=guard) is True
    assert events==["CLOCK","HOST","R14_NATIVE"]
    assert mod._admit(clock=FakeClock(),guard=guard) is True
    assert events==["CLOCK","HOST","R14_NATIVE"]


def test_r15_installer_source_hash_must_be_in_operator_approval():
    record=sample_approval()
    record["installer_source_sha256"]="0"*64
    with pytest.raises(ValueError,match="EXACT_SID_BOUND_ONE_SHOT"):
        mod.validate_operator_decision(record,sid="S-1-5-21-1-2-3-1001")


def test_future_installed_r15_receipt_ack_matches_existing_native_verifier():
    from scripts.release_selection import validate_native_install_ack, validate_spec
    from scripts.install_verified_release import write_new_json
    import hashlib
    receipt={
        "schema":"ATLAS_QD_D_RUNTIME_INSTALLATION_V1",
        "stage":"D_RUNTIME_LAYOUT_VERIFIED",
        "release_path":str(mod.TARGET),
        "source_commit":mod.SOURCE_COMMIT,
        "files":[{"path":"python/python.exe","bytes":1,
                  "sha256":"0"*64,"id":[1,2,3]}],
        "directories":[{"path":".","id":[3,4,5]}],
        "archive_sha256":mod.ARCHIVE_SHA,
        "inventory_sha256":mod.INVENTORY_SHA,
        "selected":False,"financial_effects":False,
        "provider_connections":False,"operational_acceptance":False,
        "layout":{"version":[3,12]},
        "artifact_digest":"a"*64,
    }
    ack=mod.final_native_install_ack(receipt)
    receipt_sha=hashlib.sha256(json.dumps(
        receipt,sort_keys=True,allow_nan=False).encode()).hexdigest()
    assert ack=={"stage":"UNSELECTED_CODE_INSTALL_VERIFIED",
                 "receipt_sha256":receipt_sha}
    selection=validate_spec({
        "schema":"QD_INSTALLED_RELEASE_REFERENCE_V1",
        "domain":"WINDOWS_LOCAL",
        "release":mod.SOURCE_COMMIT,
        "root":str(mod.TARGET),
        "receipt":str(mod.RECEIPT),
        "receipt_sha256":receipt_sha,
        "artifact_digest":"a"*64,
    },"WINDOWS_LOCAL")
    legacy=json.dumps({"schema":"ATLAS_R15_UNSELECTED_CODE_INSTALL_INTENT_V1"}).encode()
    complete=legacy+b"\n"+json.dumps(ack).encode()
    assert validate_native_install_ack(selection,receipt,complete) is True
    with pytest.raises(ValueError,match="SELECTION_INSTALL_ACK_REQUIRED"):
        validate_native_install_ack(selection,receipt,legacy)
    assert not mod.RECEIPT.exists()


@pytest.mark.parametrize("bad",[
    {"source_commit":"f"*40},
    {"selected":True},
    {"financial_effects":True},
    {"provider_connections":True},
    {"operational_acceptance":True},
    {"artifact_digest":None},
])
def test_final_receipt_ack_never_expands_financial_authority(bad):
    receipt={
        "stage":"D_RUNTIME_LAYOUT_VERIFIED",
        "source_commit":mod.SOURCE_COMMIT,
        "release_path":str(mod.TARGET),
        "artifact_digest":"1"*64,
        "selected":False,"financial_effects":False,
        "provider_connections":False,"operational_acceptance":False,
    }
    receipt.update(bad)
    with pytest.raises(ValueError,match="FINAL_NONFINANCIAL_RECEIPT_REQUIRED"):
        mod.final_native_install_ack(receipt)


def test_source_digest_stays_bound_when_only_one_approval_pin_is_inserted(monkeypatch,tmp_path):
    """Source-SHA must ignore only the exact pin token, not any code change."""
    raw=Path(mod.__file__).read_bytes()
    baseline=mod.approval_source_sha256()
    original=b'APPROVAL_SHA256 = None  # Cannot become an install grant from chat or old R14 consent.'
    replacement=b'APPROVAL_SHA256 = "'+b'a'*64+b'"  # Cannot become an install grant from chat or old R14 consent.'
    assert sum(line == original for line in raw.splitlines())==1
    simulated=tmp_path/"atlas_installer_single_pin_simulated.py"
    simulated.write_bytes(raw.replace(b'\n'+original+b'\n',b'\n'+replacement+b'\n',1))
    monkeypatch.setattr(mod,"__file__",str(simulated))
    assert mod.approval_source_sha256()==baseline
    # Other changes cannot be concealed by the pin normalization.
    simulated.write_bytes(simulated.read_bytes()+b"\n# unreviewed mutation\n")
    assert mod.approval_source_sha256()!=baseline


def test_native_copier_receives_started_marker_before_create_only_journal():
    import inspect
    code=inspect.getsource(mod.install)
    assert code.index('prepared["started"] = time.monotonic()') < code.index(
        'write_new_json(journal,')
    assert code.index('prepared["started"] = time.monotonic()') < code.index(
        'copied=_copy_prepared_code(')
