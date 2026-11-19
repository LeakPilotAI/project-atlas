"""Native successor PAPER root scope after the interrupted immutable R26 journals.

No directories, financial files, accounts, approval, process or order are
created here. New epoch roots may become eligible only under a distinct
selected-installed release and the exact historical R26 native read guard.
"""
from __future__ import annotations

import ntpath
import re
from pathlib import Path
from app.services.paper_financial_replay import body, strict
from scripts.observation_runtime.personal_existing_native_resource_evidence import (
    ROLES, inspect_two_lane_native_roots,
)
from scripts.observation_runtime.personal_r26_postjournal_historical_guard import (
    NativeR26HistoricalPostjournalGuard,
)

SCHEMA="ATLAS_R27_POSTR26_NEW_TWO_LANE_FINANCIAL_ROOT_SCOPE_V1"
LANES=("QUALITY_DIPS","HYPERLIQUID")
ORIGINAL_RELEASE="a746d99240f91609825b015b369020a4035d6501"
PARENTS={
    "QUALITY_DIPS":(Path(r"D:\AtlasPaper\QualityDips"),
                    Path(r"D:\AtlasCustody\QualityDips")),
    "HYPERLIQUID":(Path(r"D:\AtlasPaper\Hyperliquid"),
                   Path(r"D:\AtlasCustody\Hyperliquid")),
}
LEAF_PREFIX={"QUALITY_DIPS":"qd-paper-recovery-",
             "HYPERLIQUID":"hl-paper-recovery-"}


def successor_root_plan(*, successor_release, epoch_nonce):
    """Pure root blueprint; never authorizes provisioning or financial effects."""
    if (type(successor_release) is not str
            or re.fullmatch("[0-9a-f]{40}",successor_release) is None
            or successor_release==ORIGINAL_RELEASE
            or type(epoch_nonce) is not str
            or re.fullmatch("[0-9a-f]{24}",epoch_nonce) is None):
        raise ValueError("R27_SUCCESSOR_FRESH_RELEASE_AND_EPOCH_NONCE_REQUIRED")
    token=successor_release[:12]+"-"+epoch_nonce
    locations={}
    allpaths=[]
    for lane in LANES:
        parent,custody=PARENTS[lane]
        epoch=LEAF_PREFIX[lane]+token
        roots={}
        for role in ROLES:
            dest=(custody if role=="custody" else parent)/epoch
            path=dest if role=="custody" else dest/role
            paths=str(path)
            if (not paths.startswith("D:\\") or ntpath.normpath(paths)!=paths
                    or any(part in ("",".","..") for part in paths[3:].split("\\"))
                    or any(part in paths[2:] for part in ("%","\x00","/"))
                    or len(paths)>256):
                raise ValueError("R27_SUCCESSOR_EXACT_D_ROOT_PATH_REQUIRED")
            roots[role]=paths
            allpaths.append(paths.casefold())
        locations[lane]={"epoch":epoch,"roots":roots}
    if len(set(allpaths))!=12:
        raise ValueError("R27_SUCCESSOR_ROOT_ALIAS_REFUSED")
    return strict(body({
        "schema":SCHEMA, "successor_release":successor_release,
        "epoch_nonce":epoch_nonce,"lanes":locations,
        "old_r26_roots_may_be_reused":False,
        "financial_root_dirs_created":False,
        "account_inception_authorized":False,
        "paper_start_authorized":False,
        "live_money_trading_authorized":False,
    }))


def inspect_uncreated_successor_roots(*, plan):
    """Read-only existence check; not an approval to create missing directories."""
    if (type(plan) is not dict or plan!=successor_root_plan(
            successor_release=plan.get("successor_release"),
            epoch_nonce=plan.get("epoch_nonce"))):
        raise ValueError("R27_SUCCESSOR_UNMODIFIED_CANONICAL_ROOT_PLAN_REQUIRED")
    present=[]
    invalid_parents=[]
    for lane in LANES:
        base,custody=PARENTS[lane]
        for parent in (base,custody):
            if not parent.is_dir() or parent.is_symlink() or parent.is_junction():
                invalid_parents.append(str(parent))
        for role,path in plan["lanes"][lane]["roots"].items():
            node=Path(path)
            if node.exists() or node.is_symlink() or node.is_junction():
                present.append(path)
    if invalid_parents or present:
        raise ValueError("R27_SUCCESSOR_ROOT_ABSENT_AND_PARENT_INTEGRITY_REQUIRED")
    return {
        "schema":SCHEMA,
        "successor_release":plan["successor_release"],
        "all_twelve_prospective_financial_roots_absent":True,
        "four_parent_directories_verified":True,
        "original_journals_not_opened_or_changed":True,
        "native_root_creation_authorized":False,
        "financial_inception_authorized":False,
        "paper_start_authorized":False,
        "live_money_trading_authorized":False,
    }


class NativeSelectedSuccessorEpochRoots:
    """Selected-native NEW epoch handle inspector, bound to historical readback.

    Existing-only: the distinct 12 new directories must already be created
    under a separately approved provisioner. No path aliases or alternate
    caller-supplied native inspector can substitute for original Windows I/O.
    """
    def __init__(self, *, plan, historical_guard):
        if (type(historical_guard) is not NativeR26HistoricalPostjournalGuard
                or type(plan) is not dict
                or plan!=successor_root_plan(
                    successor_release=plan.get("successor_release"),
                    epoch_nonce=plan.get("epoch_nonce"))):
            raise ValueError("R27_SUCCESSOR_GENUINE_HISTORICAL_GUARD_AND_PLAN_REQUIRED")
        release=historical_guard.release
        expected=Path("D:/AtlasRuntime/releases")/plan["successor_release"]
        if (release.root!=expected
                or Path(__file__).absolute()!=expected/
                   "scripts/observation_runtime/personal_successor_native_root_scope.py"):
            raise ValueError("R27_SUCCESSOR_SELECTED_INSTALLED_MODULE_REQUIRED")
        evidence=historical_guard.capture()
        if (evidence.get("original_journals_verified")!=2
                or evidence.get("original_financial_account_publications")!=0
                or evidence.get("historical_writer_adoption_authorized") is not False
                or evidence.get("paper_start_authorized") is not False):
            raise ValueError("R27_SUCCESSOR_ORIGINAL_R26_HISTORY_NOT_QUIESCENT")
        self.plan=strict(body(plan))
        self.historical_guard=historical_guard
        self._ports=(historical_guard,release)
        self._first=self._observe()
        if self._first["existing_empty_root_namespaces"]!=12:
            raise ValueError("R27_SUCCESSOR_TWELVE_ORIGINAL_FRESH_ROOTS_REQUIRED")

    def _observe(self):
        paths=self.plan["lanes"]
        inventory=inspect_two_lane_native_roots(
            qd_base=PARENTS["QUALITY_DIPS"][0]/paths["QUALITY_DIPS"]["epoch"],
            qd_custody=PARENTS["QUALITY_DIPS"][1]/paths["QUALITY_DIPS"]["epoch"],
            hl_base=PARENTS["HYPERLIQUID"][0]/paths["HYPERLIQUID"]["epoch"],
            hl_custody=PARENTS["HYPERLIQUID"][1]/paths["HYPERLIQUID"]["epoch"],
        )
        if (inventory.get("native_root_total")!=12
                or inventory.get("native_root_ids_verified")!=12
                or inventory.get("filesystem_writes")!=0
                or inventory.get("network_requests")!=0):
            raise ValueError("R27_SUCCESSOR_NATIVE_ROOT_IDENTITY_REQUIRED")
        allids=[]
        for lane in LANES:
            lane_roots=inventory["lanes"][lane]["roots"]
            if inventory["lanes"][lane]["epoch"]!=paths[lane]["epoch"]:
                raise ValueError("R27_SUCCESSOR_EPOCH_DRIFT")
            for role in ROLES:
                observed=lane_roots[role]
                if (observed.get("path")!=paths[lane]["roots"][role]
                        or observed.get("native_identity_verified") is not True
                        or type(observed.get("native_id")) is not list):
                    raise ValueError("R27_SUCCESSOR_EXACT_ROLE_NATIVE_ROOT_REQUIRED")
                allids.append(tuple(observed["native_id"]))
        if len(set(allids))!=12:
            raise ValueError("R27_SUCCESSOR_CROSS_LANE_NATIVE_ID_ALIAS")
        return inventory

    def inspect(self):
        if (self.historical_guard is not self._ports[0]
                or self.historical_guard.release is not self._ports[1]
                or self.historical_guard.capture().get("original_journals_verified")!=2):
            raise ValueError("R27_SUCCESSOR_OLD_R26_JOURNAL_RECHECK_REFUSED")
        actual=self._observe()
        for lane in LANES:
            for role in ROLES:
                left=actual["lanes"][lane]["roots"][role]
                original=self._first["lanes"][lane]["roots"][role]
                if left["native_id"]!=original["native_id"]:
                    raise ValueError("R27_SUCCESSOR_NEW_ROOT_ID_CHANGED")
        return actual

    def authorize_account_issuance(self, **_kwargs):
        raise ValueError("R27_SUCCESSOR_ROOT_INSPECTOR_NOT_FINANCIAL_ISSUER")

    def create_missing_directories(self, **_kwargs):
        raise ValueError("R27_SUCCESSOR_ROOT_INSPECTOR_DOES_NOT_PROVISION_ROOTS")
