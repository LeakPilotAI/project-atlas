"""R16 original owned Job identity binding: pure negative roster tests.

The only real native process test lives in test_atlas_r16_parked_writer_owner.
These tests never spawn an actual process or assert financial authority.
"""
import copy

import pytest

from app.services.quality_dips_autonomous_enrollment import (
    WRITERS as QD_WRITERS,
)
from app.services.perp_operational_contract import (
    WRITERS as HL_WRITERS,
)
from scripts.observation_runtime.personal_native_job import ContainedChild
from scripts.observation_runtime import personal_r16_owned_job_activation as gate
from scripts.observation_runtime.atlas_r16_selected_code_readback import (
    ARTIFACT_DIGEST, RELEASE, R16_HEAD,
)
from scripts.observation_runtime.atlas_independent_ntp_clock import SOURCE

ROLES=("source","projection","report","control","coordination","custody")
IMAGE=str(RELEASE/"python/python.exe")


def rosters():
    original={"pid":47213,"creation_filetime":181151004004000000,
              "image":IMAGE}
    process={"schema":"QD_OP_PROCESS_ID_V1",**original}
    result={}
    for lane,writers,schema,enroll_schema in (
        ("QUALITY_DIPS",QD_WRITERS,"QD_AUTO_NATIVE_ROOT_V4",
         "QD_AUTO_NATIVE_ENROLLMENT_V4"),
        ("HYPERLIQUID",HL_WRITERS,"PERP_AUTO_NATIVE_ROOT_V1",
         "PERP_AUTO_NATIVE_ENROLLMENT_V1"),
    ):
        result[lane]={
            "schema":enroll_schema,
            "profile":"AUTONOMOUS_PAPER_ONLY_V1",
            "account_id":"UNACCEPTED_STRUCTURAL_"+lane,
            "epoch":"disposable-r16-"+lane.lower(),
            "policy_digest":"0"*64,
            "inception_digest":"1"*64,
            "release_digest":ARTIFACT_DIGEST,
            "resources":{
                role:{"schema":schema,"path":rf"D:\OfflineTest\{lane}\{role}",
                      "native_id":[1,1+i+(0 if lane=="QUALITY_DIPS" else 6),0]}
                for i,role in enumerate(ROLES)},
            "writers":{role:copy.deepcopy(process) for role in writers},
            "clock_source":SOURCE,
            "acceptance_id":"UNACCEPTED_R16_TEST_"+lane,
        }
    return original,result["QUALITY_DIPS"],result["HYPERLIQUID"]


def test_twelve_structural_roles_match_original_r16_process_without_lease():
    original,qd,hl=rosters()
    before=copy.deepcopy((qd,hl))
    roles,validated_qd,validated_hl=gate.validate_r16_two_lane_rosters(
        qd,hl,observed=original)
    assert len(roles)==12
    assert set(roles)==(
        {("QUALITY_DIPS",r) for r in QD_WRITERS} |
        {("HYPERLIQUID",r) for r in HL_WRITERS})
    assert len(set(roles.values()))==1
    assert next(iter(roles.values()))==(
        original["pid"],original["creation_filetime"],IMAGE.lower())
    assert validated_qd["acceptance_id"].startswith("UNACCEPTED_")
    assert validated_hl["acceptance_id"].startswith("UNACCEPTED_")
    assert (qd,hl)==before


@pytest.mark.parametrize("change",[
    "missing_quality_role","extra_hyperliquid_role",
    "foreign_pid","foreign_incarnation","foreign_process_image",
    "bad_release_qd","bad_release_perp","same_account","same_epoch",
    "same_acceptance","clock_mismatch","missing_enrollment_resource",
    "resource_alias","bad_process_type","different_original_observed_image",
    "missing_original_process_identity","fake_native_writer_identity",
])
def test_unverified_financial_writer_identity_or_scope_refuses(change):
    original,qd,hl=rosters()
    if change=="missing_quality_role":
        qd["writers"].pop("decision")
    elif change=="extra_hyperliquid_role":
        hl["writers"]["extra"]=copy.deepcopy(hl["writers"]["decision"])
    elif change=="foreign_pid":
        hl["writers"]["mark"]["pid"]+=1
    elif change=="foreign_incarnation":
        qd["writers"]["report"]["creation_filetime"]+=1
    elif change=="foreign_process_image":
        qd["writers"]["source"]["image"]=r"D:\FOREIGN\python.exe"
    elif change=="bad_release_qd":
        qd["release_digest"]="a"*64
    elif change=="bad_release_perp":
        hl["release_digest"]="a"*64
    elif change=="same_account":
        hl["account_id"]=qd["account_id"]
    elif change=="same_epoch":
        hl["epoch"]=qd["epoch"]
    elif change=="same_acceptance":
        hl["acceptance_id"]=qd["acceptance_id"]
    elif change=="clock_mismatch":
        hl["clock_source"]="UNACCEPTED_FOREIGN_CLOCK"
    elif change=="missing_enrollment_resource":
        qd["resources"].pop("coordination")
    elif change=="resource_alias":
        hl["resources"]["custody"]["path"]=hl["resources"]["report"]["path"]
    elif change=="bad_process_type":
        hl["writers"]["funding"]["pid"]=True
    elif change=="different_original_observed_image":
        original["image"]=r"D:\FOREIGN\python.exe"
    elif change=="missing_original_process_identity":
        original.pop("creation_filetime")
    elif change=="fake_native_writer_identity":
        qd["writers"]["decision"]["schema"]="SERIALIZED_PID_ADOPTION"
    with pytest.raises((ValueError,TypeError,KeyError)):
        gate.validate_r16_two_lane_rosters(qd,hl,observed=original)


@pytest.mark.parametrize("foreign",[
    None,False,123,"pid",{},object(),
])
def test_retained_owner_rejects_non_original_contained_child(foreign):
    with pytest.raises(ValueError,match="R16_RETAINED_JOB_ORIGINAL_CONTAINED_CHILD_REQUIRED"):
        gate.RetainedSelectedR16OwnerJob(
            child=foreign,qd={},perp={})


def test_bare_job_or_pid_numbers_cannot_be_adopted():
    unowned=ContainedChild(api=None,job=99,process=100)
    with pytest.raises(ValueError,match="R16_RETAINED_JOB_ORIGINAL_CONTAINED_CHILD_REQUIRED"):
        gate.RetainedSelectedR16OwnerJob(
            child=unowned,qd={},perp={})
    unowned.closed=True
    with pytest.raises(ValueError,match="R16_RETAINED_JOB_ORIGINAL_CONTAINED_CHILD_REQUIRED"):
        gate.RetainedSelectedR16OwnerJob(
            child=unowned,qd={},perp={})


def test_no_financial_issuer_or_order_dispatch_port_in_retained_owner_class():
    import inspect
    source=inspect.getsource(gate.RetainedSelectedR16OwnerJob)
    assert "with NativeInstalledReleaseVerifier" not in source
    assert "publish_personal_activation(" not in source
    assert "place_order(" not in source
    assert "commit_inception(" not in source
    assert "financial_writer_lease_issued" in source
    assert '"financial_writer_lease_issued": False' in source
    assert '"paper_start_authorized": False' in source
    assert '"live_trading_authorized": False' in source
    assert R16_HEAD in gate.SCHEMA or gate.SCHEMA.startswith("ATLAS_R16_")


def test_r16_shared_nonfinancial_owner_guard_uses_exact_type_and_finally(monkeypatch):
    from scripts.observation_runtime import personal_activation_commission as activation
    from scripts.observation_runtime import personal_r16_owned_job_activation as real
    checks=[]
    class DisposableOriginalHandle:
        def require_exact_roster(self, *, qd, perp):
            checks.append((qd,perp))
            return True
    monkeypatch.setattr(real, "RetainedSelectedR16OwnerJob", DisposableOriginalHandle)
    fake=DisposableOriginalHandle()
    qd={"lane":"STRUCTURAL_QD"}
    perp={"lane":"STRUCTURAL_HL"}
    with activation.retain_r16_nonfinancial_original_job(
            qd=qd,perp=perp,owned_job=fake) as retained:
        assert retained is fake
    assert checks == [(qd,perp),(qd,perp)]
    with pytest.raises(RuntimeError,match="DISPOSABLE_BODY_ERROR"):
        with activation.retain_r16_nonfinancial_original_job(
                qd=qd,perp=perp,owned_job=fake):
            raise RuntimeError("DISPOSABLE_BODY_ERROR")
    assert checks == [(qd,perp)]*4


def test_r16_structural_owner_cannot_enter_financial_activation_publisher(monkeypatch):
    from scripts.observation_runtime import personal_activation_commission as activation
    from scripts.observation_runtime import personal_r16_owned_job_activation as real
    checks=[]
    class DisposableOriginalHandle:
        def require_exact_roster(self, *, qd, perp):
            checks.append((qd,perp))
            return True
    monkeypatch.setattr(real, "RetainedSelectedR16OwnerJob", DisposableOriginalHandle)
    fake=DisposableOriginalHandle()
    with pytest.raises(ValueError,match="ACTIVATION_R16_INDEPENDENT_FINANCIAL_LEASE_NOT_ACCEPTED"):
        with activation.retain_activation_writer_guard(
                qd={"readonly":"qd"},perp={"readonly":"hl"},
                release_digest=ARTIFACT_DIGEST,owned_job=fake):
            pytest.fail("R16_STRUCTURAL_JOB_CANNOT_YIELD_FINANCIAL_PUBLICATION")
    assert len(checks)==2


@pytest.mark.parametrize("foreign",[None,object(),{},123,False])
def test_r16_shared_structural_guard_rejects_unowned_objects(foreign):
    from scripts.observation_runtime.personal_activation_commission import (
        retain_r16_nonfinancial_original_job,
    )
    with pytest.raises(ValueError,match="R16_NONFINANCIAL_EXACT_RETAINED_ORIGINAL_JOB_REQUIRED"):
        with retain_r16_nonfinancial_original_job(qd={},perp={},owned_job=foreign):
            pytest.fail("FOREIGN_OBJECT_CANNOT_PASS_R16_NATIVE_OWNER_GUARD")


def test_r16_financial_guard_does_not_allow_untrusted_callers_to_claim_job(monkeypatch):
    from scripts.observation_runtime import personal_activation_commission as activation
    from scripts.observation_runtime import personal_native_writer_lifetime as legacy
    def forbidden(*args, **kwargs):
        pytest.fail("R16_FINANCE_MUST_NOT_REOPEN_PID_FROM_JSON")
    monkeypatch.setattr(legacy,"retain_live_enrollment_writers",forbidden)
    with pytest.raises(ValueError,match="ACTIVATION_R16_RETAINED_FINANCIAL_OWNER_JOB_NOT_YET_ACCEPTED"):
        with activation.retain_activation_writer_guard(
                qd={},perp={},release_digest=ARTIFACT_DIGEST,
                owned_job=object()):
            pytest.fail("R16_FOREIGN_JOB_MUST_NOT_ENTER")
