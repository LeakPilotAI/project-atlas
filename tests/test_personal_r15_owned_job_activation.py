"""Selected R15 activation must be bound to a genuinely owned Windows Job.

An observed live installed-R15 process is NOT by itself an Atlas financial
writer. No test publishes a real activation, creates accounts or sends orders.
"""
import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

from app.services.paper_financial_replay import digest
from app.services.personal_paper_runtime import validate_policy
from app.services.quality_dips_autonomous_enrollment import (
    WRITERS as QD_WRITERS, validate_enrollment as validate_qd,
)
from app.services.perp_operational_contract import (
    WRITERS as HL_WRITERS, validate_enrollment as validate_hl,
)
from scripts.observation_runtime import personal_activation_commission as activation
from scripts.observation_runtime.atlas_independent_ntp_clock import SOURCE
from scripts.observation_runtime.atlas_r15_disposable_writer_process_audit import (
    _windows_handle_identity,
)
from scripts.observation_runtime.atlas_r15_paper_offline_commissioning import (
    ARTIFACT, RELEASE,
)
from scripts.observation_runtime.atlas_r15_two_account_enrollment_handoff import (
    inspect as draft,
)
from scripts.observation_runtime.personal_native_job import ContainedChild
from scripts.observation_runtime.personal_r15_owned_job_activation import (
    RetainedSelectedR15OwnerJob,
)
from scripts.observation_runtime.personal_version_safe_release_clock import PROFILE

IMAGE = str(RELEASE/"python/python.exe")


@pytest.mark.parametrize("malformed",[
    None, object(), False, "owned", {}, 5,
])
def test_foreign_claim_is_not_a_retained_contained_child(malformed):
    with pytest.raises(ValueError,match="R15_ACTIVATION_EXACT_OWNED_JOB_REQUIRED"):
        RetainedSelectedR15OwnerJob(child=malformed,qd={},perp={})


def test_bare_unowned_process_api_cannot_be_adopted():
    fake=ContainedChild(api=None,job=123,process=456)
    with pytest.raises(ValueError,match="R15_ACTIVATION_EXACT_OWNED_JOB_REQUIRED"):
        RetainedSelectedR15OwnerJob(child=fake,qd={},perp={})


@pytest.mark.skipif(sys.platform!="win32",reason="Actual installed R15 Windows process required")
def test_actual_alive_r15_executable_without_atlas_owned_job_refused_before_clock_and_publication(
        tmp_path,monkeypatch):
    child=subprocess.Popen(
        [IMAGE,"-I","-B","-S","-c","import time; time.sleep(10)"],
        cwd=str(RELEASE),stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
        creationflags=subprocess.DETACHED_PROCESS)
    try:
        actual=_windows_handle_identity(child._handle)
        identity={"schema":"QD_OP_PROCESS_ID_V1","pid":child.pid,
                  "creation_filetime":actual["creation_filetime"],
                  "image":actual["image"]}
        assert child.poll() is None
        proposal=draft()
        records={}
        for lane,roles,validator in (
                ("QUALITY_DIPS",QD_WRITERS,validate_qd),
                ("HYPERLIQUID",HL_WRITERS,validate_hl)):
            e=copy.deepcopy(proposal["accounts"][lane][
                "provisional_r15_native_enrollment_unaccepted"])
            e["writers"]={role:copy.deepcopy(identity) for role in roles}
            e["acceptance_id"]="SYNTHETIC_UNCONTAINED_TEST_NOT_APPROVED"
            records[lane]=validator(e)
        accounts={lane:digest(value) for lane,value in records.items()}
        policy=json.loads((Path(__file__).resolve().parents[1]/
            "docs/ATLAS_PERSONAL_PAPER_RELEASE_POLICY.json").read_text(encoding="utf-8"))
        record={"schema":"ATLAS_PERSONAL_ACTIVATION_V1",
                "origin":"LOCAL_OPERATOR","actions":["READ_ONLY"],
                "release_digest":ARTIFACT,"accounts":accounts,
                "policy_digest":digest(validate_policy(policy))}
        paths={}
        for key,value in (
                ("qd",records["QUALITY_DIPS"]),("hl",records["HYPERLIQUID"]),
                ("accounts",accounts),("record",record),("policy",policy)):
            path=tmp_path/(key+".json")
            path.write_text(json.dumps(value,sort_keys=True),encoding="utf-8")
            paths[key]=str(path)
        monkeypatch.setattr(activation,"NativeVersionSafePaperOperatorClock",
                            lambda **_:pytest.fail("NO_CLOCK_FOR_UNOWNED_PROCESS"))
        monkeypatch.setattr(activation,"publish_personal_activation",
                            lambda **_:pytest.fail("NO_PUBLICATION_FOR_UNOWNED_PROCESS"))
        native_root=r"D:\AtlasCustody\PersonalPaper\unowned-alive-r15-job-test"
        assert not Path(native_root).exists()
        with pytest.raises(ValueError,match="ACTIVATION_R15_RETAINED_NATIVE_JOB_REQUIRED"):
            activation.commission(
                root=native_root,record_path=paths["record"],
                policy_path=paths["policy"],release_digest=ARTIFACT,
                accounts_path=paths["accounts"],expected_clock_source=SOURCE,
                runtime_id="NONFINANCIAL_UNOWNED_R15_TEST",
                qd_enrollment_path=paths["qd"],perp_enrollment_path=paths["hl"],
                clock_profile=PROFILE)
        assert child.poll() is None
        assert not Path(native_root).exists()
    finally:
        if child.poll() is None:
            child.terminate()
            child.wait(timeout=5)


@pytest.mark.parametrize("foreign",[None,object(),False,{"job":123},123])
def test_r15_guard_refuses_any_claim_without_original_held_job(foreign,monkeypatch):
    """Foreign or absent Job must fail BEFORE opening an enrollment-supplied PID."""
    from scripts.observation_runtime import personal_native_writer_lifetime as legacy
    monkeypatch.setattr(legacy,"retain_live_enrollment_writers",
                        lambda *a,**k:pytest.fail("R15_MUST_NOT_REOPEN_A_PID"))
    with pytest.raises(ValueError,match="ACTIVATION_R15_RETAINED_NATIVE_JOB_REQUIRED"):
        with activation.retain_activation_writer_guard(
                qd={},perp={},release_digest=ARTIFACT,owned_job=foreign):
            pytest.fail("FOREIGN_JOB_MUST_NOT_BE_ENTERED")


def test_old_release_writer_guard_still_uses_original_retained_handle_port(monkeypatch):
    from contextlib import contextmanager
    from scripts.observation_runtime import personal_native_writer_lifetime as legacy
    counts=[]
    proof=object()
    @contextmanager
    def original(qd,perp,*,release_digest):
        counts.append(("entered",qd,perp,release_digest))
        yield proof
        counts.append(("exited",))
    monkeypatch.setattr(legacy,"retain_live_enrollment_writers",original)
    with activation.retain_activation_writer_guard(
            qd={"lane":"QD"},perp={"lane":"HL"},release_digest="f"*64) as port:
        assert port is proof
    assert counts == [
        ("entered",{"lane":"QD"},{"lane":"HL"},"f"*64),("exited",),
    ]


def test_old_release_refuses_any_foreign_r15_job_before_process_open(monkeypatch):
    from scripts.observation_runtime import personal_native_writer_lifetime as legacy
    monkeypatch.setattr(legacy,"retain_live_enrollment_writers",
                        lambda *a,**k:pytest.fail("FOREIGN_JOB_NOT_ALLOWED"))
    with pytest.raises(ValueError,match="ACTIVATION_FOREIGN_JOB_OR_RELEASE_REFUSED"):
        with activation.retain_activation_writer_guard(
                qd={},perp={},release_digest="f"*64,owned_job=object()):
            pytest.fail("FOREIGN_JOB_NOT_ALLOWED")
