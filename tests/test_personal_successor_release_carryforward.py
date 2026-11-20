"""R27 native empty-root approvals cannot be replayed, forged or widened.

All fixtures live under disposable test directories; no actual financial
account, historical coordination journal, data provider or order is modified.
"""
import hashlib
import json

import pytest

from app.services.paper_financial_replay import digest
from scripts.observation_runtime import personal_successor_release_carryforward as carry
from scripts.observation_runtime.personal_successor_native_root_scope import successor_root_plan

NEW_SOURCE="c"*40
NEW_ARTIFACT="d"*64


def evidence(monkeypatch,tmp_path):
    plan=successor_root_plan(
        successor_release=carry.R27_SOURCE,epoch_nonce=carry.EPOCH_NONCE)
    packet={
        "selected_release":carry.R27_SOURCE,
        "selected_artifact_digest":carry.R27_ARTIFACT,
        "plan":plan,
        "new_operator_financial_review_completed":False,
        "new_financial_journals_created":0,"simulated_accounts_initialized":0,
        "successor_terms_review":{"R26_economics":"PINNED_UNCHANGED"},
    }
    packet["successor_terms_review_digest"]=digest(packet["successor_terms_review"])
    root_ids={lane:{
        "epoch":plan["lanes"][lane]["epoch"],
        "roots":{role:{"path":path,"native_id":[i+1,10,2 if lane=="QUALITY_DIPS" else 3],
                       "native_identity_verified":True,
                       "existing_empty_namespace_verified":True}
                  for i,(role,path) in enumerate(plan["lanes"][lane]["roots"].items())}}
        for lane in plan["lanes"]}
    scope={
        "scope":"APPROVE_ATLAS_R27_CREATE_ONLY_12_NEW_SIMULATED_ACCOUNT_DIRS_NO_PAPER_START",
        "successor_release":carry.R27_SOURCE,
        "successor_release_digest":carry.R27_ARTIFACT,
        "terms_review_digest":packet["successor_terms_review_digest"],
        "plan_digest":digest(plan),
    }
    intent={
        "status":"CREATE_ONLY_NATIVE_DIRECTORY_ATTEMPT_STARTED",
        "operator_sid":"S-1-5-PINNED_TEST","scope":scope,
    }
    success={
        "schema":"ATLAS_R27_ONE_TIME_NATIVE_NEW_SIMULATED_ACCOUNT_ROOT_PROVISIONING_V1",
        "status":"TWELVE_NEW_EMPTY_ROOTS_NATIVE_ID_VERIFIED_NOT_FINANCIAL_AUTHORITY",
        "intent_sha256":"",
        "scope":scope,"native_12_roots":{
            "native_root_ids_verified":12,"all_twelve_distinct_and_empty":True,
            "lanes":root_ids},
        "new_financial_directories_created":14,
        "new_journals_created":0,"new_accounts_opened":0,
        "paper_start_authorized":False,"live_money_trading_authorized":False,
    }
    selector={
        "native_id":[10,20,30],
        "record":{"revision":27,"selected":{
            "release":carry.R27_SOURCE,
            "artifact_digest":carry.R27_ARTIFACT}},
    }
    def save(name,data):
        path=tmp_path/name
        path.write_text(json.dumps(data,sort_keys=True,separators=(",",":"))+"\n",encoding="utf8")
        return path,hashlib.sha256(path.read_bytes()).hexdigest()
    paths,pins={},{}
    for k,record in (("REVIEW",packet),("ATTEMPT",intent),
                     ("SUCCESS",success),("SELECTED_R27",selector)):
        paths[k],pins[k]=save(k+".json",record)
    success["intent_sha256"]=pins["ATTEMPT"]
    paths["SUCCESS"],pins["SUCCESS"]=save("SUCCESS.json",success)
    for k in paths:
        monkeypatch.setattr(carry,k,paths[k])
        monkeypatch.setattr(carry,k+"_SHA",pins[k])
    monkeypatch.setattr(carry,"current_sid",lambda:"S-1-5-PINNED_TEST")
    return plan,paths,pins,packet,intent,success,selector


def test_only_one_exact_provisioned_r27_epoch_carries_to_new_code(monkeypatch,tmp_path):
    p,_,_,_,_,_,_=evidence(monkeypatch,tmp_path)
    proof,roots=carry.verified_carried_r27_roots(
        plan=p,selected_code_release=NEW_SOURCE,
        selected_code_digest=NEW_ARTIFACT)
    assert proof["status"]=="ORIGINAL_R27_PROTECTED_EMPTY_ROOTS_REVIEWED_CODE_ONLY_CARRY_NO_ACCOUNTS"
    assert proof["original_R27_artifact_digest"]==carry.R27_ARTIFACT
    assert proof["selected_code_artifact_digest"]==NEW_ARTIFACT
    assert roots["native_root_ids_verified"]==12
    assert proof["new_financial_account_approval_issued"] is False
    assert proof["new_financial_journal_creation_authorized"] is False
    assert proof["paper_start_authorized"] is False
    assert proof["live_money_trading_authorized"] is False
    assert proof["original_R26_accounts_adopted"] is False


@pytest.mark.parametrize("damage",[
    "reused_r27_binary","same_r27_artifact","wrong_epoch",
    "wrong_old_source","wrong_new_source","bad_new_artifact",
    "operator_changed","tampered_intent","tampered_receipt",
    "tampered_review","tampered_selector",
])
def test_native_carryforward_rejects_unapproved_or_changed_inputs(
        monkeypatch,tmp_path,damage):
    p,paths,_,_,_,_,_=evidence(monkeypatch,tmp_path)
    source,dgst=NEW_SOURCE,NEW_ARTIFACT
    if damage=="reused_r27_binary":source=carry.R27_SOURCE
    elif damage=="same_r27_artifact":dgst=carry.R27_ARTIFACT
    elif damage=="wrong_epoch":
        p=successor_root_plan(successor_release=carry.R27_SOURCE,
                              epoch_nonce="0"*24)
    elif damage=="wrong_old_source":
        p=successor_root_plan(successor_release="e"*40,
                              epoch_nonce=carry.EPOCH_NONCE)
    elif damage=="wrong_new_source":source="ZZZ"
    elif damage=="bad_new_artifact":dgst="bad"
    elif damage=="operator_changed":
        monkeypatch.setattr(carry,"current_sid",lambda:"S-1-5-FOREIGN")
    elif damage=="tampered_intent":paths["ATTEMPT"].write_text('{"scope":"FORGED"}')
    elif damage=="tampered_receipt":paths["SUCCESS"].write_text('{"status":"FAKE_SUCCESS"}')
    elif damage=="tampered_review":paths["REVIEW"].write_text('{"accounts":"FAKE"}')
    elif damage=="tampered_selector":paths["SELECTED_R27"].write_text('{"record":"FAKE"}')
    with pytest.raises((ValueError,KeyError)):
        carry.verified_carried_r27_roots(
            plan=p,selected_code_release=source,selected_code_digest=dgst)
