"""Retain the EXACT selected R16 original Windows Job and PROCESS handles.

This in-process observation-only admission binds the five QD and seven
Hyperliquid structural native writer roster roles to one original R16 process
while holding the same owned kill-on-close Windows Job. It also binds all
twelve original pre-inception EMPTY native resource directory identities.

This is NOT a financial writer lease. Native account inception, current
operator authority, source rights, financial clock and PAPER runtime remain
independent unaccepted gates. Never adopt an external PID or serialized Job.
"""
from __future__ import annotations

import ctypes
import ntpath
import os
from copy import deepcopy
from ctypes import wintypes

from app.services.paper_financial_replay import digest
from app.services.quality_dips_autonomous_enrollment import (
    WRITERS as QD_WRITERS, validate_enrollment as validate_qd,
)
from app.services.perp_operational_contract import (
    WRITERS as HL_WRITERS, validate_enrollment as validate_hl,
)
from scripts.observation_runtime.atlas_r16_selected_code_readback import (
    ARTIFACT_DIGEST, RELEASE, R16_HEAD, selected_code,
)
from scripts.observation_runtime.atlas_r16_parked_writer_owner import (
    _exact_r16_process,
)
from scripts.observation_runtime.personal_existing_native_resource_evidence import (
    inspect_two_lane_native_roots,
)
from scripts.observation_runtime.personal_native_writer_lifetime import _identity
from scripts.observation_runtime.personal_native_job import ContainedChild
from scripts.observation_runtime.personal_native_windows_api import (
    JOB_OBJECT_EXTENDED_LIMIT_INFORMATION_CLASS,
    JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE,
    JOBOBJECT_EXTENDED_LIMIT_INFORMATION,
    WindowsJobAPI,
)
from scripts.observation_runtime.personal_r15_owned_job_activation import (
    require_exact_r15_preinception_roots,
)

SCHEMA = "ATLAS_R16_RETAINED_ORIGINAL_JOB_TWELVE_STRUCTURAL_WRITER_ROLES_V1"
WAIT_TIMEOUT = 258


def validate_r16_two_lane_rosters(qd, perp, *, observed):
    """Validate entire native structural rosters without manufacturing grants."""
    qd = validate_qd(qd)
    perp = validate_hl(perp)
    if (qd["release_digest"] != ARTIFACT_DIGEST
            or perp["release_digest"] != ARTIFACT_DIGEST
            or qd["account_id"] == perp["account_id"]
            or qd["epoch"] == perp["epoch"]
            or qd["clock_source"] != perp["clock_source"]
            or qd["acceptance_id"] == perp["acceptance_id"]):
        raise ValueError("R16_RETAINED_JOB_TWO_DISTINCT_RELEASE_BOUND_ENROLLMENTS_REQUIRED")
    if type(observed) is not dict or set(observed) != {
            "pid", "creation_filetime", "image"}:
        raise ValueError("R16_RETAINED_JOB_ORIGINAL_PROCESS_ID_REQUIRED")
    canonical = (
        observed["pid"], observed["creation_filetime"],
        ntpath.normcase(ntpath.normpath(observed["image"])),
    )
    expected_image = ntpath.normcase(str(RELEASE / "python/python.exe"))
    if canonical[2] != expected_image:
        raise ValueError("R16_RETAINED_JOB_EXACT_SELECTED_IMAGE_REQUIRED")
    roles = {}
    for lane, enrollment, expected in (
            ("QUALITY_DIPS", qd, QD_WRITERS),
            ("HYPERLIQUID", perp, HL_WRITERS)):
        if set(enrollment["writers"]) != set(expected):
            raise ValueError("R16_RETAINED_JOB_EXACT_WRITER_ROLES_REQUIRED")
        for role in expected:
            candidate = _identity(enrollment["writers"][role])
            if candidate != canonical:
                raise ValueError("R16_RETAINED_JOB_ORIGINAL_PROCESS_ROSTER_MISMATCH")
            roles[(lane, role)] = candidate
    if len(roles) != 12 or len(set(roles.values())) != 1:
        raise ValueError("R16_RETAINED_JOB_SAME_PROCESS_ALL_TWELVE_ROLES_REQUIRED")
    return roles, qd, perp


class RetainedSelectedR16OwnerJob:
    """In-process original Job+PROCESS handle ownership, NO finance grant."""

    def __init__(self, *, child, qd, perp):
        if (os.name != "nt" or type(child) is not ContainedChild
                or type(child.api) is not WindowsJobAPI
                or child.closed or not child.job or not child.process):
            raise ValueError("R16_RETAINED_JOB_ORIGINAL_CONTAINED_CHILD_REQUIRED")
        self.child = child
        self.api = child.api
        self.job = child.job
        self.process = child.process
        self._selected = selected_code()
        if (self._selected.get("selected_revision") != 15
                or self._selected.get("selected_native_head") != R16_HEAD
                or self._selected.get("financial_writer_operational_accepted") is not False
                or self._selected.get("paper_start_authorized") is not False):
            raise ValueError("R16_RETAINED_JOB_EXACT_SELECTED_CODE_REFUSED")
        self._identity = _exact_r16_process(self.api, self.process)
        roles, accepted_qd, accepted_perp = validate_r16_two_lane_rosters(
            qd, perp, observed=self._identity)
        self._qd = digest(accepted_qd)
        self._perp = digest(accepted_perp)
        self._original_qd = deepcopy(accepted_qd)
        self._original_perp = deepcopy(accepted_perp)
        self._role_bindings = roles
        self._native_roots = inspect_two_lane_native_roots()
        self._native_binding = require_exact_r15_preinception_roots(
            accepted_qd, accepted_perp, self._native_roots)
        self.verify_still_running()

    def _require_original_owned_job(self):
        if (self.child.closed or self.child.api is not self.api
                or self.child.job != self.job
                or self.child.process != self.process
                or selected_code() != self._selected):
            raise ValueError("R16_RETAINED_JOB_ORIGINAL_HANDLES_OR_RELEASE_CHANGED")
        k = self.api.kernel32
        k.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        k.WaitForSingleObject.restype = wintypes.DWORD
        if k.WaitForSingleObject(self.process, 0) != WAIT_TIMEOUT:
            raise ValueError("R16_RETAINED_JOB_ORIGINAL_PROCESS_EXITED")
        k.IsProcessInJob.argtypes = [
            wintypes.HANDLE, wintypes.HANDLE,
            ctypes.POINTER(wintypes.BOOL),
        ]
        k.IsProcessInJob.restype = wintypes.BOOL
        present = wintypes.BOOL()
        if (not k.IsProcessInJob(
                self.process, self.job, ctypes.byref(present))
                or not present.value
                or self.api.active_processes(self.job) != 1):
            raise ValueError("R16_RETAINED_JOB_ORIGINAL_SINGLE_PROCESS_MEMBERSHIP_REFUSED")
        limits = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
        if not k.QueryInformationJobObject(
                self.job, JOB_OBJECT_EXTENDED_LIMIT_INFORMATION_CLASS,
                ctypes.byref(limits), ctypes.sizeof(limits), None):
            raise ValueError("R16_RETAINED_JOB_ORIGINAL_KILL_ON_CLOSE_QUERY_REFUSED")
        if not (limits.BasicLimitInformation.LimitFlags
                & JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE):
            raise ValueError("R16_RETAINED_JOB_KILL_ON_CLOSE_NOT_SET")
        if _exact_r16_process(
                self.api, self.process,
                expected_pid=self._identity["pid"]) != self._identity:
            raise ValueError("R16_RETAINED_JOB_ORIGINAL_PROCESS_INCARCATION_CHANGED")
        return True

    def verify_still_running(self):
        self._require_original_owned_job()
        roots = inspect_two_lane_native_roots()
        if (roots != self._native_roots
                or require_exact_r15_preinception_roots(
                    self._original_qd, self._original_perp, roots)
                   != self._native_binding):
            raise ValueError("R16_RETAINED_JOB_ORIGINAL_TWELVE_ROOTS_CHANGED")
        return True

    def require_exact_roster(self, *, qd, perp):
        if (digest(qd) != self._qd or digest(perp) != self._perp):
            raise ValueError("R16_RETAINED_JOB_ENROLLMENT_DIGEST_DRIFT")
        roles, _, _ = validate_r16_two_lane_rosters(
            qd, perp, observed=self._identity)
        if roles != self._role_bindings:
            raise ValueError("R16_RETAINED_JOB_ORIGINAL_ROSTER_CHANGED")
        return self.verify_still_running()

    def nonfinancial_handoff_readback(self):
        self.verify_still_running()
        return {
            "schema": SCHEMA,
            "selected_native_head": R16_HEAD,
            "original_owned_job_kill_on_close_verified": True,
            "one_live_original_selected_r16_process": True,
            "twelve_structural_writer_roles_bound_to_same_process": True,
            "twelve_original_empty_native_directory_identities_verified": True,
            "quality_dips_structural_roles": 5,
            "hyperliquid_structural_roles": 7,
            "financial_writer_lease_issued": False,
            "operator_financial_authority_accepted": False,
            "financial_account_inception_accepted": False,
            "provider_source_rights_accepted": False,
            "financial_clock_lease_accepted": False,
            "paper_start_authorized": False,
            "live_trading_authorized": False,
        }
