"""Fresh selected successor Stage C: disposable in-memory only contracts."""
import copy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.services.paper_financial_replay import body,digest
from scripts.observation_runtime import personal_successor_stage_c_candidates as candidate
from scripts.observation_runtime import personal_successor_account_terms_review as terms
from scripts.observation_runtime import personal_successor_native_root_scope as scope

SOURCE="e"*40
ARTIFACT="f"*64
NONCE="1234567890abcdef12345678"


def system(monkeypatch,tmp_path):
    plan=scope.successor_root_plan(successor_release=SOURCE,epoch_nonce=NONCE)
    original_process={"pid":101,"creation_filetime":1001,
                      "image":r"D:\AtlasRuntime\releases\old\python\python.exe"}
    process={"pid":202,"creation_filetime":2002,
             "image":r"D:\AtlasRuntime\releases\new\python\python.exe"}
    class Job:
        identity=copy.deepcopy(process)
        def verify(self):return True
    class Release:
        root=Path("D:/AtlasRuntime/releases")/SOURCE
        artifact_digest=ARTIFACT
    class Clock:
        def __init__(self):self.now=1795104014
        def __call__(self):return self.now
        def require_operational(self,runtime_id):
            assert runtime_id=="EXACT_SUCCESSOR"
    class Admission:
        def __init__(self,*,release):
            self.release=release
        def verify(self,*,release_digest):
            return {"verified":True} if release_digest==ARTIFACT else None
    originals={};reviews={};economic_pins={};enrollment_pins={};manifest_pins={}
    roots={"schema":"ATLAS_TWO_LANE_EXISTING_NATIVE_ROOT_PRE_ENROLLMENT_V1",
           "native_root_total":12,"native_root_ids_verified":12,
           "all_twelve_distinct_and_empty":True,"lanes":{}}
    for lane in scope.LANES:
        economics={"schema":"TEST_PAPER_SCHEMA","opening_cash":"1000",
                   "currency":"USD" if lane=="QUALITY_DIPS" else "USDC",
                   "initial_net_r":"0","timezone":"UTC",
                   "autonomous_policy":{"schema":"FAKE_POLICY"},
                   "perp_policy":{"schema":"FAKE_PERP","taker_bps":"10"}}
        economic_pins[lane]=digest(economics)
        original={
            "schema":"TEST_ENROLLMENT","profile":"AUTONOMOUS_PAPER_ONLY_V1",
            "account_id":terms.ORIGINAL_ACCOUNTS[lane],
            "epoch":terms.ORIGINAL_EPOCHS[lane],
            "release_digest":terms.R26_DIGEST,
            "acceptance_id":"R26_APPROVAL_FOR_ORIGINAL_ONLY",
            "writers":{"source":{"schema":"QD_OP_PROCESS_ID_V1",**original_process}},
            "resources":{
                role:{"schema":("QD_AUTO_NATIVE_ROOT_V4" if lane=="QUALITY_DIPS"
                                else "PERP_AUTO_NATIVE_ROOT_V1"),
                      "path":"D:\\synthetic\\"+lane+"\\"+role,
                      "native_id":[1,index+1,1 if lane=="QUALITY_DIPS" else 2]}
                for index,role in enumerate(scope.ROLES)
            }}
        originals[lane]=original
        enrollment_pins[lane]=digest(original)
        manifest_pins[lane]=digest("ORIGINAL_MANIFEST_"+lane)
        row={}
        for idx,role in enumerate(scope.ROLES):
            row[role]={"path":plan["lanes"][lane]["roots"][role],
                       "native_id":[1,idx+1,1 if lane=="QUALITY_DIPS" else 2],
                       "native_identity_verified":True,
                       "existing_empty_namespace_verified":True}
        roots["lanes"][lane]={"epoch":plan["lanes"][lane]["epoch"],"roots":row}
        reviews[lane]={
            "lane":lane,"new_epoch":plan["lanes"][lane]["epoch"],
            "new_account_id":terms.ORIGINAL_ACCOUNTS[lane]+"-recovery-"+NONCE,
            "new_release_digest":ARTIFACT,
            "old_original_enrollment_digest":enrollment_pins[lane],
            "old_original_manifest_digest":manifest_pins[lane],
            "economic_terms_digest":economic_pins[lane],
            "exact_economic_terms":economics,
            "prospective_paths":plan["lanes"][lane]["roots"],
            "opening_timestamp_pending_independent_native_UTC":True,
            "new_native_resource_ids_pending":True,
            "new_windows_process_writer_roster_pending":True,
            "new_local_operator_financial_review_required":True,
            "account_initialized":False}
    packet={
        "schema":terms.SCHEMA,
        "status":"EXACT_NEW_EPOCH_TERMS_FOR_OPERATOR_REVIEW_ONLY",
        "source":"TWO_VERIFIED_ORIGINAL_R26_JOURNAL_MANIFESTS",
        "successor_release":SOURCE,"epoch_nonce":NONCE,
        "successor_artifact_digest":ARTIFACT,
        "accounts":reviews,"old_approval_transferred":False,
        "new_operator_approval_issued":False,
        "new_journal_or_account_created":False,
        "original_R26_immutable":True,
        "paper_start_authorized":False,
        "live_money_trading_authorized":False}
    class Historian:
        def __init__(self):
            self.release=Release()
            self.old_enrollments=originals
            self.valid=True
        def capture(self):
            if not self.valid:raise ValueError("R26_HISTORY_TAMPER")
            return {"original_journals_verified":2,
                    "original_financial_account_publications":0,
                    "historical_writer_adoption_authorized":False}
    class Scope:
        def __init__(self):
            self.plan=plan
            self.historical_guard=Historian()
            self.actual=roots
        def inspect(self):return copy.deepcopy(self.actual)
    monkeypatch.setattr(candidate,"NativeOriginalSelfJob",Job)
    monkeypatch.setattr(candidate,"NativePersonalReleaseIdentity",Release)
    monkeypatch.setattr(candidate,"NativeVersionSafePaperOperatorClock",Clock)
    monkeypatch.setattr(candidate,"NativeFinancialReleaseAdmission",Admission)
    monkeypatch.setattr(candidate,"NativeSelectedSuccessorEpochRoots",Scope)
    monkeypatch.setattr(candidate,"__file__",str(Release.root/
        "scripts/observation_runtime/personal_successor_stage_c_candidates.py"))
    monkeypatch.setattr(candidate,"observe_self",lambda:copy.deepcopy(process))
    monkeypatch.setattr(candidate,"require_version_safe_release_digest",lambda **kw:True)
    monkeypatch.setattr(candidate,"validate_policy",lambda p:copy.deepcopy(p))
    monkeypatch.setattr(candidate,"validate_manifest",lambda p:None)
    def strict_resource_contract(entry):
        lane=entry["lane"]
        expected="QD_AUTO_NATIVE_ROOT_V4" if lane=="QUALITY_DIPS" else "PERP_AUTO_NATIVE_ROOT_V1"
        resources=entry["native_enrollment"]["resources"]
        assert set(resources)==set(scope.ROLES)
        for value in resources.values():
            assert set(value)=={"schema","path","native_id"}
            assert value["schema"]==expected
        return entry["lane"],entry["native_enrollment"],entry["parameters"]
    monkeypatch.setattr(candidate,"validate_personal_inception",strict_resource_contract)
    monkeypatch.setattr(candidate,"ORIGINAL_ENROLLMENT_DIGESTS",enrollment_pins)
    monkeypatch.setattr(candidate,"ORIGINAL_MANIFEST_DIGESTS",manifest_pins)
    monkeypatch.setattr(candidate,"ORIGINAL_ECONOMIC_DIGESTS",economic_pins)
    from scripts.volume_inspector import windows_output
    monkeypatch.setattr(windows_output,"current_sid",lambda:"S-1-5-SYNTHETIC")
    from scripts.observation_runtime import personal_successor_root_provision_once as provisioning
    monkeypatch.setattr(provisioning,"_attempt_paths",
                        lambda plan:(tmp_path/"intent.json",tmp_path/"success.json"))
    intent={
        "status":"CREATE_ONLY_NATIVE_DIRECTORY_ATTEMPT_STARTED",
        "operator_sid":"S-1-5-SYNTHETIC",
        "scope":provisioning.exact_scope(
            plan=plan,successor_release_digest=ARTIFACT,
            terms_review_digest=digest(packet)),
    }
    (tmp_path/"intent.json").write_text(json.dumps(intent,sort_keys=True),encoding="utf8")
    raw=(tmp_path/"intent.json").read_bytes()
    import hashlib
    receipt={
        "schema":provisioning.SCHEMA,
        "status":"TWELVE_NEW_EMPTY_ROOTS_NATIVE_ID_VERIFIED_NOT_FINANCIAL_AUTHORITY",
        "intent_sha256":hashlib.sha256(raw).hexdigest(),
        "scope":intent["scope"],"native_12_roots":roots,
        "new_financial_directories_created":14,
        "new_accounts_opened":0,"new_journals_created":0,
        "paper_start_authorized":False,
        "live_money_trading_authorized":False,
    }
    (tmp_path/"success.json").write_text(json.dumps(receipt,sort_keys=True),encoding="utf8")
    approval_ids={lane:"R27_REVIEWED_"+lane+"_NEW_INDEPENDENT" for lane in scope.LANES}
    approved={}
    for lane in scope.LANES:
        manifest={**reviews[lane]["exact_economic_terms"],
                  "release":ARTIFACT,"epoch":reviews[lane]["new_epoch"]}
        approved[lane]=digest(manifest)
    new_scope=Scope()
    new_clock=Clock()
    args={
        "self_job":Job(),"release":new_scope.historical_guard.release,
        "clock":new_clock,"runtime_id":"EXACT_SUCCESSOR",
        "successor_root_scope":new_scope,
        "reviewed_successor_terms":packet,
        "personal_policy":{"simulation_only":True},
        "operator_acceptance_ids":approval_ids,
        "approved_unstamped_manifest_digests":approved,
    }
    return SimpleNamespace(**locals())


def test_exact_in_memory_stage_c_never_initializes_accounts(monkeypatch,tmp_path):
    s=system(monkeypatch,tmp_path)
    before=copy.deepcopy((s.originals,s.packet,s.roots))
    candidates,admission=candidate.prepare_fresh_successor_account_candidates(**s.args)
    assert type(admission) is s.Admission
    assert set(candidates)==set(scope.LANES)
    for lane,item in candidates.items():
        m=item["parameters"];e=item["native_enrollment"]
        assert m["release"]==ARTIFACT
        assert m["opened_at"]==1795104014
        assert e["account_id"]!=terms.ORIGINAL_ACCOUNTS[lane]
        assert e["epoch"]!=terms.ORIGINAL_EPOCHS[lane]
        assert e["inception_digest"]==digest(m)
        assert e["release_digest"]==ARTIFACT
        assert e["resources"]["coordination"]["path"]==s.plan["lanes"][lane]["roots"]["coordination"]
        assert e["acceptance_id"]==s.approval_ids[lane]
        assert len(set(digest(v) for v in e["writers"].values()))==1
        assert item["personal_policy"]["simulation_only"] is True
    assert (s.originals,s.packet,s.roots)==before
    assert not any("initialize" in k or "publish" in k for k in candidates)


@pytest.mark.parametrize("damage",[
    "fake_root_scope","bad_history","new_release_mismatch","old_operator_approval",
    "reused_R26_account","wrong_fee","wrong_cash","foreign_root",
    "existing_financial_publication","wrong_operator_approval",
    "new_financial_digest_missing","wrong_owner_pid","missing_provisioning_receipt",
    "receipt_wrong_terms","receipt_wrong_sid","native_root_id_changed",
    "clock_expired","stale_accepted_financial_terms",
])
def test_stage_c_refuses_new_epoch_identity_or_authority_drift(monkeypatch,tmp_path,damage):
    s=system(monkeypatch,tmp_path)
    q=s.packet["accounts"]["QUALITY_DIPS"]
    if damage=="fake_root_scope":s.args["successor_root_scope"]=object()
    elif damage=="bad_history":s.new_scope.historical_guard.valid=False
    elif damage=="new_release_mismatch":s.new_scope.historical_guard.release.artifact_digest="a"*64
    elif damage=="old_operator_approval":s.packet["old_approval_transferred"]=True
    elif damage=="reused_R26_account":q["new_account_id"]=terms.ORIGINAL_ACCOUNTS["QUALITY_DIPS"]
    elif damage=="wrong_fee":q["exact_economic_terms"]["fees_bps"]="90"
    elif damage=="wrong_cash":q["exact_economic_terms"]["opening_cash"]="2000"
    elif damage=="foreign_root":q["prospective_paths"]["coordination"]=r"D:\AtlasPaper\QualityDips\OLD"
    elif damage=="existing_financial_publication":
        old=s.new_scope.historical_guard.capture
        s.new_scope.historical_guard.capture=lambda:{**old(),"original_financial_account_publications":1}
    elif damage=="wrong_operator_approval":
        s.args["operator_acceptance_ids"]["QUALITY_DIPS"]="R26_OLD_APPROVAL"
    elif damage=="new_financial_digest_missing":
        s.args["approved_unstamped_manifest_digests"].pop("QUALITY_DIPS")
    elif damage=="wrong_owner_pid":
        s.args["self_job"].identity={"pid":999,"creation_filetime":3,"image":"D:\\OTHER"}
    elif damage=="missing_provisioning_receipt":(tmp_path/"success.json").unlink()
    elif damage=="receipt_wrong_terms":
        value=json.loads((tmp_path/"success.json").read_bytes())
        value["scope"]["terms_review_digest"]="0"*64
        (tmp_path/"success.json").write_text(json.dumps(value))
    elif damage=="receipt_wrong_sid":
        value=json.loads((tmp_path/"intent.json").read_bytes())
        value["operator_sid"]="FOREIGN"
        (tmp_path/"intent.json").write_text(json.dumps(value))
    elif damage=="native_root_id_changed":
        s.new_scope.actual["lanes"]["QUALITY_DIPS"]["roots"]["source"]["native_id"]=[8,8,8]
    elif damage=="clock_expired":s.new_clock.now=-1
    elif damage=="stale_accepted_financial_terms":
        s.args["approved_unstamped_manifest_digests"]["QUALITY_DIPS"]="a"*64
    with pytest.raises((ValueError,TypeError,AttributeError)):
        candidate.prepare_fresh_successor_account_candidates(**s.args)
