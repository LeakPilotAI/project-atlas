"""R14 native code-only selector publisher: consent-locked and disposable tests.

No public NTP, real installed-file rescan, native D: selector mutation, market
account, service startup or trading. Positive publisher test intercepts store.
"""
import copy
import hashlib
import json
from contextlib import contextmanager
from pathlib import Path

import pytest

from scripts import atlas_r14_selection_publisher as pub
from scripts import atlas_r14_selection_proposal as proposal
from scripts import release_selection as selection

ROOT = Path(__file__).resolve().parents[1]
SID = "S-1-5-21-111-222-333-1001"  # synthetic only, never user's SID.


def decision():
    return {
        "schema":"ATLAS_R14_NATIVE_CODE_SELECTION_APPROVAL_V1",
        "decision":pub.DECISION,
        "scope":pub.SCOPE,
        "operator_sid":SID,
        "one_shot":True,
        "review_sha256":pub.REVIEW_SHA256,
        "proposal_source_sha256":pub.PROPOSAL_SOURCE_SHA256,
        "selected_r12_head":proposal.R12_HEAD,
        "selected_r12_envelope_sha256":proposal.R12_ENVELOPE_SHA256,
        "native_selection_root":str(proposal.SEL),
        "native_selection_root_identity":list(proposal.NATIVE_ID),
        "operation":pub.OPERATION,
        "proposed_head":pub.EXPECTED_HEAD,
        "r14_release":selection.R14_CODE_RELEASE,
        "r14_receipt_sha256":selection.R14_RECEIPT_SHA256,
        "r14_artifact_digest":selection.R14_ARTIFACT_DIGEST,
        "selection_source_sha256":pub.SELECTOR_SHA256,
        "selection_store_source_sha256":pub.NATIVE_STORE_SHA256,
        "clock_profile":pub.CLOCK_PROFILE,
        "selection_allowed":True,
        "financial_authority":False,
        "paper_accounts":False,
        "providers":False,
        "paper_start":False,
        "simulated_orders":False,
        "live_orders":False,
        "automatic_startup":False,
    }


def test_publisher_preview_real_readonly_source_and_no_consent():
    report=pub.inspect()
    assert report["status"]=="READY_FOR_SEPARATE_SELECTION_OPERATOR_REVIEW_NOT_APPROVED"
    assert report["operation"]==pub.OPERATION
    assert report["proposed_head"]==pub.EXPECTED_HEAD
    assert report["previous_head"]==proposal.R12_HEAD
    assert report["proposed_revision"]==13
    assert report["operator_approval_pinned"] is False
    assert report["r14_selected"] is False
    assert report["selection_authorized"] is False
    for field in ("financial_authority","paper_accounts","providers",
                  "paper_start","orders","live_orders","automatic_startup"):
        assert report[field] is False
    assert not (proposal.SEL/"r0013.json").exists()
    assert not (proposal.SEL/"r0013.pending").exists()


def test_explicit_selection_is_disabled_before_any_clock_or_store(monkeypatch):
    from scripts import release_selection_store
    monkeypatch.setattr(release_selection_store,"NativeSelectionStore",
                        lambda **_: pytest.fail("MUST_NOT_OPEN_OPERATING_STORE"))
    with pytest.raises(ValueError,match="R14_PUBLISHER_FRESH_ONE_SHOT_OPERATOR_APPROVAL_NOT_PINNED"):
        pub.main(["--execute-one-shot-code-selection","--confirm-scope",pub.SCOPE])
    with pytest.raises(ValueError,match="R14_PUBLISHER_EXACT_CONFIRMATION_REQUIRED"):
        pub.main(["--execute-one-shot-code-selection"])
    with pytest.raises(ValueError,match="R14_PUBLISHER_INSPECT_MIXED_SCOPE_REFUSED"):
        pub.main(["--inspect","--confirm-scope",pub.SCOPE])
    assert pub.APPROVAL_PIN is None
    assert not pub.APPROVAL.exists()


def test_exact_synthetic_operator_scope_can_be_validated_not_authorized():
    assert pub.validate_operator_decision(decision(),sid=SID)==decision()
    assert pub.APPROVAL_PIN is None


@pytest.mark.parametrize("field,value",[
    ("schema","FOREIGN"),("decision","APPROVE_ALL"),
    ("scope","PAPER_TRADING"),("operator_sid","S-1-5-18"),
    ("one_shot",1),("review_sha256","0"*64),
    ("proposal_source_sha256","0"*64),("selected_r12_head","0"*64),
    ("selected_r12_envelope_sha256","0"*64),
    ("native_selection_root","D:/foreign"),("native_selection_root_identity",[1,2,3]),
    ("operation","0"*32),("proposed_head","0"*64),
    ("r14_release","a"*40),("r14_receipt_sha256","0"*64),
    ("r14_artifact_digest","0"*64),
    ("selection_source_sha256","0"*64),("selection_store_source_sha256","0"*64),
    ("clock_profile","WINDOWS_TIME_CODE_SELECTION_V1"),
    ("selection_allowed",False),("financial_authority",True),
    ("paper_accounts",True),("providers",True),("paper_start",True),
    ("simulated_orders",True),("live_orders",True),("automatic_startup",True),
])
def test_changed_operator_field_or_widened_scope_refused(field,value):
    changed=decision()
    changed[field]=value
    with pytest.raises(ValueError,match="R14_PUBLISHER_EXACT_ONE_SHOT_NONFINANCIAL_OPERATOR_SCOPE_REQUIRED"):
        pub.validate_operator_decision(changed,sid=SID)


def test_extra_field_and_wrong_sid_refused():
    a=decision()
    a["approve_automatically"]=True
    with pytest.raises(ValueError,match="EXACT_ONE_SHOT"):
        pub.validate_operator_decision(a,sid=SID)
    with pytest.raises(ValueError,match="EXACT_ONE_SHOT"):
        pub.validate_operator_decision(decision(),sid="S-1-5-21-111-222-333-9999")


def test_consent_requires_exact_pinned_new_private_file(monkeypatch,tmp_path):
    from scripts.volume_inspector import windows_output
    raw=(json.dumps(decision(),sort_keys=True)+"\n").encode()
    path=tmp_path/"approval.json"
    path.write_bytes(raw)
    monkeypatch.setattr(pub,"APPROVAL",path)
    monkeypatch.setattr(pub,"APPROVAL_PIN",hashlib.sha256(raw).hexdigest())
    monkeypatch.setattr(windows_output,"current_sid",lambda:SID)
    assert pub.require_approved_operator()==decision()
    path.write_bytes(raw+b" ")
    with pytest.raises(ValueError,match="R14_SELECTION_PINNED_BYTES_CHANGED"):
        pub.require_approved_operator()


def test_snapshot_proposal_hash_and_rows_exact_and_not_permission():
    review=pub.pinned_review()
    assert review["row"]["operation"]==pub.OPERATION
    assert review["proposed_head"]==pub.EXPECTED_HEAD
    assert selection.digest(review["row"])==pub.EXPECTED_HEAD
    assert review["selection_authorized"] is False
    assert review["operator_approval_present"] is False


def test_source_review_digest_tamper_refuses(monkeypatch):
    monkeypatch.setattr(pub,"REVIEW_SHA256","0"*64)
    with pytest.raises(ValueError,match="R14_SELECTION_PINNED_BYTES_CHANGED"):
        pub.pinned_review()


def test_clock_requires_genuine_two_peer_type_and_uncertainty():
    with pytest.raises(ValueError,match="REAL_INDEPENDENT_TWO_PEER_CLOCK_REQUIRED"):
        pub.validate_clock(object(),"test")


def _simulate_native_publish(monkeypatch, *, fault=None):
    """Replace every real risky port, but exercise actual publisher logic."""
    from scripts import release_selection_store
    from scripts.observation_runtime import atlas_independent_ntp_clock as ntp
    from scripts import atlas_r13_low_impact_installer as low
    from contextlib import contextmanager
    events=[]
    real_rows=[]
    for n in range(1,13):
        path=proposal.SEL/f"r{n:04d}.json"
        real_rows.append(selection.strict(path.read_bytes())["record"])

    class FakeClock:
        def __init__(self):
            self.evidence={
                "source":ntp.SOURCE,
                "domain":"TWO_PUBLIC_UNAUTHENTICATED_NTP_PEERS",
                "financial_authority":False,
                "os_windows_time_service_required":False,
                "bound_ms":130,
            }
            self.calls=0
        def require_operational(self, identity):
            assert identity=="TEST_R14_ONLY"
            self.calls+=1
            events.append("clock")
            if fault=="clock_refused" and self.calls>=40:
                raise ValueError("SYNTHETIC_NTP_REVOKED")

    class FakeStore:
        domain="WINDOWS_LOCAL"
        def __init__(self,*,root,native_root):
            assert root==str(proposal.SEL)
            assert native_root==proposal.NATIVE_ID
            self.rows=copy.deepcopy(real_rows)
            events.append("store_opened")
        @contextmanager
        def locked(self):
            events.append("native_lock_enter")
            try:
                yield self
            finally:
                events.append("native_lock_exit")
        def records(self):
            events.append("native_records_read")
            if fault=="changed_chain":
                changed=copy.deepcopy(self.rows)
                changed[-1]["previous"]="0"*64
                return changed
            return copy.deepcopy(self.rows)
        def publish(self,row):
            events.append("NATIVE_PUBLISH_INTERCEPTED")
            assert row==pub.pinned_review()["row"]
            if fault=="publish_refused":
                raise OSError("SYNTHETIC_NATIVE_PUBLISH_REFUSED")
            self.rows.append(copy.deepcopy(row))
        def close(self):
            events.append("store_closed")

    class FakeVerifier:
        @contextmanager
        def open(self, target):
            assert target==pub.pinned_review()["row"]["selected"]
            events.append("native_readback_intercepted")
            yield {
                "source_commit":selection.R14_CODE_RELEASE,
                "artifact_digest":selection.R14_ARTIFACT_DIGEST,
                "selected":False,"financial_effects":False,
                "provider_connections":False,"operational_acceptance":False,
            }
            events.append("native_readback_closed")

    class FakeEnvelope:
        def __init__(self,**kwargs):
            assert kwargs["check_every"]==32 and kwargs["pace_every"]==128
            events.append("idle_envelope_constructed")
        def __enter__(self):
            events.append("idle_enter")
            return self
        def tick(self):
            events.append("admission_tick")
            return True
        def __exit__(self,*args):
            events.append("idle_restore")

    monkeypatch.setattr(ntp,"IndependentNtpClock",FakeClock)
    monkeypatch.setattr(selection,"NativeInstalledReleaseVerifier",FakeVerifier)
    monkeypatch.setattr(release_selection_store,"NativeSelectionStore",FakeStore)
    monkeypatch.setattr(low,"LowImpactEnvelope",FakeEnvelope)
    monkeypatch.setattr(pub,"require_approved_operator",lambda: events.append("synthetic_consent") or decision())
    now=[100.]
    monkeypatch.setattr(pub.time,"perf_counter",lambda:now[0])
    monkeypatch.setattr(pub.time,"sleep",lambda seconds:now.__setitem__(0,now[0]+seconds))
    clock=FakeClock()
    proof=pub.qualify_clock(clock,"TEST_R14_ONLY")
    assert proof["samples"]==37
    assert proof["elapsed_seconds"]==180
    return clock,proof,events,now


def test_synthetic_actual_publisher_flow_only_intercepts_native_write(monkeypatch):
    clock,proof,events,_=_simulate_native_publish(monkeypatch)
    result=pub.publish_with_native_lock(
        clock=clock,identity="TEST_R14_ONLY",proof=proof)
    assert result["status"]=="R14_NONFINANCIAL_CODE_SELECTED"
    assert result["revision"]==13
    assert result["selected_release"]==selection.R14_CODE_RELEASE
    assert result["new_head"]==pub.EXPECTED_HEAD
    assert result["financial_authority"] is False
    assert result["paper_accounts"] is False
    assert result["providers"] is False
    assert result["paper_start"] is False
    assert result["orders"] is False
    assert events.count("NATIVE_PUBLISH_INTERCEPTED")==1
    assert events.index("native_lock_enter") < events.index("NATIVE_PUBLISH_INTERCEPTED")
    assert events.index("native_readback_intercepted") < events.index("NATIVE_PUBLISH_INTERCEPTED")
    assert events.index("NATIVE_PUBLISH_INTERCEPTED") < events.index("native_lock_exit")
    assert events[-1]=="store_closed"
    assert not (proposal.SEL/"r0013.json").exists()


@pytest.mark.parametrize("fault,pattern", [
    ("changed_chain","R14_SELECTION_NATIVE_PREDECESSOR_CHAIN_REFUSED"),
    ("clock_refused","SYNTHETIC_NTP_REVOKED"),
    ("publish_refused","SYNTHETIC_NATIVE_PUBLISH_REFUSED"),
])
def test_synthetic_native_publication_fault_preserves_existing_selected_release(
        monkeypatch,fault,pattern):
    clock,proof,events,_=_simulate_native_publish(monkeypatch,fault=fault)
    before=(proposal.SEL/"r0012.json").read_bytes()
    with pytest.raises((ValueError,OSError),match=pattern):
        pub.publish_with_native_lock(
            clock=clock,identity="TEST_R14_ONLY",proof=proof)
    assert (proposal.SEL/"r0012.json").read_bytes()==before
    assert not (proposal.SEL/"r0013.json").exists()
    assert "store_closed" in events
    if fault!="publish_refused":
        assert "NATIVE_PUBLISH_INTERCEPTED" not in events


def test_forged_clock_proof_does_not_open_native_selector(monkeypatch):
    from scripts import release_selection_store
    monkeypatch.setattr(pub,"require_approved_operator",lambda:decision())
    monkeypatch.setattr(release_selection_store,"NativeSelectionStore",
                        lambda **_:pytest.fail("NATIVE_STORE_MUST_STAY_LOCKED"))
    with pytest.raises(ValueError,match="FRESH_IN_PROCESS_NTP_QUALIFICATION_REQUIRED"):
        pub.publish_with_native_lock(clock=object(),identity="UNQUALIFIED",
                                     proof={"elapsed_seconds":180,"samples":37})


def test_stale_clock_qualification_refuses(monkeypatch):
    clock,proof,events,now=_simulate_native_publish(monkeypatch)
    now[0]+=pub.QUALIFICATION_FRESH_SECONDS+1
    with pytest.raises(ValueError,match="FRESH_IN_PROCESS_NTP_QUALIFICATION_REQUIRED"):
        pub.publish_with_native_lock(clock=clock,identity="TEST_R14_ONLY",proof=proof)
    assert "store_opened" not in events
    assert "NATIVE_PUBLISH_INTERCEPTED" not in events
