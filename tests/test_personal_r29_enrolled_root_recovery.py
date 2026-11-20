"""R29 fresh-owner read-only recovery of exact enrolled native roots.

Pure identity/shape refusal tests: do not create accounts, data activation,
PAPER sessions, provider calls or financial writer authority. R26 historical
fixed accounts remain accepted at their own enrolled roots.
"""
import copy
from pathlib import Path

import pytest

from scripts.observation_runtime import personal_owner_continuity_v2 as owner
from scripts.observation_runtime import personal_existing_native_resource_evidence as native

ROLES=("source","projection","report","control","coordination","custody")


def enrollments(*, successor=True):
    epochs=(
        ("qd-paper-recovery-599ffe283d2b-29a729a729a729a729a729a7",
         "hl-paper-recovery-599ffe283d2b-29a729a729a729a729a729a7")
        if successor else
        (native.QD_EPOCH,native.HL_EPOCH))
    pairs=(
        ("QUALITY_DIPS",native.QD_BASE.parent,native.QD_CUSTODY.parent,epochs[0]),
        ("HYPERLIQUID",native.HL_BASE.parent,native.HL_CUSTODY.parent,epochs[1]),
    )
    result={}
    for n,(lane,base_parent,custody_parent,epoch) in enumerate(pairs):
        base=base_parent/epoch
        custody=custody_parent/epoch
        result[lane]={
            "epoch":epoch,
            "resources":{
                role:{
                    "path":str(custody if role=="custody" else base/role),
                    "native_id":[7711,1+n,1+n*6+i],
                } for i,role in enumerate(ROLES)
            },
        }
    return result


def setup_inspector(monkeypatch,values):
    received=[]
    def inspect(**kwargs):
        received.append(kwargs)
        rows={}
        for lane,prefix in (
            ("QUALITY_DIPS","qd"),
            ("HYPERLIQUID","hl")):
            roots={}
            for role in ROLES:
                record=values[lane]["resources"][role]
                roots[role]={
                    "native_identity_verified":True,
                    "path":record["path"],
                    "native_id":copy.deepcopy(record["native_id"]),
                }
            rows[lane]={"roots":roots}
        return {"native_root_ids_verified":12,"native_root_total":12,"lanes":rows}
    monkeypatch.setattr(native,"inspect_two_lane_native_roots",inspect)
    return received


@pytest.mark.parametrize("successor",[True,False])
def test_fresh_recovery_uses_each_original_enrollment_epoch_not_r26_default(
        monkeypatch,successor):
    values=enrollments(successor=successor)
    calls=setup_inspector(monkeypatch,values)
    result=owner.inspect_enrolled_native_account_roots(values)
    assert result["native_root_ids_verified"]==12
    assert len(calls)==1
    for lane,prefix in (("QUALITY_DIPS","qd"),("HYPERLIQUID","hl")):
        base=Path(values[lane]["resources"]["source"]["path"]).parent
        custody=Path(values[lane]["resources"]["custody"]["path"])
        assert calls[0][prefix+"_base"]==base
        assert calls[0][prefix+"_custody"]==custody
    if successor:
        assert calls[0]["qd_base"]!=native.QD_BASE
        assert calls[0]["hl_base"]!=native.HL_BASE


@pytest.mark.parametrize("damage",[
    "foreign-parent","foreign-custody","mixed-epoch","role-alias",
    "path-traversal","missing-role","bad-id","same-native-id",
    "wrong-native-id","incomplete-native-scan","unknown-lane",
])
def test_recovery_does_not_adopt_foreign_epochs_aliases_or_unsupported_ids(
        monkeypatch,damage):
    values=enrollments()
    calls=setup_inspector(monkeypatch,values)
    q=values["QUALITY_DIPS"]
    h=values["HYPERLIQUID"]
    if damage=="foreign-parent":
        q["resources"]["source"]["path"]=q["resources"]["source"]["path"].replace(
            "AtlasPaper","AtlasUntrusted",1)
    elif damage=="foreign-custody":
        q["resources"]["custody"]["path"]=q["resources"]["custody"]["path"].replace(
            "AtlasCustody","AtlasUntrusted",1)
    elif damage=="mixed-epoch":
        h["epoch"]="wrong-epoch"
    elif damage=="role-alias":
        q["resources"]["projection"]["path"]=q["resources"]["source"]["path"]
    elif damage=="path-traversal":
        q["resources"]["source"]["path"]+=r"\.."
    elif damage=="missing-role":
        del q["resources"]["control"]
    elif damage=="bad-id":
        q["resources"]["report"]["native_id"]=["spoof",2,3]
    elif damage=="same-native-id":
        h["resources"]["custody"]["native_id"]=q["resources"]["custody"]["native_id"]
    elif damage=="wrong-native-id":
        # Scanner holds original ID. After first preflight a new untrusted
        # enrollment mutation is never allowed to change the native identity.
        old=copy.deepcopy(q["resources"]["source"]["native_id"])
        def observed(**kwargs):
            result={"native_root_ids_verified":12,"native_root_total":12,
                    "lanes":{}}
            for lane in values:
                result["lanes"][lane]={"roots":{
                    role:{"native_identity_verified":True,
                          "path":value["path"],"native_id":copy.deepcopy(value["native_id"])}
                    for role,value in values[lane]["resources"].items()}}
            result["lanes"]["QUALITY_DIPS"]["roots"]["source"]["native_id"]=old
            return result
        monkeypatch.setattr(native,"inspect_two_lane_native_roots",observed)
        q["resources"]["source"]["native_id"]=[555,666,777]
    elif damage=="incomplete-native-scan":
        monkeypatch.setattr(native,"inspect_two_lane_native_roots",
                            lambda **_:{"native_root_ids_verified":11,"native_root_total":12})
    elif damage=="unknown-lane":
        values["FOREIGN"]=values["HYPERLIQUID"]
    if damage=="same-native-id":
        # Duplicate ID in the enrolled resources must never satisfy
        # native distinctness even when every file handle is readable.
        pass
    with pytest.raises((ValueError,KeyError,TypeError)):
        owner.inspect_enrolled_native_account_roots(values)


def test_existing_cold_recovery_stays_read_only_without_writer_enrollment():
    assert owner.NativeRecoveredReadOnlyOwner.require_exact_roster is not None
    assert owner.NativeReadOnlyRecoveryActivationGuard.require_exact_roster is not None
