"""Require *owned Windows Job HANDLE* for selected R15 writer activation.

Liveness of an arbitrary exact-PID process is insufficient: it may not be the
parked child which the current Atlas owner is able to stop. The owner must
retain the exact Job and PROCESS HANDLE from suspended Job admission, prove
the process belongs to that job, prove kill-on-close, and prove that all
Quality Dips and Hyperliquid writer roles resolve to this one live process.

This is a necessary prepublication identity/containment check, NOT a lease
over ledgers, source rights, independent issuer approval or a trading grant.
It can be used only in the same trusted owner process retaining the handles.
"""
import ctypes
import ntpath
import os
from copy import deepcopy
from ctypes import wintypes

from app.services.paper_financial_replay import digest
from scripts.observation_runtime.atlas_r15_disposable_writer_process_audit import (
    _windows_handle_identity,
)
from scripts.observation_runtime.atlas_r15_paper_offline_commissioning import (
    ARTIFACT, RELEASE, SELECTED_HEAD, selected_code,
)
from scripts.observation_runtime.personal_native_job import ContainedChild
from scripts.observation_runtime.personal_native_windows_api import (
    JOB_OBJECT_EXTENDED_LIMIT_INFORMATION_CLASS,
    JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE,
    JOBOBJECT_EXTENDED_LIMIT_INFORMATION,
    WindowsJobAPI,
)
from scripts.observation_runtime.personal_native_writer_lifetime import (
    writer_roster,
)
from scripts.observation_runtime.personal_existing_native_resource_evidence import (
    ROLES, inspect_two_lane_native_roots,
)

SCHEMA = "ATLAS_R15_RETAINED_OWNED_JOB_BOTH_FINANCIAL_WRITER_ROSTERS_V1"
WAIT_TIMEOUT = 258


def require_exact_r15_preinception_roots(qd, perp, evidence):
    """Bind real empty native roots to BOTH enrollment rosters, not a PID alone.

    This is a pre-inception constraint, deliberately invalid once account
    files exist. It cannot authorize publication, account creation or PAPER.
    """
    if (type(qd) is not dict or type(perp) is not dict
            or type(evidence) is not dict
            or evidence.get("schema") !=
                "ATLAS_TWO_LANE_EXISTING_NATIVE_ROOT_PRE_ENROLLMENT_V1"
            or evidence.get("native_root_total") != 12
            or evidence.get("native_root_ids_verified") != 12
            or evidence.get("existing_empty_root_namespaces") != 12
            or evidence.get("all_twelve_distinct_and_empty") is not True
            or any(evidence.get(k) is not False for k in (
                "operator_account_enrollment_verified",
                "writer_ownership_verified",
                "financial_inception_verified",
                "paper_start_authorized", "live_trading_authorized"))
            or evidence.get("filesystem_writes") != 0
            or evidence.get("network_requests") != 0
            or type(evidence.get("lanes")) is not dict
            or set(evidence["lanes"]) != {"QUALITY_DIPS", "HYPERLIQUID"}):
        raise ValueError("R15_ACTIVATION_EXACT_EMPTY_NATIVE_PREINCEPTION_REQUIRED")
    bound = []
    ids = set()
    paths = set()
    for lane, enrollment in (("QUALITY_DIPS", qd), ("HYPERLIQUID", perp)):
        lane_evidence = evidence["lanes"][lane]
        if (type(lane_evidence) is not dict
                or type(enrollment.get("resources")) is not dict
                or set(enrollment["resources"]) != set(ROLES)
                or type(lane_evidence.get("roots")) is not dict
                or set(lane_evidence["roots"]) != set(ROLES)
                or lane_evidence.get("epoch") != enrollment.get("epoch")):
            raise ValueError("R15_ACTIVATION_TWO_EXACT_NATIVE_ENROLLMENT_ROOTS_REQUIRED")
        for role in ROLES:
            actual = lane_evidence["roots"][role]
            expected = enrollment["resources"][role]
            if (type(actual) is not dict or type(expected) is not dict
                    or actual.get("native_identity_verified") is not True
                    or actual.get("existing_empty_namespace_verified") is not True
                    or type(actual.get("native_id")) is not list
                    or len(actual["native_id"]) != 3
                    or any(type(k) is not int or k < 0
                           for k in actual["native_id"])
                    or type(actual.get("path")) is not str
                    or actual["path"] != expected.get("path")
                    or actual["native_id"] != expected.get("native_id")):
                raise ValueError("R15_ACTIVATION_NATIVE_RESOURCE_IDENTITY_CHANGED")
            identity = tuple(actual["native_id"])
            path = actual["path"].casefold()
            if identity in ids or path in paths:
                raise ValueError("R15_ACTIVATION_TWO_LANE_ROOT_ALIAS_REFUSED")
            ids.add(identity)
            paths.add(path)
            bound.append((lane, role, actual["path"], identity))
    if len(ids) != 12:
        raise ValueError("R15_ACTIVATION_ALL_TWELVE_NATIVE_ROOTS_REQUIRED")
    return tuple(bound)


class RetainedSelectedR15OwnerJob:
    """Retained native Job+PROCESS handles; no standalone authority issuer."""

    def __init__(self, *, child, qd, perp):
        if (os.name != "nt" or type(child) is not ContainedChild
                or type(child.api) is not WindowsJobAPI or child.closed
                or not child.job or not child.process):
            raise ValueError("R15_ACTIVATION_EXACT_OWNED_JOB_REQUIRED")
        self.child = child
        self.api = child.api
        self.job, self.process = child.job, child.process
        self._original_selected = selected_code()
        if (self._original_selected.get("revision") != 14
                or self._original_selected.get("selected_native_head") != SELECTED_HEAD
                or self._original_selected.get("financial_authority") is not False):
            raise ValueError("R15_ACTIVATION_SELECTED_RELEASE_NOT_FINANCIALLY_QUALIFIED")
        self._qd, self._perp = digest(qd), digest(perp)
        self._original_qd, self._original_perp = deepcopy(qd), deepcopy(perp)
        roster, original_selector = writer_roster(qd, perp, release_digest=ARTIFACT)
        if (original_selector != self._original_selected or len(roster) != 12
                or len(set(roster.values())) != 1):
            raise ValueError("R15_ACTIVATION_EXACT_ONE_PROCESS_BOTH_WRITER_ROSTERS_REQUIRED")
        self._only_writer = next(iter(set(roster.values())))
        self._native_root_snapshot = inspect_two_lane_native_roots()
        self._native_root_binding = require_exact_r15_preinception_roots(
            qd, perp, self._native_root_snapshot)
        self._verified = False
        self.verify_still_running()
        self._verified = True

    def verify_still_running(self):
        if (self.child.closed or self.child.job != self.job
                or self.child.process != self.process
                or self.child.api is not self.api
                or selected_code() != self._original_selected):
            raise ValueError("R15_ACTIVATION_OWNED_JOB_OR_RELEASE_CHANGED")
        k = self.api.kernel32
        k.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        k.WaitForSingleObject.restype = wintypes.DWORD
        k.IsProcessInJob.argtypes = [
            wintypes.HANDLE, wintypes.HANDLE, ctypes.POINTER(wintypes.BOOL)]
        k.IsProcessInJob.restype = wintypes.BOOL
        k.GetProcessId.argtypes = [wintypes.HANDLE]
        k.GetProcessId.restype = wintypes.DWORD
        if k.WaitForSingleObject(self.process, 0) != WAIT_TIMEOUT:
            raise ValueError("R15_ACTIVATION_OWNED_WORKER_EXITED")
        contained = wintypes.BOOL()
        if not k.IsProcessInJob(self.process, self.job, ctypes.byref(contained)):
            raise ValueError("R15_ACTIVATION_JOB_MEMBERSHIP_UNAVAILABLE")
        if not contained.value or self.api.active_processes(self.job) != 1:
            raise ValueError("R15_ACTIVATION_EXACT_ONE_WORKER_IN_OWNED_JOB_REQUIRED")
        limits = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
        if not k.QueryInformationJobObject(
                self.job, JOB_OBJECT_EXTENDED_LIMIT_INFORMATION_CLASS,
                ctypes.byref(limits), ctypes.sizeof(limits), None):
            raise ValueError("R15_ACTIVATION_JOB_TERMINATION_POLICY_UNAVAILABLE")
        if not (limits.BasicLimitInformation.LimitFlags &
                JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE):
            raise ValueError("R15_ACTIVATION_OWNED_JOB_KILL_ON_CLOSE_MISSING")
        pid, created, image = self._only_writer
        observed = _windows_handle_identity(self.process)
        if (int(k.GetProcessId(self.process)) != pid
                or observed["creation_filetime"] != created
                or ntpath.normcase(ntpath.normpath(observed["image"])) != image
                or image != ntpath.normcase(str(RELEASE / "python/python.exe"))):
            raise ValueError("R15_ACTIVATION_OWNED_WORKER_INCARCATION_CHANGED")
        roots = inspect_two_lane_native_roots()
        if (roots != self._native_root_snapshot
                or require_exact_r15_preinception_roots(
                    self._original_qd, self._original_perp, roots)
                   != self._native_root_binding):
            raise ValueError("R15_ACTIVATION_NATIVE_ROOTS_CHANGED_DURING_OWNED_JOB")
        return True

    def require_exact_roster(self, *, qd, perp):
        if (digest(qd) != self._qd or digest(perp) != self._perp):
            raise ValueError("R15_ACTIVATION_OWNED_JOB_ENROLLMENT_DRIFT")
        self.verify_still_running()
        return True

    def nonfinancial_handoff_readback(self):
        self.verify_still_running()
        return {
            "schema": SCHEMA,
            "selected_native_head": SELECTED_HEAD,
            "owned_job_kill_on_close_verified": True,
            "retained_job_has_one_live_selected_r15_worker": True,
            "both_native_writer_rosters_match_same_job_worker": True,
            "writer_roles_examined": 12,
            "genuine_activation_or_owner_lease_issued": False,
            "native_financial_inception_accepted": False,
            "paper_start_authorized": False,
            "live_trading_authorized": False,
        }
