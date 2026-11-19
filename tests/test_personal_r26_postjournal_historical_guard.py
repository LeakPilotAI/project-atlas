"""R26 historical postjournal read guard: disposable memory, no native files."""
import copy
import sqlite3
from contextlib import nullcontext
from types import SimpleNamespace
from pathlib import Path

import pytest
from app.services.paper_financial_replay import body,digest
import scripts.observation_runtime.personal_r26_postjournal_historical_guard as target


def fixture(monkeypatch):
    historical={"pid":110,"creation_filetime":774411,"image":r"D:\AtlasRuntime\releases\original\python\python.exe"}
    fresh={"pid":220,"creation_filetime":774422,"image":r"D:\AtlasRuntime\releases\successor\python\python.exe"}
    class Job:
        def __init__(self):
            self.identity=copy.deepcopy(fresh)
            self.alive=True
        def verify(self):return self.alive
    class Release:
        def __init__(self):
            self.artifact_digest="c"*64
            self.root=target.SOURCE_RELEASE/"1111111111111111111111111111111111111111"
    class Admission:
        def __init__(self):
            self.release=Release()
            self.valid=True
        def verify(self,*,release_digest):
            if not self.valid or release_digest!=self.release.artifact_digest:return None
            return {"selected_artifact_digest_bound":True}
    monkeypatch.setattr(target,"NativeOriginalSelfJob",Job)
    monkeypatch.setattr(target,"NativeFinancialReleaseAdmission",Admission)
    monkeypatch.setattr(target,"NativePersonalReleaseIdentity",Release)
    monkeypatch.setattr(target,"__file__",str(
        target.SOURCE_RELEASE/"1111111111111111111111111111111111111111"/
        "scripts/observation_runtime/personal_r26_postjournal_historical_guard.py"))
    job=Job();admission=Admission()
    monkeypatch.setattr(target,"observe_self",lambda:copy.deepcopy(fresh))
    exits=[True]
    def previous_exited(previous):
        if not exits[0]:raise ValueError("ORIGINAL_STILL_ALIVE")
        assert previous==historical
        return {"excluded":"ORIGINAL_PROCESS_EXITED_NATIVE_CROSSCHECK"}
    monkeypatch.setattr(target,"verify_previous_exited",previous_exited)
    enrollments={};roster={};roots={"lanes":{},"native_root_total":12,
       "native_root_ids_verified":12,"existing_empty_root_namespaces":10,
       "all_twelve_distinct_and_empty":False}
    count=1
    for lane in target.LANES:
        resources={};natives={}
        for role in ("source","projection","report","control","coordination","custody"):
            loc=rf"D:\synthetic\{lane}\{role}"
            identity=[123,count,999];count+=1
            resources[role]={"path":loc,"native_id":identity}
            natives[role]={"path":loc,"native_id":identity,
                "existing_empty_namespace_verified":role!="coordination"}
        e={"profile":"SYNTHETIC_TEST","schema":"SYNTHETIC_R26_ONLY",
           "account_id":lane+"-A","epoch":lane+"-E",
           "release_digest":target.R26_DIGEST,
           "writers":{"a":copy.deepcopy(historical)},"resources":resources,
           "inception_digest":None}
        enrollments[lane]=e
        roots["lanes"][lane]={"roots":natives}
    manifest={"schema":"SYNTHETIC_ORIGINAL_FIRST_COORDINATION","cash":"1000"}
    db=sqlite3.connect(":memory:")
    try:
        db.executescript("""
        CREATE TABLE inception(body TEXT);
        CREATE TABLE events(id INTEGER);
        CREATE TABLE projections(id INTEGER);
        CREATE TABLE personal_sessions(id INTEGER);
        CREATE TABLE personal_publications(id INTEGER);
        """)
        db.execute("INSERT INTO inception VALUES (?)",(body(manifest),))
        db.commit()
        image=db.serialize()
    finally:db.close()
    for e in enrollments.values():
        e["inception_digest"]=digest(manifest)
    monkeypatch.setattr(target,"validate_qd",lambda value:copy.deepcopy(value))
    monkeypatch.setattr(target,"validate_hl",lambda value:copy.deepcopy(value))
    monkeypatch.setattr(target,"inspect_two_lane_native_roots",lambda:copy.deepcopy(roots))
    images={"image":image,"revision":1,"read_calls":0,"closes":0}
    class Image:
        def __init__(self,*,root,native_root,enrollment_digest):
            assert root.startswith("D:\\synthetic")
            self.enrollment_digest=enrollment_digest
        def read_view(self):return nullcontext()
        def _load(self):
            images["read_calls"]+=1
            return images["image"],{"revision":images["revision"]}
        def close(self):images["closes"]+=1
    monkeypatch.setattr(target,"NativePersonalCoordinationImages",Image)
    monkeypatch.setattr(target.PersonalNativeCoordination,"initial_image",
                        staticmethod(lambda value:image if value==manifest else b"WRONG"))
    approval={"origin":"LOCAL_OPERATOR","actions":["READ_ONLY","INITIALIZE_SIMULATED_ACCOUNTS"],
              "accounts":{lane:digest(e) for lane,e in enrollments.items()},
              "original_only":True}
    failure={"phase":"ORIGINAL_STAGE_D_E_F_ONCE_POSSIBLY_IRREVERSIBLE",
             "error":"PERSONAL_TECHNICAL_CHECKS_FAILED","attempt_reserved":True}
    inputs={"job":job}
    def construct():
        return target.NativeR26HistoricalPostjournalGuard(
            self_job=inputs["job"],release_admission=admission,
            old_enrollments=enrollments,old_activation=approval,old_failure=failure)
    return SimpleNamespace(**locals())


def test_historical_read_guard_retains_original_journal_identity_without_finance(monkeypatch):
    s=fixture(monkeypatch)
    before=copy.deepcopy((s.enrollments,s.approval,s.failure,s.roots))
    owner=s.construct()
    actual=owner.capture()
    assert actual["schema"]==target.SCHEMA
    assert actual["original_journals_verified"]==2
    assert actual["original_financial_account_publications"]==0
    assert actual["historical_writer_adoption_authorized"] is False
    assert actual["same_epoch_replay_authorized"] is False
    assert actual["paper_start_authorized"] is False
    assert actual["live_money_trading_authorized"] is False
    assert copy.deepcopy((s.enrollments,s.approval,s.failure,s.roots))==before
    assert s.images["closes"]==4
    with pytest.raises(ValueError, match="CANNOT_ADOPT_WRITERS"):
        owner.require_exact_roster(qd={},perp={})
    with pytest.raises(ValueError, match="NO_FINANCIAL_PUBLICATION"):
        owner.publish_both_once()


@pytest.mark.parametrize("damage",[
    "job_missing","release_not_selected","same_release","old_writer_alive",
    "old_writer_equals_new","foreign_hl_process","original_digest_wrong",
    "activation_actions","old_approval_reuse","unreserved_failure",
])
def test_historical_owner_refuses_untrusted_or_stale_inputs(monkeypatch,damage):
    s=fixture(monkeypatch)
    if damage=="job_missing":s.inputs["job"]=None
    elif damage=="release_not_selected":s.admission.valid=False
    elif damage=="same_release":s.admission.release.artifact_digest=target.R26_DIGEST
    elif damage=="old_writer_alive":s.exits[0]=False
    elif damage=="old_writer_equals_new":
        s.job.identity=copy.deepcopy(s.historical)
        monkeypatch.setattr(target,"observe_self",lambda:copy.deepcopy(s.historical))
    elif damage=="foreign_hl_process":s.enrollments["HYPERLIQUID"]["writers"]["a"]["pid"]=500
    elif damage=="original_digest_wrong":s.enrollments["QUALITY_DIPS"]["release_digest"]="d"*64
    elif damage=="activation_actions":s.approval["actions"]=["AUTO_PAPER"]
    elif damage=="old_approval_reuse":s.approval["original_only"]=False
    elif damage=="unreserved_failure":s.failure["attempt_reserved"]=False
    with pytest.raises((ValueError,AttributeError)):
        s.construct()


@pytest.mark.parametrize("damage",[
    "job_exit","release_revoke","old_writer_return","journal_modified",
    "root_modified","account_files_appeared","original_binding_mutated",
])
def test_historical_read_guard_terminal_refusal_never_replays(monkeypatch,damage):
    s=fixture(monkeypatch)
    guard=s.construct()
    if damage=="job_exit":s.job.alive=False
    elif damage=="release_revoke":s.admission.valid=False
    elif damage=="old_writer_return":s.exits[0]=False
    elif damage=="journal_modified":s.images["revision"]=2
    elif damage=="root_modified":s.roots["lanes"]["QUALITY_DIPS"]["roots"]["coordination"]["native_id"]=[1,99,1]
    elif damage=="account_files_appeared":
        s.roots["existing_empty_root_namespaces"]=9
    elif damage=="original_binding_mutated":
        guard.activation["original_only"]=False
    with pytest.raises(ValueError):
        guard.capture()
    assert guard._unknown is True
    with pytest.raises(ValueError,match="TERMINAL_UNKNOWN"):
        guard.capture()
