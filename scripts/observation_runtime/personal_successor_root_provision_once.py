"""R27 successor financial-root provisioner: one-shot and approval-only.

This module never creates account journals, financial activation, accounts,
provider connections or orders. It is NOT used by the R26 initializer. An
operator may separately approve 12 new EMPTY simulated account root directories
in a selected successor installed release after native R26 historical readback.
No retries after any intent, partial mkdir, or uncertain outcome.
"""
from __future__ import annotations

import ctypes
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from app.services.paper_financial_replay import body, digest, strict
from scripts.observation_runtime.personal_r26_postjournal_historical_guard import (
    NativeR26HistoricalPostjournalGuard,
)
from scripts.observation_runtime.personal_successor_native_root_scope import (
    LANES, PARENTS, ROLES, inspect_uncreated_successor_roots,
    successor_root_plan, NativeSelectedSuccessorEpochRoots,
)

SCOPE="APPROVE_ATLAS_R27_CREATE_ONLY_12_NEW_SIMULATED_ACCOUNT_DIRS_NO_PAPER_START"
SCHEMA="ATLAS_R27_ONE_TIME_NATIVE_NEW_SIMULATED_ACCOUNT_ROOT_PROVISIONING_V1"
LOG=Path(r"D:\Work\Project Atlas\logs\diagnostics")
# Two epoch containers + ten PAPER leaves and two custody epochs = 14 mkdirs.
EXPECTED_DIRECTORIES=14


def exact_scope(*, plan, successor_release_digest, terms_review_digest):
    """Immutable exact action description, not an operator decision."""
    if (type(plan) is not dict or plan!=successor_root_plan(
            successor_release=plan.get("successor_release"),
            epoch_nonce=plan.get("epoch_nonce"))
            or type(successor_release_digest) is not str
            or len(successor_release_digest)!=64
            or any(c not in "0123456789abcdef" for c in successor_release_digest)
            or type(terms_review_digest) is not str
            or len(terms_review_digest)!=64
            or any(c not in "0123456789abcdef" for c in terms_review_digest)):
        raise ValueError("R27_ROOT_PROVISIONING_EXACT_REVIEW_INPUTS_REQUIRED")
    return strict(body({
        "schema":SCHEMA, "scope":SCOPE,
        "action":"CREATE_ONLY_TWELVE_EMPTY_NEW_FINANCIAL_ROOTS",
        "successor_release":plan["successor_release"],
        "successor_release_digest":successor_release_digest,
        "terms_review_digest":terms_review_digest,
        "plan_digest":digest(plan),
        "epoch_nonce":plan["epoch_nonce"],
        "root_directories":{
            lane:plan["lanes"][lane]["roots"] for lane in LANES
        },
        "new_directories_max":EXPECTED_DIRECTORIES,
        "existing_R26_journals_not_modifiable":True,
        "financial_journal_creation_authorized":False,
        "financial_activation_authorized":False,
        "account_initialization_authorized":False,
        "paper_start_authorized":False,
        "live_money_trading_authorized":False,
    }))


def _visible_local_operator():
    if os.name!="nt" or not sys.stdin.isatty():
        raise ValueError("R27_ROOT_PROVISIONING_VISIBLE_WINDOWS_CONSOLE_REQUIRED")
    kernel=ctypes.WinDLL("kernel32",use_last_error=True)
    user=ctypes.WinDLL("user32",use_last_error=True)
    kernel.GetConsoleWindow.restype=ctypes.c_void_p
    user.IsWindowVisible.argtypes=[ctypes.c_void_p]
    user.IsWindowVisible.restype=ctypes.c_int
    hwnd=kernel.GetConsoleWindow()
    if not hwnd or user.IsWindowVisible(hwnd)!=1:
        raise ValueError("R27_ROOT_PROVISIONING_VISIBLE_WINDOWS_CONSOLE_REQUIRED")
    from scripts.volume_inspector.windows_output import current_sid
    return current_sid()


def _create_only_json(path,record):
    data=(json.dumps(record,sort_keys=True,indent=2,allow_nan=False)+"\n").encode()
    with path.open("xb") as file:
        file.write(data)
        file.flush()
        os.fsync(file.fileno())
    return hashlib.sha256(data).hexdigest()


def _attempt_paths(plan):
    token=plan["successor_release"][:12]+"-"+plan["epoch_nonce"]
    if (not LOG.is_dir() or LOG.is_symlink() or LOG.is_junction()):
        raise ValueError("R27_ROOT_PROVISIONING_D_ONLY_AUDIT_PARENT_REQUIRED")
    return (LOG/("atlas-r27-successor-root-provision-attempt-"+token+".json"),
            LOG/("atlas-r27-successor-root-provision-success-"+token+".json"))


def _new_directories(plan):
    """14 exact mkdir targets, parent before child; no recursion/overwrite."""
    targets=[]
    for lane in LANES:
        base,custody=PARENTS[lane]
        epoch=plan["lanes"][lane]["epoch"]
        targets.append(base/epoch)
        for role in ROLES:
            if role!="custody":
                targets.append(Path(plan["lanes"][lane]["roots"][role]))
        targets.append(custody/epoch)
    if len(targets)!=EXPECTED_DIRECTORIES or len(set(targets))!=len(targets):
        raise ValueError("R27_ROOT_PROVISIONING_EXACT_NEW_ROOT_COUNT_REQUIRED")
    return targets


class NativeSuccessorRootProvisioningOnce:
    """Valid successor installed release + original R26 history + new review.

    The constructor/preflight do not write. The execute method requires a
    signed-in operator typing the entire single-use scope in a visible console
    *after* seeing the 12 paths, then reserves an immutable local attempt.
    """
    def __init__(self, *, plan, historical_guard, reviewed_terms):
        if (type(historical_guard) is not NativeR26HistoricalPostjournalGuard
                or type(plan) is not dict
                or plan!=successor_root_plan(
                    successor_release=plan.get("successor_release"),
                    epoch_nonce=plan.get("epoch_nonce"))
                or type(reviewed_terms) is not dict):
            raise ValueError("R27_PROVISIONING_NATIVE_HISTORICAL_AND_TERMS_PORTS_REQUIRED")
        release=historical_guard.release
        expected=Path("D:/AtlasRuntime/releases")/plan["successor_release"]
        if (release.root!=expected
                or Path(__file__).absolute()!=expected/
                   "scripts/observation_runtime/personal_successor_root_provision_once.py"):
            raise ValueError("R27_PROVISIONING_GENUINE_SELECTED_INSTALLED_RELEASE_REQUIRED")
        from scripts.observation_runtime.personal_successor_account_terms_review import (
            SCHEMA as REVIEW_SCHEMA, ORIGINAL_ACCOUNTS,
            ORIGINAL_ENROLLMENT_DIGESTS, ORIGINAL_MANIFEST_DIGESTS,
            ORIGINAL_ECONOMIC_DIGESTS,
        )
        if (reviewed_terms.get("schema")!=REVIEW_SCHEMA
                or reviewed_terms.get("status")!=
                   "EXACT_NEW_EPOCH_TERMS_FOR_OPERATOR_REVIEW_ONLY"
                or reviewed_terms.get("successor_release")!=plan["successor_release"]
                or reviewed_terms.get("epoch_nonce")!=plan["epoch_nonce"]
                or reviewed_terms.get("successor_artifact_digest")!=release.artifact_digest
                or reviewed_terms.get("old_approval_transferred") is not False
                or reviewed_terms.get("new_operator_approval_issued") is not False
                or reviewed_terms.get("new_journal_or_account_created") is not False
                or reviewed_terms.get("paper_start_authorized") is not False
                or reviewed_terms.get("live_money_trading_authorized") is not False
                or type(reviewed_terms.get("accounts")) is not dict
                or set(reviewed_terms["accounts"])!=set(LANES)):
            raise ValueError("R27_PROVISIONING_EXACT_UNAPPROVED_NEW_ECONOMIC_REVIEW_REQUIRED")
        for lane in LANES:
            item=reviewed_terms["accounts"][lane]
            if (type(item) is not dict
                    or item.get("old_original_enrollment_digest")!=ORIGINAL_ENROLLMENT_DIGESTS[lane]
                    or item.get("old_original_manifest_digest")!=ORIGINAL_MANIFEST_DIGESTS[lane]
                    or item.get("economic_terms_digest")!=ORIGINAL_ECONOMIC_DIGESTS[lane]
                    or digest(item.get("exact_economic_terms"))!=ORIGINAL_ECONOMIC_DIGESTS[lane]
                    or item.get("new_epoch")!=plan["lanes"][lane]["epoch"]
                    or item.get("new_account_id")!=ORIGINAL_ACCOUNTS[lane]+"-recovery-"+plan["epoch_nonce"]
                    or item.get("prospective_paths")!=plan["lanes"][lane]["roots"]
                    or item.get("opening_timestamp_pending_independent_native_UTC") is not True
                    or item.get("new_native_resource_ids_pending") is not True
                    or item.get("new_windows_process_writer_roster_pending") is not True
                    or item.get("new_local_operator_financial_review_required") is not True
                    or item.get("account_initialized") is not False):
                raise ValueError("R27_PROVISIONING_EXACT_ORIGINAL_R26_FINANCIAL_TERMS_REQUIRED")
        self._plan=strict(body(plan))
        self._historian=historical_guard
        self._terms=strict(body(reviewed_terms))
        self._source=(historical_guard,release,release.artifact_digest,
                      digest(self._plan),digest(self._terms))
        self._scope=exact_scope(plan=self._plan,
            successor_release_digest=release.artifact_digest,
            terms_review_digest=digest(self._terms))
        if historical_guard.capture().get("original_journals_verified")!=2:
            raise ValueError("R27_PROVISIONING_TWO_ORIGINAL_JOURNALS_REQUIRED")

    def preflight(self):
        historian,release,artifact,plan_pin,terms_pin=self._source
        if (self._historian is not historian
                or historian.release is not release
                or release.artifact_digest!=artifact
                or digest(self._plan)!=plan_pin or digest(self._terms)!=terms_pin
                or historian.capture().get("original_financial_account_publications")!=0):
            raise ValueError("R27_PROVISIONING_HISTORICAL_OR_REVIEW_BINDING_CHANGED")
        for parent in {parent for pair in PARENTS.values() for parent in pair}:
            if not parent.is_dir() or parent.is_symlink() or parent.is_junction():
                raise ValueError("R27_PROVISIONING_FINANCIAL_PARENT_UNSAFE")
        absent=inspect_uncreated_successor_roots(plan=self._plan)
        if absent["all_twelve_prospective_financial_roots_absent"] is not True:
            raise ValueError("R27_PROVISIONING_NEW_ROOTS_NOT_ABSENT")
        for item in _new_directories(self._plan):
            if item.exists() or item.is_symlink() or item.is_junction():
                raise ValueError("R27_PROVISIONING_CANDIDATE_ALREADY_PRESENT")
        attempt,success=_attempt_paths(self._plan)
        if (attempt.exists() or success.exists() or attempt.is_symlink()
                or success.is_symlink()):
            raise ValueError("R27_PROVISIONING_ATTEMPT_OR_SUCCESS_ALREADY_RESERVED")
        return strict(body({
            "schema":SCHEMA,"status":"NATIVE_PROVISIONING_PREFLIGHT_ONLY",
            "scope":self._scope,"create_new_dirs_max":EXPECTED_DIRECTORIES,
            "new_root_namespaces_verified_absent":12,
            "historical_journals_preserved":2,
            "new_native_provisioning_attempt_created":False,
            "paper_start_authorized":False,
            "live_money_trading_authorized":False,
        }))

    def execute_after_visible_local_approval(self):
        """One irreversible create-only attempt; NEVER retry partial outcomes."""
        before=self.preflight()
        sid=_visible_local_operator()
        print(json.dumps(before,sort_keys=True,indent=2),flush=True)
        if input("TYPE THE ENTIRE ONE-TIME DIRECTORY-ONLY SCOPE: ").strip()!=SCOPE:
            raise ValueError("R27_PROVISIONING_LOCAL_OPERATOR_DECLINED")
        if _visible_local_operator()!=sid:
            raise ValueError("R27_PROVISIONING_OPERATOR_CHANGED")
        self.preflight()
        attempt,success=_attempt_paths(self._plan)
        # Reserve immutable attempt BEFORE first native financial-directory
        # effect. A crash leaves a stop marker and cannot be replayed.
        original={"schema":SCHEMA, "status":"CREATE_ONLY_NATIVE_DIRECTORY_ATTEMPT_STARTED",
            "operator_sid":sid,"scope":self._scope,"files_created":0,
            "journal_or_account_create_authorized":False,
            "paper_start_authorized":False,
            "live_money_trading_authorized":False,
            "time_utc":datetime.now(timezone.utc).isoformat()}
        _create_only_json(attempt,original)
        # Python mkdir inherits broad NTFS ACLs and is NOT compatible with
        # Atlas's protected SID+SYSTEM-only native financial output. Use the
        # existing tested handle-relative Windows create-only primitive.
        from scripts.observation_runtime.personal_paper_inception import native_primitives
        native=native_primitives()
        for directory in _new_directories(self._plan):
            parent=directory.parent
            if not parent.is_dir() or parent.is_symlink() or parent.is_junction():
                raise ValueError("R27_PROVISIONING_PARENT_CHANGED_STOP_NO_RETRY")
            if directory.exists() or directory.is_symlink() or directory.is_junction():
                raise ValueError("R27_PROVISIONING_NATIVE_ROOT_ALREADY_PRESENT_NO_RETRY")
            with native.w.WindowsOutput.create_root(str(directory)) as output:
                output._verify()
        from scripts.observation_runtime.personal_existing_native_resource_evidence import (
            inspect_two_lane_native_roots,
        )
        qd=self._plan["lanes"]["QUALITY_DIPS"]["epoch"]
        hl=self._plan["lanes"]["HYPERLIQUID"]["epoch"]
        roots=inspect_two_lane_native_roots(
            qd_base=PARENTS["QUALITY_DIPS"][0]/qd,
            qd_custody=PARENTS["QUALITY_DIPS"][1]/qd,
            hl_base=PARENTS["HYPERLIQUID"][0]/hl,
            hl_custody=PARENTS["HYPERLIQUID"][1]/hl,
        )
        if (roots["native_root_ids_verified"]!=12
                or roots["all_twelve_distinct_and_empty"] is not True
                or self._historian.capture().get("original_journals_verified")!=2):
            raise ValueError(
                "R27_PROVISIONING_NATIVE_FINAL_READBACK_REFUSED_NO_RETRY:"
                +str((roots.get("native_root_total"),
                      roots.get("native_root_ids_verified"),
                      roots.get("existing_empty_root_namespaces"),
                      roots.get("all_twelve_distinct_and_empty"))))
        result={"schema":SCHEMA,
          "status":"TWELVE_NEW_EMPTY_ROOTS_NATIVE_ID_VERIFIED_NOT_FINANCIAL_AUTHORITY",
          "scope":self._scope, "intent_sha256":hashlib.sha256(attempt.read_bytes()).hexdigest(),
          "native_12_roots":roots,"new_financial_directories_created":EXPECTED_DIRECTORIES,
          "new_journals_created":0,"new_accounts_opened":0,
          "old_r26_journals_unchanged":True,
          "financial_activation_authorized":False,
          "paper_start_authorized":False,"live_money_trading_authorized":False}
        _create_only_json(success,result)
        return strict(body(result))
