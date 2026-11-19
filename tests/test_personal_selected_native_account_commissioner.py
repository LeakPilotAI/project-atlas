"""Genuine product stage D/E/F orchestration, disposable injected ports.

The sole production orchestrator requires original native classes, fresh
operator authority and one living original process. Tests substitute ports
ONLY through pytest monkeypatch; never touch original account directories.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from scripts.observation_runtime import (
    personal_selected_native_account_commissioner as target,
)

RELEASE = "a"*64
LANES = ("QUALITY_DIPS", "HYPERLIQUID")


def configured(monkeypatch):
    events = []
    class Release:
        artifact_digest = RELEASE
        def verify(self, *, release_digest):
            assert release_digest == RELEASE
            events.append("native_release_verify")
            return True
    class Admission:
        def __init__(self, release):
            self.release=release
        def verify(self, *, release_digest):
            self.release.verify(release_digest=release_digest)
            events.append("release_admission")
            return True
    class Owner:
        release_digest = RELEASE
        _phase = "PREINCEPTION"
        def __init__(self, release):
            self._release_admission = Admission(release)
            self.alive = True
        def verify_still_running(self):
            events.append("held_owner")
            if not self.alive:
                raise ValueError("ORIGINAL_WINDOWS_OWNER_GONE")
            return True
        def require_exact_roster(self, *, qd, perp):
            assert qd["lane"]=="QUALITY_DIPS"
            assert perp["lane"]=="HYPERLIQUID"
            events.append("same_twelve_roles")
            return True
    class Clock:
        def require_operational(self, runtime_id):
            assert runtime_id=="EXACT_LOCAL_PROCESS"
            events.append("live_NTP")
            return True
    class Ledger:
        def __init__(self, lane, enrollment):
            self.manifest={"release":RELEASE,"opening_cash":"1000",
                "currency":"USD" if lane=="QUALITY_DIPS" else "USDC",
                "opened_at":1794489500}
            self.images=SimpleNamespace(enrollment=target.digest(enrollment))
    class Reader:
        pass
    class Journal:
        def __init__(self, *, job, clock, runtime_id, ledgers, operator_scope):
            events.append("journal_scope_checked")
            assert type(job) is Owner and type(clock) is Clock
            assert runtime_id=="EXACT_LOCAL_PROCESS"
            assert operator_scope=={"human_exact_scope":"JOURNALS_ONLY"}
        def publish_both_original_journals_once(self):
            events.append("journal_publish")
            owner._phase="PREINCEPTION_COORDINATION_READY"
            return {"native_initial_journal_count":2,
                    "paper_start_authorized":False,
                    "live_trading_authorized":False}
    def publish_activation(**kw):
        events.append("activation_publish")
        assert kw["clock_profile"]==target.CLOCK_PROFILE
        assert kw["owned_job"] is owner and kw["prequalified_clock"] is clock
        assert kw["release_digest"]==RELEASE
        return {"schema":"ATLAS_PERSONAL_ACTIVATION_PUBLICATION_V1",
                "status":"NATIVE_VERIFIED",
                "binding":{"id":[1,2,3],"sha256":"b"*64},
                "paper_start_authorized":False,
                "live_trading_authorized":False}
    class Writer:
        def __init__(self,lane):
            self.lane=lane
            self.closed=False
        def close(self):
            self.closed=True
            events.append("closed_"+self.lane)
    class Pair:
        def publish_both_once(self):
            events.append("accounts_publish")
            owner._phase="INITIAL_READBACK_ONLY"
            return {"status":"TWO_NATIVE_SIMULATED_ACCOUNT_OPENINGS_ACKNOWLEDGED",
                    "paper_start_authorized":False,
                    "live_trading_authorized":False}
    def assemble(**kwargs):
        events.append("original_issuer_factory")
        assert kwargs["job"] is owner and kwargs["release"] is release
        assert kwargs["clock"] is clock and kwargs["runtime_id"]=="EXACT_LOCAL_PROCESS"
        assert type(kwargs["reader"]) is Reader
        return Pair(),{lane:Writer(lane) for lane in LANES}
    monkeypatch.setattr(target,"RetainedSelectedNativeOwnerPreflight",Owner)
    monkeypatch.setattr(target,"NativePersonalReleaseIdentity",Release)
    monkeypatch.setattr(target,"NativeFinancialReleaseAdmission",Admission)
    monkeypatch.setattr(target,"NativeVersionSafePaperOperatorClock",Clock)
    monkeypatch.setattr(target,"PersonalNativeCoordination",Ledger)
    monkeypatch.setattr(target,"NativePersonalActivationReader",Reader)
    monkeypatch.setattr(target,"NativeOriginalTwoJournalPreinceptionPermit",Journal)
    monkeypatch.setattr(target,"commission_native_activation",publish_activation)
    monkeypatch.setattr(target,"assemble_selected_two_account_inception",assemble)
    monkeypatch.setattr(target,"require_version_safe_release_digest",
        lambda *,clock,runtime_id,release_digest:
            type(clock) is Clock and runtime_id=="EXACT_LOCAL_PROCESS"
            and release_digest==RELEASE)
    from scripts.observation_runtime import personal_existing_native_resource_evidence
    monkeypatch.setattr(personal_existing_native_resource_evidence,
        "inspect_two_lane_native_roots",
        lambda: {"native_root_total":12,"all_twelve_distinct_and_empty":True})
    release=Release()
    clock=Clock()
    owner=Owner(release)
    enrollments={lane:{"lane":lane} for lane in LANES}
    ledgers={lane:Ledger(lane,enrollments[lane]) for lane in LANES}
    obj=target.NativeSelectedPersonalAccountCommissioner(
        owner=owner,release=release,clock=clock,ledgers=ledgers,
        enrollments=enrollments,runtime_id="EXACT_LOCAL_PROCESS")
    return SimpleNamespace(
        obj=obj,owner=owner,release=release,clock=clock,events=events,
        enrollments=enrollments,ledgers=ledgers,Reader=Reader,
    )


def first(scope=None):
    return {"operator_scope":scope or {"human_exact_scope":"JOURNALS_ONLY"}}


def second():
    return {
        "root":r"D:\AtlasCustody\PersonalPaper\existing-original",
        "record_path":r"D:\Work\Project Atlas\operator\reviewed.json",
        "policy_path":r"D:\Work\Project Atlas\docs\ATLAS_PERSONAL_PAPER_RELEASE_POLICY.json",
        "accounts_path":r"D:\Work\Project Atlas\operator\accounts.json",
        "qd_enrollment_path":r"D:\Work\Project Atlas\operator\qd.json",
        "perp_enrollment_path":r"D:\Work\Project Atlas\operator\hl.json",
    }


def third(x):
    return {"reader":x.Reader(),
            "operators":{lane:object() for lane in LANES},
            "inception_enrollments":{
                lane:{"native_enrollment":x.enrollments[lane]} for lane in LANES}}


def test_real_product_bridge_orders_three_exact_irreversible_phases(monkeypatch):
    x=configured(monkeypatch)
    assert x.obj.phase=="PREINCEPTION_READY"
    a=x.obj.initialize_two_journals_once(**first())
    assert a["native_initial_journal_count"]==2
    assert x.obj.phase=="TWO_JOURNALS_ACKNOWLEDGED"
    b=x.obj.publish_initialization_activation_once(**second())
    assert b["status"]=="NATIVE_VERIFIED"
    assert x.obj.phase=="INITIALIZE_ACTIVATION_ACKNOWLEDGED"
    c=x.obj.initialize_two_accounts_once(**third(x))
    assert c["status"]=="TWO_NATIVE_SIMULATED_ACCOUNT_OPENINGS_ACKNOWLEDGED"
    assert x.obj.phase=="TWO_ACCOUNTS_ACKNOWLEDGED"
    assert x.events.index("journal_publish") < x.events.index("activation_publish")
    assert x.events.index("activation_publish") < x.events.index("accounts_publish")
    assert x.events[-2:]==["closed_HYPERLIQUID","closed_QUALITY_DIPS"]
    with pytest.raises(ValueError,match="REPLAY_OR_UNKNOWN"):
        x.obj.initialize_two_accounts_once(**third(x))
    with pytest.raises(ValueError,match="REPLAY_OR_UNKNOWN"):
        x.obj.initialize_two_journals_once(**first())
    with pytest.raises(ValueError,match="REPLAY_OR_UNKNOWN"):
        x.obj.publish_initialization_activation_once(**second())


@pytest.mark.parametrize("phase",["activation","accounts"])
def test_out_of_order_financial_effects_refuse_before_any_publication(monkeypatch,phase):
    x=configured(monkeypatch)
    with pytest.raises(ValueError,match="REPLAY_OR_UNKNOWN"):
        if phase=="activation":
            x.obj.publish_initialization_activation_once(**second())
        else:
            x.obj.initialize_two_accounts_once(**third(x))
    assert "journal_publish" not in x.events
    assert "activation_publish" not in x.events
    assert "accounts_publish" not in x.events


@pytest.mark.parametrize("alter",["missing_scope","bad_scope","dead_job",
     "foreign_release","mutated_enrollment","changed_native_owner_phase"])
def test_journal_admission_is_not_generic_execute_approval(monkeypatch,alter):
    x=configured(monkeypatch)
    kw=first()
    if alter=="missing_scope":kw["operator_scope"]=None
    if alter=="bad_scope":kw["operator_scope"]={"human_exact_scope":"AUTO_PAPER"}
    if alter=="dead_job":x.owner.alive=False
    if alter=="foreign_release":x.owner._release_admission.release=object()
    if alter=="mutated_enrollment":x.obj.enrollments["QUALITY_DIPS"]["lane"]="OTHER"
    if alter=="changed_native_owner_phase":x.owner._phase="CURRENT_READBACK_ONLY"
    with pytest.raises((ValueError,AssertionError)):
        x.obj.initialize_two_journals_once(**kw)
    assert "journal_publish" not in x.events


def test_activation_requires_all_six_explicit_original_paths(monkeypatch):
    x=configured(monkeypatch)
    x.obj.initialize_two_journals_once(**first())
    kw=second()
    kw["accounts_path"]=""
    with pytest.raises(ValueError,match="EXPLICIT_ACTIVATION_INPUTS_REQUIRED"):
        x.obj.publish_initialization_activation_once(**kw)
    assert x.obj.phase=="TWO_JOURNALS_ACKNOWLEDGED"
    assert "activation_publish" not in x.events


def test_activation_failure_is_terminal_unknown_not_restarted(monkeypatch):
    x=configured(monkeypatch)
    x.obj.initialize_two_journals_once(**first())
    def broken(**kw):
        x.events.append("activation_partial")
        raise OSError("TEST_ORIGINAL_ACTIVATION_UNKNOWN")
    monkeypatch.setattr(target,"commission_native_activation",broken)
    with pytest.raises(OSError,match="UNKNOWN"):
        x.obj.publish_initialization_activation_once(**second())
    assert x.obj.phase=="ACTIVATION_UNKNOWN"
    with pytest.raises(ValueError,match="REPLAY_OR_UNKNOWN"):
        x.obj.publish_initialization_activation_once(**second())


def test_partial_journal_publication_does_not_replay(monkeypatch):
    x=configured(monkeypatch)
    def fail(*args,**kwargs):
        x.events.append("journal_partly_created")
        raise OSError("FIRST_COMMITTED_SECOND_UNKNOWN")
    monkeypatch.setattr(target.NativeOriginalTwoJournalPreinceptionPermit,
        "publish_both_original_journals_once",fail)
    with pytest.raises(OSError,match="SECOND_UNKNOWN"):
        x.obj.initialize_two_journals_once(**first())
    assert x.obj.phase=="JOURNALS_UNKNOWN"
    with pytest.raises(ValueError,match="REPLAY_OR_UNKNOWN"):
        x.obj.initialize_two_journals_once(**first())


@pytest.mark.parametrize("tamper",["reader","operators","enrollments","phase"])
def test_two_account_issuer_requires_bound_original_ports(monkeypatch,tamper):
    x=configured(monkeypatch)
    x.obj.initialize_two_journals_once(**first())
    x.obj.publish_initialization_activation_once(**second())
    kw=third(x)
    if tamper=="reader":kw["reader"]=object()
    if tamper=="operators":kw["operators"].pop("HYPERLIQUID")
    if tamper=="enrollments":
        kw["inception_enrollments"]["QUALITY_DIPS"]["native_enrollment"]={"lane":"ALIEN"}
    if tamper=="phase":x.owner._phase="PREINCEPTION"
    with pytest.raises(ValueError):
        x.obj.initialize_two_accounts_once(**kw)
    assert "accounts_publish" not in x.events


def test_real_unmocked_production_bridge_refuses_without_native_owner():
    with pytest.raises(ValueError,match="EXACT_SELECTED_ORIGINAL_OWNER_REQUIRED"):
        target.NativeSelectedPersonalAccountCommissioner(
            owner=object(),release=object(),clock=object(),
            ledgers={},enrollments={},runtime_id="fake")


def activate_to_two_accounts(x):
    x.obj.initialize_two_journals_once(**first())
    x.obj.publish_initialization_activation_once(**second())
    x.obj.initialize_two_accounts_once(**third(x))


def postinit(x, *, root=None):
    result = second()
    result["root"] = root or r"D:\AtlasCustody\PersonalPaper\postinit-simulated-scope"
    result["record_path"] = r"D:\Work\Project Atlas\operator\postinit-approved.json"
    return result


def stub_original_data_operator_record(monkeypatch,x,*,actions=None):
    from scripts.observation_runtime import personal_activation_commission
    action_list = (["READ_ONLY","CONNECT_APPROVED_DATA"]
                   if actions is None else actions)
    monkeypatch.setattr(
        personal_activation_commission,"read_bounded_activation_input",
        lambda path,role: {
            "actions":action_list,"origin":"LOCAL_OPERATOR",
            "release_digest":RELEASE,"accounts":x.obj._digest,
        })


def test_stage_g_uses_distinct_issuer_and_never_starts_paper(monkeypatch):
    x=configured(monkeypatch)
    activate_to_two_accounts(x)
    stub_original_data_operator_record(monkeypatch,x)
    result=x.obj.publish_postinception_data_activation_once(**postinit(x))
    assert result["status"]=="NATIVE_VERIFIED"
    assert x.obj.phase=="POSTINCEPTION_DATA_ACTIVATION_ACKNOWLEDGED"
    assert x.events.count("activation_publish")==2
    assert x.events.count("accounts_publish")==1
    assert x.events[-1]=="activation_publish"
    with pytest.raises(ValueError,match="REPLAY_OR_UNKNOWN"):
        x.obj.publish_postinception_data_activation_once(**postinit(x))


@pytest.mark.parametrize("invalid",[
    "initial_root_reused","initial_root_case_alias","c_drive",
    "wrong_record_actions","initialization_action_reused","auto_paper_action",
    "absent_hyperliquid_source_approval","wrong_account_digests","wrong_release",
])
def test_stage_g_never_reuses_preactivation_or_accepts_auto_paper(
        monkeypatch,invalid):
    x=configured(monkeypatch)
    activate_to_two_accounts(x)
    kw=postinit(x)
    actions=None
    if invalid=="initial_root_reused":
        kw["root"]=second()["root"]
    elif invalid=="initial_root_case_alias":
        kw["root"]=second()["root"].upper()
    elif invalid=="c_drive":
        kw["record_path"]=r"C:\Users\unaccepted\data_approval.json"
    elif invalid=="wrong_record_actions":
        actions=["CONNECT_APPROVED_DATA"]
    elif invalid=="initialization_action_reused":
        actions=["READ_ONLY","INITIALIZE_SIMULATED_ACCOUNTS"]
    elif invalid=="auto_paper_action":
        actions=["READ_ONLY","AUTO_PAPER"]
    elif invalid=="absent_hyperliquid_source_approval":
        actions=[]
    elif invalid=="wrong_account_digests":
        x.obj._digest["HYPERLIQUID"]="0"*64
    elif invalid=="wrong_release":
        x.owner.release_digest="b"*64
    stub_original_data_operator_record(monkeypatch,x,actions=actions)
    with pytest.raises((ValueError,AssertionError)):
        x.obj.publish_postinception_data_activation_once(**kw)
    assert x.events.count("activation_publish")==1


def test_stage_g_partial_publication_terminal_and_no_retry(monkeypatch):
    x=configured(monkeypatch)
    activate_to_two_accounts(x)
    stub_original_data_operator_record(monkeypatch,x)
    def unknown(**kwargs):
        x.events.append("data_activation_unknown")
        raise OSError("SECOND_ACTIVATION_MAY_HAVE_COMMITTED")
    monkeypatch.setattr(target,"commission_native_activation",unknown)
    with pytest.raises(OSError,match="MAY_HAVE_COMMITTED"):
        x.obj.publish_postinception_data_activation_once(**postinit(x))
    assert x.obj.phase=="DATA_ACTIVATION_UNKNOWN"
    with pytest.raises(ValueError,match="REPLAY_OR_UNKNOWN"):
        x.obj.publish_postinception_data_activation_once(**postinit(x))


def test_stage_g_requires_real_initial_fs1_fs3_not_just_journals(monkeypatch):
    x=configured(monkeypatch)
    x.obj.initialize_two_journals_once(**first())
    x.obj.publish_initialization_activation_once(**second())
    stub_original_data_operator_record(monkeypatch,x)
    with pytest.raises(ValueError,match="REPLAY_OR_UNKNOWN"):
        x.obj.publish_postinception_data_activation_once(**postinit(x))


def test_writer_handle_close_failure_leaves_account_outcome_unknown_and_closes_all(monkeypatch):
    x=configured(monkeypatch)
    x.obj.initialize_two_journals_once(**first())
    x.obj.publish_initialization_activation_once(**second())
    events=x.events
    class Publisher:
        def publish_both_once(self):
            x.owner._phase="INITIAL_READBACK_ONLY"
            events.append("two_accounts_acknowledged")
            return {"status":"TWO_NATIVE_SIMULATED_ACCOUNT_OPENINGS_ACKNOWLEDGED",
                    "paper_start_authorized":False,"live_trading_authorized":False}
    class Writer:
        def __init__(self,lane):self.lane=lane
        def close(self):
            events.append("close_"+self.lane)
            if self.lane=="HYPERLIQUID":
                raise OSError("HYPERLIQUID_NATIVE_WRITER_CLOSE_UNKNOWN")
    monkeypatch.setattr(target,"assemble_selected_two_account_inception",
                        lambda **kw:(Publisher(),{lane:Writer(lane) for lane in LANES}))
    with pytest.raises(OSError,match="CLOSE_UNKNOWN"):
        x.obj.initialize_two_accounts_once(**third(x))
    assert x.obj.phase=="TWO_ACCOUNTS_UNKNOWN"
    assert events[-2:]==["close_HYPERLIQUID","close_QUALITY_DIPS"]
    with pytest.raises(ValueError,match="REPLAY_OR_UNKNOWN"):
        x.obj.initialize_two_accounts_once(**third(x))
