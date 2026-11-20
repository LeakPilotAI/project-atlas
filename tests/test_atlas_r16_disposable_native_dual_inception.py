"""R16 two original account drafts -> 12 TEST-ONLY native roots -> real FS1/FS3.

Uses genuine Windows create-only file writers and genuine native-bound cold
readback under two strictly disposable pytest temp directories, but synthetic
in-memory issuer/owner/clock/coordination (NEVER accepted operator authority).
No writes to 12 ORIGINAL D:/AtlasCustody financial roots. No providers/orders,
no operational finance lease and no PAPER startup.
"""
from __future__ import annotations

import hashlib
import copy
import json
import os
import sys
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.services.paper_financial_replay import digest, initial_state
from app.services.personal_publication_custody import PersonalPublicationCustody
from app.services.quality_dips_autonomous_enrollment import (
    WRITERS as QD_WRITERS, validate_enrollment as validate_qd,
)
from app.services.perp_operational_contract import (
    WRITERS as HL_WRITERS, validate_enrollment as validate_hl,
)
from scripts.observation_runtime.atlas_r16_two_account_enrollment_handoff import (
    R16_ARTIFACT, inspect as draft_inspect,
)
from scripts.observation_runtime.atlas_r16_selected_code_readback import (
    RELEASE, selected_code,
)
from scripts.observation_runtime.personal_existing_native_resource_evidence import (
    ROLES, inspect_two_lane_native_roots,
)
from scripts.observation_runtime.personal_paper_inception import (
    NativePersonalInceptionFiles, NativePersonalInitialReadback,
    PersonalInceptionBootstrap, PersonalInceptionPublisher,
    native_primitives, validate_personal_inception,
)
from scripts.observation_runtime.quality_dips_read_service import observe_self
from scripts.observation_runtime.atlas_r16_two_account_financial_arithmetic import (
    POLICY_PATH, POLICY_SHA256,
)
from test_personal_session_reservation_integrity import Memory

# This test uses the EXACT SAME immutable source/native-writer bytes as
# installed R16, even though the test harness itself lives in host Git.
REQUIRED_INSTALLED_MODULES = {
    "scripts/observation_runtime/personal_paper_inception.py":
        "618383cbe352f9648ab008dc52872448630eb14c70442870e9943e263d3eb8c3",
    "scripts/volume_inspector/snapshot_store.py":
        "f28b27414969d11184c21487a02fba5176e47b6ad9f59fb23eca8f9efcc552a9",
    "backend/app/services/paper_financial_replay.py":
        "39494b81ba9ab1a6f5bd70730558ffe4be8fc95a5d9563c18d63bb13d9d572aa",
    "backend/app/services/paper_daily_report.py":
        "f702c767e36b990182c28291c135d65da9589e0ddd63e5acc8b624c0dd5fcb22",
}


def exact_disposable_test_root(path):
    """Fresh D: diagnostics child only; never original custody/runtime."""
    location = Path(path).resolve(strict=True)
    allowed = Path(__file__).resolve().parents[1]/"logs/diagnostics"
    allowed = allowed.resolve(strict=True)
    if (os.name != "nt" or location.parent != allowed
            or not location.name.startswith("atlas-r16-native-disposable-")
            or len(location.name) < 34
            or any(p.is_symlink() or p.is_junction()
                   for p in (location,allowed))
            or any(location.iterdir())):
        raise ValueError("R16_NATIVE_FINANCIAL_FIXTURE_MUST_USE_EMPTY_D_DIAGNOSTICS_CHILD")
    return location


def prepare_lane(lane, *, base, original, policy, native):
    """Rebind the authentic R16 manifest to synthetic TEST root identities."""
    if lane not in ("QUALITY_DIPS","HYPERLIQUID"):
        raise ValueError("R16_NATIVE_FIXTURE_UNKNOWN_LANE")
    if base.exists() or not base.parent.is_dir():
        raise ValueError("R16_NATIVE_FIXTURE_FRESH_LANE_REQUIRED")
    base.mkdir()
    manifest = copy.deepcopy(original["provisional_r16_parameters"])
    enrollment = copy.deepcopy(original["provisional_r16_enrollment_unaccepted"])
    scope = copy.deepcopy(original["provisional_r16_report_scope_unaccepted"])
    if (manifest["release"] != R16_ARTIFACT
            or enrollment["release_digest"] != R16_ARTIFACT
            or enrollment["writers"] is not None
            or enrollment["acceptance_id"] is not None):
        raise ValueError("R16_NATIVE_FIXTURE_ORIGINAL_PROPOSAL_UNACCEPTED_REQUIRED")
    original_resources = copy.deepcopy(enrollment["resources"])
    expected_roles = QD_WRITERS if lane=="QUALITY_DIPS" else HL_WRITERS
    creator = native.w.WindowsOutput
    created = {}
    for role in ROLES:
        with creator.create_root(str(base/role)) as out:
            created[role] = {
                "path":str(out.root),
                "native_id":native.native.file_identity(out.root_handle),
            }
    # No original account native root path is EVER passed to a native writer.
    for role in ROLES:
        assert created[role]["path"]!=original_resources[role]["path"]
        assert created[role]["native_id"]!=original_resources[role]["native_id"]
        enrollment["resources"][role].update(created[role])
    observed=observe_self()
    # Real original selected R16 D: Python identity; never forge a C:
    # development process into a trusted native financial writer.
    assert observed["image"].lower().startswith(
        "d:\\atlasruntime\\releases\\cadb3b5a163b31f9ee7bda32453a5983e809ccc0\\python\\")
    process={"schema":"QD_OP_PROCESS_ID_V1",**observed}
    enrollment["writers"]={role:copy.deepcopy(process) for role in expected_roles}
    enrollment["acceptance_id"]="DISPOSABLE_R16_TEST_NOT_OPERATOR_"+lane
    validated=(validate_qd if lane=="QUALITY_DIPS" else validate_hl)(enrollment)
    assert validated==enrollment
    e = {
        "profile":"PERSONAL_PAPER_ONLY_V1",
        "personal_policy":copy.deepcopy(policy),
        "lane":lane,
        "native_enrollment":enrollment,
        "parameters":manifest,
        "report_scope":scope,
    }
    validate_personal_inception(e)
    return e, original_resources


def publish_in_test_memory(e, *, at):
    """Use actual NativePersonalInceptionFiles + actual native cold readback.

    Operator issuer and owner are synthetic check-only test objects. Custody
    is sqlite :memory:, not any original native coordination directory.
    """
    custody_db = Memory()
    PersonalPublicationCustody.install_schema(custody_db.db)
    custody_db.db.commit()
    custody = PersonalPublicationCustody(custody_db)
    @contextmanager
    def test_only_issuer(scope, stamp):
        assert stamp == at
        yield SimpleNamespace(check=lambda candidate,t:
                              candidate == scope and t == at)
    @contextmanager
    def test_only_owner(context, stamp):
        assert stamp == at
        yield SimpleNamespace(check=lambda candidate,t:
                              candidate == context and t == at)
    issuer = SimpleNamespace(lease=test_only_issuer)
    owner = SimpleNamespace(lease=test_only_owner)
    bootstrap=PersonalInceptionBootstrap(
        enrollment=e, publication=custody,
        issuer=issuer, clock=lambda:at,
        readback=NativePersonalInitialReadback())
    publisher=PersonalInceptionPublisher(
        bootstrap=bootstrap, custody=custody, ownership=owner,
        observer=lambda:{"schema":"QD_OP_PROCESS_ID_V1",**observe_self()},
        files=NativePersonalInceptionFiles())
    try:
        ready=publisher.publish()
        assert ready["financial_startup_authorized"] is False
        assert NativePersonalInitialReadback().verify(
            e,ready["current"]) is True
        before=copy.deepcopy(ready["current"])
        # Actual original once-only publisher must refuse replay.
        with pytest.raises(ValueError):
            publisher.publish()
        assert bootstrap.verify_publication()["current"]==before
        return ready
    finally:
        custody_db.db.close()


@pytest.mark.skipif(
    sys.platform != "win32" or
    os.path.normcase(os.path.normpath(sys.executable)) !=
        os.path.normcase(os.path.normpath(str(RELEASE/"python/python.exe"))),
    reason="requires ORIGINAL selected R16 D: Python executable and Windows native file handles",
)
def test_selected_r16_both_original_paper_drafts_incept_in_disposable_native_files_only():
    # The real financial enrollment contract requires an absolute D: path;
    # Python/pytest defaults to C: TEMP. A unique native test root under
    # preexisting D: diagnostics is removed on exit, never an Atlas account.
    parent=Path(__file__).resolve().parents[1]/"logs/diagnostics"
    assert parent.is_dir() and not parent.is_symlink() and not parent.is_junction()
    with tempfile.TemporaryDirectory(
            prefix="atlas-r16-native-disposable-",dir=parent) as disposable:
        root=exact_disposable_test_root(disposable)
        _exercise_two_native_test_only_accounts(root)


def _exercise_two_native_test_only_accounts(root):
    actual_before=inspect_two_lane_native_roots()
    assert actual_before["native_root_total"]==12
    assert actual_before["all_twelve_distinct_and_empty"] is True
    assert selected_code()["selected_revision"]==15
    source_root=Path(__file__).resolve().parents[1]
    for relative,pin in REQUIRED_INSTALLED_MODULES.items():
        source=source_root/relative
        installed=RELEASE/relative
        assert source.is_file() and installed.is_file()
        assert not source.is_symlink() and not installed.is_symlink()
        assert hashlib.sha256(source.read_bytes()).hexdigest()==pin
        assert hashlib.sha256(installed.read_bytes()).hexdigest()==pin
    assert os.path.normcase(os.path.normpath(sys.executable))==(
        os.path.normcase(os.path.normpath(str(RELEASE/"python/python.exe"))))
    assert hashlib.sha256(POLICY_PATH.read_bytes()).hexdigest()==POLICY_SHA256
    policy=json.loads(POLICY_PATH.read_text(encoding="utf-8-sig"))
    proposal=draft_inspect()
    assert proposal["status"]=="R16_TWO_LANE_CURRENT_CODE_PROPOSAL_ONLY_UNACCEPTED"
    native=native_primitives()
    results={}
    seen_native_ids=set()
    at=int(time.time())
    for lane in ("QUALITY_DIPS","HYPERLIQUID"):
        original=proposal["accounts"][lane]
        e, original_resources=prepare_lane(
            lane,base=root/lane,original=original,policy=policy,native=native)
        assert at>e["parameters"]["opened_at"]
        for role in ROLES:
            native_root=e["native_enrollment"]["resources"][role]["native_id"]
            assert tuple(native_root) not in seen_native_ids
            seen_native_ids.add(tuple(native_root))
        ready=publish_in_test_memory(e,at=at)
        initial=initial_state(e["parameters"])
        assert initial["cash"]=="1000" and initial["positions"]=={}
        assert ready["current"]["state_digest"]==digest(initial)
        assert ready["current"]["revision"]==0
        assert ready["current"]["acknowledged_revision"]==0
        assert ready["current"]["status"]=="ACKNOWLEDGED"
        # A forged native FS1 revision or report-root handle must fail
        # independent reader validation, not be silently repaired.
        forged=copy.deepcopy(ready["current"])
        forged["revision"]=1
        with pytest.raises(ValueError):
            NativePersonalInitialReadback().verify(e,forged)
        forged=copy.deepcopy(ready["current"])
        forged["reports"]["root"]=[0,0,0]
        with pytest.raises(ValueError):
            NativePersonalInitialReadback().verify(e,forged)
        assert ready["current"]["source"]["entries"]==[]
        assert ready["current"]["projection"][
            "required"]==ready["current"]["projection"]["acknowledged"]==0
        assert {p.name for p in (root/lane/"source").iterdir()}=={"inception.json"}
        assert {p.name for p in (root/lane/"report").iterdir()}=={
            "scope.json","0001-report.json"}
        assert not list((root/lane/"projection").iterdir())
        assert not list((root/lane/"control").iterdir())
        assert not list((root/lane/"coordination").iterdir())
        assert not list((root/lane/"custody").iterdir())
        report=json.loads((root/lane/"report"/"0001-report.json").read_text())
        assert report["report"]["status"]=="INCOMPLETE"
        assert report["report"]["startup_authorized"] is False
        assert report["report"]["currency"]==(
            "USD" if lane=="QUALITY_DIPS" else "USDC")
        assert ready["financial_startup_authorized"] is False
        assert e["native_enrollment"]["acceptance_id"].startswith("DISPOSABLE_")
        results[lane] = {
            "opening_cash":"1000",
            "currency":e["parameters"]["currency"],
            "source_initial_state_verified":True,
            "native_fs1_fs3_cold_readback_verified":True,
            "original_account_roots_untouched":True,
            "financial_authority_accepted":False,
        }
        assert inspect_two_lane_native_roots()==actual_before
    assert len(seen_native_ids)==12
    assert results["QUALITY_DIPS"]["currency"]=="USD"
    assert results["HYPERLIQUID"]["currency"]=="USDC"
    assert sum(1 for p in root.rglob("*") if p.is_file())==6
    assert inspect_two_lane_native_roots()==actual_before


@pytest.mark.parametrize("invalid",[
    "foreigner","../AtlasRuntime","./T","/","R16_GLOBAL_NATIVE"
])
def test_disposable_root_refuses_foreign_namespace_or_bad_case(tmp_path,invalid):
    base=tmp_path/invalid
    with pytest.raises(ValueError):
        prepare_lane("FOREIGN_ACCOUNT",base=base,original={},policy={},
                     native=None)


@pytest.mark.parametrize("bogus",[r"D:\AtlasRuntime",r"D:\AtlasCustody",
                                   r"D:\Work\Project Atlas",tempfile.gettempdir()])
def test_test_only_disposable_root_guard_refuses_operational_or_c_paths(bogus):
    with pytest.raises(ValueError,match="R16_NATIVE_FINANCIAL_FIXTURE_MUST_USE_EMPTY_D_DIAGNOSTICS_CHILD"):
        exact_disposable_test_root(bogus)
