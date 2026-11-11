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

SCHEMA = "ATLAS_R15_RETAINED_OWNED_JOB_BOTH_FINANCIAL_WRITER_ROSTERS_V1"
WAIT_TIMEOUT = 258


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
        roster, original_selector = writer_roster(qd, perp, release_digest=ARTIFACT)
        if (original_selector != self._original_selected or len(roster) != 12
                or len(set(roster.values())) != 1):
            raise ValueError("R15_ACTIVATION_EXACT_ONE_PROCESS_BOTH_WRITER_ROSTERS_REQUIRED")
        self._only_writer = next(iter(set(roster.values())))
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
