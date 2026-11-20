"""One-time successor ROOT-ONLY provisioning; no accounts or PAPER authority."""
import builtins
import copy
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.services.paper_financial_replay import digest
from scripts.observation_runtime import personal_successor_root_provision_once as p
from scripts.observation_runtime import personal_successor_native_root_scope as scope
from scripts.observation_runtime import personal_successor_account_terms_review as terms

REV="d"*40
NONCE="0123456789abcdef01234567"
ARTIFACT="e"*64


def system(monkeypatch,tmp_path):
    sources={}
    for lane in scope.LANES:
        base=tmp_path/"Paper"/lane
        custody=tmp_path/"Custody"/lane
        base.mkdir(parents=True)
        custody.mkdir(parents=True)
        sources[lane]=(base,custody)
    monkeypatch.setattr(scope,"PARENTS",sources)
    monkeypatch.setattr(p,"PARENTS",sources)
    audit=tmp_path/"diagnostics"
    audit.mkdir()
    monkeypatch.setattr(p,"LOG",audit)
    plan=scope.successor_root_plan(successor_release=REV,epoch_nonce=NONCE)

    class Historian:
        def __init__(self):
            self.release=SimpleNamespace(
                root=Path("D:/AtlasRuntime/releases")/REV,
                artifact_digest=ARTIFACT)
            self.valid=True
        def capture(self):
            if not self.valid:raise ValueError("OLD_R26_JOURNAL_DRIFT")
            return {"original_journals_verified":2,
                    "original_financial_account_publications":0,
                    "paper_start_authorized":False}
    monkeypatch.setattr(p,"NativeR26HistoricalPostjournalGuard",Historian)
    monkeypatch.setattr(p,"__file__",str(Path("D:/AtlasRuntime/releases")/REV/
        "scripts/observation_runtime/personal_successor_root_provision_once.py"))
    historian=Historian()
    old_e={};old_m={};old_t={};review={}
    for lane in scope.LANES:
        economic={"opening_cash":"1000",
                  "currency":"USD" if lane=="QUALITY_DIPS" else "USDC"}
        old_e[lane]=digest("ORIGINAL_ACCOUNT_"+lane)
        old_m[lane]=digest("ORIGINAL_MANIFEST_"+lane)
        old_t[lane]=digest(economic)
        review[lane]={
            "old_original_enrollment_digest":old_e[lane],
            "old_original_manifest_digest":old_m[lane],
            "economic_terms_digest":old_t[lane],
            "exact_economic_terms":economic,
            "new_epoch":plan["lanes"][lane]["epoch"],
            "new_account_id":terms.ORIGINAL_ACCOUNTS[lane]+"-recovery-"+NONCE,
            "prospective_paths":plan["lanes"][lane]["roots"],
            "opening_timestamp_pending_independent_native_UTC":True,
            "new_native_resource_ids_pending":True,
            "new_windows_process_writer_roster_pending":True,
            "new_local_operator_financial_review_required":True,
            "account_initialized":False}
    monkeypatch.setattr(terms,"ORIGINAL_ENROLLMENT_DIGESTS",old_e)
    monkeypatch.setattr(terms,"ORIGINAL_MANIFEST_DIGESTS",old_m)
    monkeypatch.setattr(terms,"ORIGINAL_ECONOMIC_DIGESTS",old_t)
    packet={
      "schema":terms.SCHEMA,
      "status":"EXACT_NEW_EPOCH_TERMS_FOR_OPERATOR_REVIEW_ONLY",
      "successor_release":REV,"epoch_nonce":NONCE,
      "successor_artifact_digest":ARTIFACT,
      "accounts":review,"old_approval_transferred":False,
      "new_operator_approval_issued":False,
      "new_journal_or_account_created":False,
      "paper_start_authorized":False,
      "live_money_trading_authorized":False}
    inputs={"historian":historian}
    def construct():
        return p.NativeSuccessorRootProvisioningOnce(
            plan=plan,historical_guard=inputs["historian"],reviewed_terms=packet)
    return SimpleNamespace(**locals())


def test_scope_review_has_no_financial_issuer_or_start_grants(monkeypatch,tmp_path):
    s=system(monkeypatch,tmp_path)
    before=copy.deepcopy((s.plan,s.packet))
    review=p.exact_scope(plan=s.plan,successor_release_digest=ARTIFACT,
                         terms_review_digest=digest(s.packet))
    assert (s.plan,s.packet)==before
    assert review["scope"]==p.SCOPE
    assert len(review["root_directories"])==2
    assert review["new_directories_max"]==14
    for field in ("financial_journal_creation_authorized",
                  "financial_activation_authorized",
                  "account_initialization_authorized",
                  "paper_start_authorized","live_money_trading_authorized"):
        assert review[field] is False
    admit=s.construct().preflight()
    assert admit["status"]=="NATIVE_PROVISIONING_PREFLIGHT_ONLY"
    assert admit["new_root_namespaces_verified_absent"]==12
    assert admit["new_native_provisioning_attempt_created"] is False
    assert list(s.audit.iterdir())==[]
    assert all(not (parent/s.plan["lanes"][lane]["epoch"]).exists()
               for lane,parents in s.sources.items() for parent in parents)


@pytest.mark.parametrize("change",[
    "fake_historian","historical_loss","wrong_release","approved_paper",
    "old_operator_approval_reused","wrong_fee","wrong_account_id",
    "wrong_epoch","wrong_paths","fake_digest","old_cash_changed",
    "review_account_initialized","bad_scope",
])
def test_review_and_native_historical_custody_cannot_be_bypassed(monkeypatch,tmp_path,change):
    s=system(monkeypatch,tmp_path)
    entry=s.packet["accounts"]["QUALITY_DIPS"]
    if change=="fake_historian":s.inputs["historian"]=None
    elif change=="historical_loss":s.historian.valid=False
    elif change=="wrong_release":s.historian.release.root=Path("D:/AtlasRuntime/releases")/("f"*40)
    elif change=="approved_paper":s.packet["paper_start_authorized"]=True
    elif change=="old_operator_approval_reused":s.packet["old_approval_transferred"]=True
    elif change=="wrong_fee":entry["exact_economic_terms"]["fees_bps"]="7"
    elif change=="wrong_account_id":entry["new_account_id"]="atlas-personal-quality-dips"
    elif change=="wrong_epoch":entry["new_epoch"]="old-original-epoch"
    elif change=="wrong_paths":entry["prospective_paths"]["coordination"]=r"D:\AtlasPaper\QualityDips\ORIGINAL"
    elif change=="fake_digest":entry["economic_terms_digest"]="f"*64
    elif change=="old_cash_changed":entry["exact_economic_terms"]["opening_cash"]="800"
    elif change=="review_account_initialized":entry["account_initialized"]=True
    elif change=="bad_scope":s.plan["successor_release"]="x"*40
    with pytest.raises((ValueError,AttributeError)):
        s.construct()
    assert list(s.audit.iterdir())==[]


def test_visible_consent_refusal_prevents_any_native_dir_creation(monkeypatch,tmp_path):
    s=system(monkeypatch,tmp_path)
    monkeypatch.setattr(p,"_visible_local_operator",lambda:"S-1-test")
    monkeypatch.setattr(builtins,"input",lambda message:"DECLINE")
    with pytest.raises(ValueError,match="DECLINED"):
        s.construct().execute_after_visible_local_approval()
    assert list(s.audit.iterdir())==[]


def test_one_time_native_empty_dir_creation_and_no_retry(monkeypatch,tmp_path):
    if __import__("sys").platform!="win32":
        pytest.skip("Real Windows native financial-root handle verification")
    s=system(monkeypatch,tmp_path)
    monkeypatch.setattr(p,"_visible_local_operator",lambda:"S-1-test")
    monkeypatch.setattr(builtins,"input",lambda message:p.SCOPE)
    owner=s.construct()
    result=owner.execute_after_visible_local_approval()
    assert result["status"]=="TWELVE_NEW_EMPTY_ROOTS_NATIVE_ID_VERIFIED_NOT_FINANCIAL_AUTHORITY"
    assert result["new_financial_directories_created"]==14
    assert result["native_12_roots"]["native_root_ids_verified"]==12
    assert result["new_accounts_opened"]==0
    assert result["new_journals_created"]==0
    assert result["paper_start_authorized"] is False
    assert result["live_money_trading_authorized"] is False
    assert len(list(s.audit.iterdir()))==2
    assert not any(any(Path(root).iterdir()) for lane in scope.LANES
                   for root in s.plan["lanes"][lane]["roots"].values())
    with pytest.raises(ValueError,match="ATTEMPT_OR_SUCCESS_ALREADY_RESERVED|NEW_ROOTS_NOT_ABSENT|ROOT_ABSENT_AND_PARENT_INTEGRITY_REQUIRED"):
        owner.execute_after_visible_local_approval()


def test_partial_attempt_receipt_blocks_retry_without_cleaning(monkeypatch,tmp_path):
    s=system(monkeypatch,tmp_path)
    attempt,success=p._attempt_paths(s.plan)
    attempt.write_text('{"status":"UNKNOWN_PARTIAL"}',encoding="utf8")
    with pytest.raises(ValueError,match="ATTEMPT_OR_SUCCESS_ALREADY_RESERVED"):
        s.construct().preflight()
    assert attempt.is_file()
    assert not success.exists()
