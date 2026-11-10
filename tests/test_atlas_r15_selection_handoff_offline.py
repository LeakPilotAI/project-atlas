"""R15 selection handoff only; no native publication or installation."""
import copy
import hashlib
import json

import pytest

from scripts import atlas_r15_selection_handoff as handoff
from scripts import release_selection
from scripts.atlas_r15_code_only_installer import final_native_install_ack


@pytest.fixture(scope="module")
def receipt_and_journal():
    files=[{
        "path":f"python/_synthetic_{n:05d}.dat",
        "bytes":1,
        "sha256":"0"*64,
        "id":[1,1,n+100],
    } for n in range(handoff.EXPECTED_FILES)]
    dirs=[{"path":".","id":[1,1,1]}] + [
        {"path":f"python/synthetic_{n:04d}","id":[1,1,n+2]}
        for n in range(handoff.EXPECTED_DIRECTORIES-1)
    ]
    assert len(files)==10526 and len(dirs)==912
    receipt={
        "schema":"ATLAS_QD_D_RUNTIME_INSTALLATION_V1",
        "stage":"D_RUNTIME_LAYOUT_VERIFIED",
        "release_path":str(handoff.TARGET),
        "source_commit":handoff.SOURCE_COMMIT,
        "files":files,
        "directories":dirs,
        "archive_sha256":handoff.ARCHIVE_SHA,
        "inventory_sha256":handoff.INVENTORY_SHA,
        "selected":False,
        "financial_effects":False,
        "provider_connections":False,
        "operational_acceptance":False,
        "layout":{"version":[3,12]},
    }
    receipt["artifact_digest"]=hashlib.sha256(json.dumps(
        files,sort_keys=True,separators=(",",":")).encode()).hexdigest()
    raw=json.dumps(receipt,sort_keys=True,allow_nan=False).encode()
    first={
        "schema":"ATLAS_R15_UNSELECTED_CODE_INSTALL_INTENT_V1",
        "source_commit":handoff.SOURCE_COMMIT,
        "archive_sha256":handoff.ARCHIVE_SHA,
        "target":str(handoff.TARGET),
        "selection_allowed":False,
        "financial_authority":False,
        "provider_access":False,
        "startup_authorized":False,
    }
    second=final_native_install_ack(receipt)
    journal=(json.dumps(first,sort_keys=True).encode()+b"\n"+
             json.dumps(second,sort_keys=True).encode())
    return receipt,raw,journal


def test_install_not_present_and_current_r14_only_is_selected():
    result=handoff.inspect()
    assert result["schema"]=="ATLAS_R15_CODE_SELECTION_HANDOFF_V1"
    if handoff.TARGET.is_dir():
        assert result["status"]=="SOURCE_ONLY_CANDIDATE_REQUIRES_NATIVE_HANDLE_VERIFIER_AND_ONE_SHOT_SELECTION_APPROVAL"
        assert result["proposed_row_digest"]=="274f5b00ee0e2f6271c6dd1dc5316f7d9124e932483038a6d93ef62ddbd2cd25"
    else:
        assert result["status"]=="WAITING_FOR_SEPARATELY_AUTHORIZED_R15_CODE_ONLY_NATIVE_INSTALL"
    assert result["source_commit"]==handoff.SOURCE_COMMIT
    assert result["selected_native_predecessor"]=="R14"
    assert result["expected_revision"]==14
    assert result["new_selection_record_written"] is False
    assert result["selection_authorized"] is False
    assert result["financial_authority"] is False
    assert not (handoff.SELECTION_ROOT/"r0014.json").exists()
    assert not (handoff.SELECTION_ROOT/"r0014.json").exists()


def test_exact_synthetic_installed_receipt_produces_nonpublishing_r0014(
        receipt_and_journal):
    receipt,raw,journal=receipt_and_journal
    row=handoff.candidate_from_receipt(
        receipt=receipt,receipt_bytes=raw,journal_bytes=journal)
    assert set(row)=={
        "schema","domain","revision","action",
        "operation","previous","selected","restores",
    }
    assert row["revision"]==14 and row["action"]=="SELECT"
    assert row["previous"]==handoff.R14_HEAD
    assert row["restores"] is None
    assert row["selected"]["receipt_sha256"]==hashlib.sha256(raw).hexdigest()
    assert row["selected"]["artifact_digest"]==receipt["artifact_digest"]
    assert release_selection.digest(row)==release_selection.digest(
        handoff.candidate_from_receipt(
            receipt=receipt,receipt_bytes=raw,journal_bytes=journal))
    assert release_selection.validate_native_install_ack(
        row["selected"],receipt,journal) is True


@pytest.mark.parametrize("field,value",[
    ("source_commit","f"*40),
    ("release_path","D:/wrong"),
    ("archive_sha256","0"*64),
    ("inventory_sha256","0"*64),
    ("selected",True),
    ("financial_effects",True),
    ("provider_connections",True),
    ("operational_acceptance",True),
    ("artifact_digest","0"*64),
])
def test_unauthorized_or_foreign_synthetic_receipt_is_refused(
        receipt_and_journal,field,value):
    original,_,journal=receipt_and_journal
    receipt=copy.deepcopy(original)
    receipt[field]=value
    raw=json.dumps(receipt,sort_keys=True).encode()
    with pytest.raises(ValueError,match="R15_SELECTION"):
        handoff.candidate_from_receipt(
            receipt=receipt,receipt_bytes=raw,journal_bytes=journal)


@pytest.mark.parametrize("mutation",[
    "remove_ack","add_ack","wrong_ack_sha","wrong_intent","noncanonical_receipt",
])
def test_torn_or_forged_create_only_journal_refused(receipt_and_journal,mutation):
    receipt,raw,journal=receipt_and_journal
    if mutation=="remove_ack":
        journal=journal.splitlines()[0]
    elif mutation=="add_ack":
        journal+=b"\n"+journal.splitlines()[-1]
    elif mutation=="wrong_ack_sha":
        first,second=journal.splitlines()
        row=json.loads(second)
        row["receipt_sha256"]="0"*64
        journal=first+b"\n"+json.dumps(row).encode()
    elif mutation=="wrong_intent":
        first,second=journal.splitlines()
        row=json.loads(first)
        row["financial_authority"]=True
        journal=json.dumps(row).encode()+b"\n"+second
    else:
        raw=json.dumps(receipt,indent=2,sort_keys=True).encode()
    with pytest.raises(ValueError):
        handoff.candidate_from_receipt(
            receipt=receipt,receipt_bytes=raw,journal_bytes=journal)


def test_missing_or_forged_r14_anchor_is_refused():
    valid={
        "revision":13,
        "selected_release":"7ff9d3dba2eabe110f843c13efac49464805de2a",
        "native_selection_head":handoff.R14_HEAD,
        "native_selection_record_verified":True,
        "financial_authority":False,
    }
    assert handoff.validate_existing_r14_selected(valid)
    for change in ({"revision":12},{"native_selection_head":"f"*64},
                   {"native_selection_record_verified":False},
                   {"financial_authority":True}):
        row={**valid,**change}
        with pytest.raises(ValueError,match="NATIVE_R14_ANCHOR_REQUIRED"):
            handoff.validate_existing_r14_selected(row)


def test_pure_handoff_can_never_publish_selection(capsys):
    assert handoff.main(["--inspect"])==2
    result=json.loads(capsys.readouterr().out)
    assert result["new_selection_record_written"] is False
    with pytest.raises(SystemExit):
        handoff.main(["--publish"])
