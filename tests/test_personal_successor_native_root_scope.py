"""Tests for future native successor root scope; no original financial writes."""
import copy
from pathlib import Path
from types import SimpleNamespace
import pytest

import scripts.observation_runtime.personal_successor_native_root_scope as scope

RELEASE="1"*40
NONCE="abcdef0123456789abcdef01"


def plan():
    return scope.successor_root_plan(successor_release=RELEASE,epoch_nonce=NONCE)


def test_fresh_successor_plan_is_canonical_and_not_an_issuer():
    p=plan()
    assert p["schema"]==scope.SCHEMA
    assert set(p["lanes"])==set(scope.LANES)
    assert len({path for lane in scope.LANES
                     for path in p["lanes"][lane]["roots"].values()})==12
    assert all(x.startswith("D:\\") for lane in scope.LANES
               for x in p["lanes"][lane]["roots"].values())
    assert p["old_r26_roots_may_be_reused"] is False
    assert p["financial_root_dirs_created"] is False
    assert p["account_inception_authorized"] is False
    assert p["paper_start_authorized"] is False
    assert p["live_money_trading_authorized"] is False


@pytest.mark.parametrize("bad", [
    "a"*39, "A"*40, scope.ORIGINAL_RELEASE,
    "../old", "garbage", "0"*41, "f"*40+"\\foreign",
])
def test_stale_or_noncanonical_successor_release_is_rejected(bad):
    with pytest.raises(ValueError,match="R27_SUCCESSOR"):
        scope.successor_root_plan(successor_release=bad,epoch_nonce=NONCE)


@pytest.mark.parametrize("nonce", ["", "x"*24, "0"*23, "0"*25, "A"*24, "..", "0"*24+"\\old"])
def test_succession_nonce_requires_exact_bounded_lowercase_hex(nonce):
    with pytest.raises(ValueError,match="R27_SUCCESSOR"):
        scope.successor_root_plan(successor_release=RELEASE,epoch_nonce=nonce)


def test_plan_rejects_changed_recovered_root_path_before_native_file_calls(monkeypatch):
    p=plan()
    p["lanes"]["QUALITY_DIPS"]["roots"]["coordination"]=r"D:\AtlasPaper\QualityDips\old"
    with pytest.raises(ValueError,match="R27_SUCCESSOR"):
        scope.inspect_uncreated_successor_roots(plan=p)


def test_uncreated_candidate_inspection_is_readonly_and_refuses_any_existing_target(monkeypatch):
    p=plan()
    class Parent:
        def __init__(self,value):self.value=str(value)
        def is_dir(self):return True
        def is_symlink(self):return False
        def is_junction(self):return False
        def __str__(self):return self.value
        def __truediv__(self,name):return Parent(self.value+'\\'+str(name))
    monkeypatch.setattr(scope,"PARENTS",{
        lane:(Parent(str(parents[0])),Parent(str(parents[1])))
        for lane,parents in scope.PARENTS.items()})
    class Candidate:
        existing=set()
        def __init__(self,value):self.value=str(value)
        def exists(self):return self.value in self.existing
        def is_symlink(self):return False
        def is_junction(self):return False
    monkeypatch.setattr(scope,"Path",Candidate)
    out=scope.inspect_uncreated_successor_roots(plan=p)
    assert out["all_twelve_prospective_financial_roots_absent"] is True
    assert out["native_root_creation_authorized"] is False
    Candidate.existing.add(p["lanes"]["QUALITY_DIPS"]["roots"]["source"])
    with pytest.raises(ValueError,match="R27_SUCCESSOR_ROOT_ABSENT"):
        scope.inspect_uncreated_successor_roots(plan=p)


def owner_fixture(monkeypatch):
    p=plan()
    class Historian:
        def __init__(self):
            self.release=SimpleNamespace(root=Path("D:/AtlasRuntime/releases")/RELEASE,artifact_digest="c"*64)
            self.valid=True
        def capture(self):
            if not self.valid:raise ValueError("ORIGINAL_JOURNAL_TAMPERED")
            return {
                "original_journals_verified":2,
                "original_financial_account_publications":0,
                "historical_writer_adoption_authorized":False,
                "paper_start_authorized":False,
            }
    monkeypatch.setattr(scope,"NativeR26HistoricalPostjournalGuard",Historian)
    monkeypatch.setattr(scope,"__file__",
      str(Path("D:/AtlasRuntime/releases")/RELEASE/
          "scripts/observation_runtime/personal_successor_native_root_scope.py"))
    roots={"schema":"ATLAS_TWO_LANE_EXISTING_NATIVE_ROOT_PRE_ENROLLMENT_V1",
           "native_root_total":12,"native_root_ids_verified":12,
           "existing_empty_root_namespaces":12,
           "all_twelve_distinct_and_empty":True,
           "filesystem_writes":0,"network_requests":0,"lanes":{}}
    x=10
    for lane in scope.LANES:
        records={}
        for role in scope.ROLES:
            x+=1
            records[role]={"native_id":[0,x,0],"path":p["lanes"][lane]["roots"][role],
                           "native_identity_verified":True,
                           "existing_empty_namespace_verified":True}
        roots["lanes"][lane]={"epoch":p["lanes"][lane]["epoch"],"roots":records}
    current=[roots]
    def inspect_two_lane_native_roots(**kwargs):
        for lane in scope.LANES:
            base=kwargs["qd_base" if lane=="QUALITY_DIPS" else "hl_base"]
            custody=kwargs["qd_custody" if lane=="QUALITY_DIPS" else "hl_custody"]
            assert base.name==p["lanes"][lane]["epoch"]
            assert custody.name==p["lanes"][lane]["epoch"]
        return copy.deepcopy(current[0])
    monkeypatch.setattr(scope,"inspect_two_lane_native_roots",inspect_two_lane_native_roots)
    return SimpleNamespace(p=p,historian=Historian(),current=current)


def test_native_root_scope_preserves_native_ids_and_original_historical_guard(monkeypatch):
    a=owner_fixture(monkeypatch)
    s=scope.NativeSelectedSuccessorEpochRoots(plan=a.p,historical_guard=a.historian)
    original=s.inspect()
    assert original["native_root_ids_verified"]==12
    assert original["existing_empty_root_namespaces"]==12
    with pytest.raises(ValueError,match="NOT_FINANCIAL_ISSUER"):
        s.authorize_account_issuance()
    with pytest.raises(ValueError,match="DOES_NOT_PROVISION"):
        s.create_missing_directories()


@pytest.mark.parametrize("damage", ["bad_history","populated_initial","identity_changed","new_release_changed",
                                    "new_root_alias","historical_changed","original_epoch_changed"])
def test_native_root_scope_refuses_changed_financial_namespace(monkeypatch,damage):
    a=owner_fixture(monkeypatch)
    if damage=="bad_history":
        a.historian.valid=False
    elif damage=="populated_initial":
        a.current[0]["existing_empty_root_namespaces"]=11
    elif damage=="new_release_changed":
        a.historian.release.root=Path("D:/AtlasRuntime/releases")/("f"*40)
    elif damage=="new_root_alias":
        a.current[0]["lanes"]["HYPERLIQUID"]["roots"]["source"]["native_id"]=(
            a.current[0]["lanes"]["QUALITY_DIPS"]["roots"]["source"]["native_id"])
    elif damage=="original_epoch_changed":
        a.current[0]["lanes"]["QUALITY_DIPS"]["epoch"]="forged-epoch"
    if damage in {"bad_history","populated_initial","new_release_changed",
                  "new_root_alias","original_epoch_changed"}:
        with pytest.raises((ValueError,TypeError)):
            scope.NativeSelectedSuccessorEpochRoots(plan=a.p,historical_guard=a.historian)
        return
    s=scope.NativeSelectedSuccessorEpochRoots(plan=a.p,historical_guard=a.historian)
    if damage=="identity_changed":
        a.current[0]["lanes"]["QUALITY_DIPS"]["roots"]["source"]["native_id"]=[999,999,999]
    elif damage=="historical_changed":
        a.historian.valid=False
    with pytest.raises(ValueError):
        s.inspect()


def test_carried_r27_native_roots_are_bound_to_new_selected_code_only(monkeypatch):
    """No new mkdir, journal or financial approval; uses a simulated exact proof."""
    a=owner_fixture(monkeypatch)
    from scripts.observation_runtime import personal_successor_release_carryforward as carry
    p=scope.successor_root_plan(
        successor_release=carry.R27_SOURCE,epoch_nonce=carry.EPOCH_NONCE)
    new_source="a"*40
    new_artifact="b"*64
    a.historian.release.root=Path("D:/AtlasRuntime/releases")/new_source
    a.historian.release.artifact_digest=new_artifact
    monkeypatch.setattr(scope,"__file__",str(
        a.historian.release.root/
        "scripts/observation_runtime/personal_successor_native_root_scope.py"))
    for lane in scope.LANES:
        a.current[0]["lanes"][lane]["epoch"]=p["lanes"][lane]["epoch"]
        for role in scope.ROLES:
            a.current[0]["lanes"][lane]["roots"][role]["path"]=p["lanes"][lane]["roots"][role]
    copied=copy.deepcopy(a.current[0])
    monkeypatch.setattr(scope,"inspect_two_lane_native_roots",
                        lambda **kwargs:copy.deepcopy(a.current[0]))
    def proof(*,plan,selected_code_release,selected_code_digest):
        assert plan==p
        assert selected_code_release==new_source
        assert selected_code_digest==new_artifact
        return {"original_R27_terms_digest":"1"*64,
                "original_R27_artifact_digest":carry.R27_ARTIFACT},copied
    monkeypatch.setattr(carry,"verified_carried_r27_roots",proof)
    bound=scope.NativeSelectedSuccessorEpochRoots(
        plan=p,historical_guard=a.historian)
    assert bound.root_provisioning_terms_digest=="1"*64
    assert bound.root_provisioning_artifact_digest==carry.R27_ARTIFACT
    assert bound.exact_selected_release_bound(new_source,new_artifact)
    assert bound.inspect()["lanes"]==copied["lanes"]
    with pytest.raises(ValueError,match="SELECTED_CODE_OR_FINANCIAL_OWNER_CHANGED"):
        bound.exact_selected_release_bound(carry.R27_SOURCE,new_artifact)
    a.current[0]["lanes"]["HYPERLIQUID"]["roots"]["report"]["native_id"]=[9,8,7]
    with pytest.raises(ValueError,match="NATIVE_ROOTS_NO_LONGER|NEW_ROOT_ID"):
        bound.inspect()
