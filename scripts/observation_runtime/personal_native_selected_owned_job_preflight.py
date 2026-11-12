"""Version-safe selected native successor: original Job/PROCESS pre-financial owner.

Future installed PAPER authority prerequisite, NOT the financial lease issuer.
Only a live in-process ContainedChild's ORIGINAL Windows Job and PROCESS
handles are accepted. Never reopen or adopt a writer PID from JSON. Require
the same installed selected Python source, selected release digest, 5+7
structural writer identities and all 12 pre-inception empty native roots.

No process launch, provider, financial inception, Stop flatness, order, or
activation publisher is reachable through this module. Native selection,
operator, clock, provider rights and ledger/Stop remain separate gates.
"""
from __future__ import annotations

import ctypes
import ntpath
import os
from copy import deepcopy
from ctypes import wintypes
from pathlib import Path

from app.services.paper_financial_replay import digest
from app.services.perp_operational_contract import (
    WRITERS as HL_WRITERS,
)
from app.services.perp_operational_contract import (
    validate_enrollment as validate_hl,
)
from app.services.quality_dips_autonomous_enrollment import (
    WRITERS as QD_WRITERS,
)
from app.services.quality_dips_autonomous_enrollment import (
    validate_enrollment as validate_qd,
)

from scripts.observation_runtime.personal_existing_native_resource_evidence import (
    inspect_two_lane_native_roots,
)
from scripts.observation_runtime.personal_native_financial_release_origin import (
    require_selected_native_origin,
)
from scripts.observation_runtime.personal_native_job import ContainedChild
from scripts.observation_runtime.personal_native_windows_api import (
    JOB_OBJECT_EXTENDED_LIMIT_INFORMATION_CLASS,
    JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE,
    JOBOBJECT_EXTENDED_LIMIT_INFORMATION,
    WindowsJobAPI,
)
from scripts.observation_runtime.personal_native_writer_lifetime import _identity
from scripts.observation_runtime.personal_r15_owned_job_activation import (
    require_exact_r15_populated_root_identities,
    require_exact_r15_preinception_roots,
)
from scripts.observation_runtime.personal_version_safe_release_clock import (
    require_native_version_safe_clock_source,
)

SCHEMA = "ATLAS_SELECTED_NATIVE_SUCCESSOR_ORIGINAL_JOB_FINANCIAL_OWNER_PREFLIGHT_V1"
WAIT_TIMEOUT = 258


def validate_selected_two_lane_rosters(qd, perp, *, original_process,
                                       release_digest, image):
    """Pure static roster and provenance validation; never financial admission."""
    if (type(release_digest) is not str or len(release_digest) != 64
            or any(char not in "0123456789abcdef" for char in release_digest)
            or type(image) is not str or not image.startswith("D:\\")
            or ntpath.normpath(image) != image
            or type(original_process) is not dict
            or set(original_process) != {"pid", "creation_filetime", "image"}
            or type(original_process["pid"]) is not int or original_process["pid"] <= 0
            or type(original_process["creation_filetime"]) is not int
            or original_process["creation_filetime"] <= 0
            or type(original_process["image"]) is not str
            or ntpath.normcase(ntpath.normpath(original_process["image"]))
               != ntpath.normcase(image)):
        raise ValueError("SELECTED_OWNER_EXACT_ORIGINAL_PROCESS_AND_RELEASE_REQUIRED")
    qd = validate_qd(qd)
    perp = validate_hl(perp)
    if (qd["release_digest"] != release_digest
            or perp["release_digest"] != release_digest
            or qd["account_id"] == perp["account_id"]
            or qd["epoch"] == perp["epoch"]
            or qd["clock_source"] != perp["clock_source"]
            or qd["acceptance_id"] == perp["acceptance_id"]):
        raise ValueError("SELECTED_OWNER_TWO_DISTINCT_RELEASE_BOUND_ACCOUNTS_REQUIRED")
    expected_process = (
        original_process["pid"], original_process["creation_filetime"],
        ntpath.normcase(image),
    )
    roles = {}
    root_ids = set()
    root_paths = set()
    for lane, enrollment, expected in (
            ("QUALITY_DIPS", qd, QD_WRITERS),
            ("HYPERLIQUID", perp, HL_WRITERS)):
        if set(enrollment["writers"]) != set(expected):
            raise ValueError("SELECTED_OWNER_EXACT_TWELVE_WRITER_ROLES_REQUIRED")
        for resource in enrollment["resources"].values():
            identifier = tuple(resource["native_id"])
            path = ntpath.normcase(ntpath.normpath(resource["path"]))
            if identifier in root_ids or path in root_paths:
                raise ValueError("SELECTED_OWNER_CROSS_ACCOUNT_NATIVE_ROOT_ALIAS")
            root_ids.add(identifier)
            root_paths.add(path)
        for role in expected:
            if _identity(enrollment["writers"][role]) != expected_process:
                raise ValueError("SELECTED_OWNER_FOREIGN_PID_OR_PROCESS_REUSED")
            roles[(lane, role)] = expected_process
    if len(roles) != 12 or len(set(roles.values())) != 1:
        raise ValueError("SELECTED_OWNER_ONE_ORIGINAL_PROCESS_FOR_TWELVE_ROLES")
    return roles, qd, perp


class RetainedSelectedNativeOwnerPreflight:
    """Hold actual selected installed Job and roots; no financial lease method."""

    def __init__(self, *, child, qd, perp, release_digest):
        if (os.name != "nt" or type(child) is not ContainedChild
                or type(child.api) is not WindowsJobAPI
                or child.closed or not child.job or not child.process):
            raise ValueError("SELECTED_OWNER_EXACT_ORIGINAL_JOB_PROCESS_REQUIRED")
        # This call is non-injectable production admission: native selector and
        # installed Python original Windows-handle readback must succeed first.
        origin = require_selected_native_origin(release_digest=release_digest)
        release = origin["selected_code_release"]
        expected_image = str(
            Path("D:/AtlasRuntime/releases") / release / "python/python.exe")
        self.child = child
        self.api = child.api
        self.job = child.job
        self.process = child.process
        self.release_digest = release_digest
        self.origin = deepcopy(origin)
        # Deep installed-original-file readback occurs once at admission.
        # Every subsequent fast owner check still validates the live native
        # selector chain/head, held Job/process handles and all 12 native roots.
        self._selected_head = require_native_version_safe_clock_source(deep=False)
        self.image = expected_image
        self._identity = self._original_process_identity()
        roles, qd, perp = validate_selected_two_lane_rosters(
            qd, perp, original_process=self._identity,
            release_digest=release_digest, image=expected_image)
        self._qd, self._perp = digest(qd), digest(perp)
        self._original_qd, self._original_perp = deepcopy(qd), deepcopy(perp)
        self._roles = roles
        self._roots = inspect_two_lane_native_roots()
        self._native_binding = require_exact_r15_preinception_roots(
            qd, perp, self._roots)
        self._phase = "PREINCEPTION"
        self._initial_cuts = None
        self._initial_bootstraps = None
        self.verify_still_running()

    def _original_process_identity(self):
        # Get identity through the ACTUAL held process HANDLE; never reopen PID.
        from scripts.observation_runtime.atlas_r15_disposable_writer_process_audit import (
            _windows_handle_identity,
        )
        k = self.api.kernel32
        k.GetProcessId.argtypes = [wintypes.HANDLE]
        k.GetProcessId.restype = wintypes.DWORD
        pid = int(k.GetProcessId(self.process))
        raw = _windows_handle_identity(self.process)
        if (pid <= 0 or type(raw.get("creation_filetime")) is not int
                or raw["creation_filetime"] <= 0
                or ntpath.normcase(ntpath.normpath(raw.get("image", "")))
                   != ntpath.normcase(self.image)):
            raise ValueError("SELECTED_OWNER_ORIGINAL_IMAGE_OR_CREATION_CHANGED")
        return {
            "pid": pid, "creation_filetime": raw["creation_filetime"],
            "image": raw["image"],
        }

    def _verify_original_job(self):
        if (self.child.closed or self.child.api is not self.api
                or self.child.job != self.job or self.child.process != self.process
                or require_native_version_safe_clock_source(deep=False)
                   != self._selected_head):
            raise ValueError("SELECTED_OWNER_ORIGINAL_JOB_OR_SELECTION_CHANGED")
        k = self.api.kernel32
        k.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        k.WaitForSingleObject.restype = wintypes.DWORD
        if k.WaitForSingleObject(self.process, 0) != WAIT_TIMEOUT:
            raise ValueError("SELECTED_OWNER_ORIGINAL_PROCESS_EXITED")
        k.IsProcessInJob.argtypes = [
            wintypes.HANDLE, wintypes.HANDLE,
            ctypes.POINTER(wintypes.BOOL),
        ]
        k.IsProcessInJob.restype = wintypes.BOOL
        present = wintypes.BOOL()
        if (not k.IsProcessInJob(
                self.process, self.job, ctypes.byref(present))
                or not present.value or self.api.active_processes(self.job) != 1):
            raise ValueError("SELECTED_OWNER_EXACT_SINGLE_JOB_PROCESS_REQUIRED")
        limits = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
        if not k.QueryInformationJobObject(
                self.job, JOB_OBJECT_EXTENDED_LIMIT_INFORMATION_CLASS,
                ctypes.byref(limits), ctypes.sizeof(limits), None):
            raise ValueError("SELECTED_OWNER_NATIVE_JOB_LIMIT_QUERY_FAILED")
        if not (limits.BasicLimitInformation.LimitFlags
                & JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE):
            raise ValueError("SELECTED_OWNER_KILL_ON_CLOSE_REQUIRED")
        if self._original_process_identity() != self._identity:
            raise ValueError("SELECTED_OWNER_PROCESS_INCARCATION_CHANGED")
        return True

    def verify_still_running(self):
        self._verify_original_job()
        roots = inspect_two_lane_native_roots()
        if self._phase == "PREINCEPTION":
            if (roots != self._roots
                    or require_exact_r15_preinception_roots(
                        self._original_qd, self._original_perp, roots)
                       != self._native_binding):
                raise ValueError("SELECTED_OWNER_ORIGINAL_TWELVE_NATIVE_ROOTS_CHANGED")
        elif self._phase == "INITIAL_READBACK_ONLY":
            if (require_exact_r15_populated_root_identities(
                    self._original_qd, self._original_perp, roots,
                    self._native_binding) != self._native_binding
                    or type(self._initial_cuts) is not tuple
                    or len(self._initial_cuts) != 2):
                raise ValueError("SELECTED_OWNER_INITIAL_NATIVE_CUT_OR_ROOT_DRIFT")
            if (type(self._initial_bootstraps) is not tuple
                    or len(self._initial_bootstraps) != 2):
                raise ValueError("SELECTED_OWNER_INITIAL_PUBLISHERS_NOT_BOUND")
            # Each genuine bootstrap reads its independently ACKNOWLEDGED
            # native publication and reruns FS1/FS3 bound-file validation.
            for bootstrap, (enrollment, current) in zip(
                    self._initial_bootstraps, self._initial_cuts, strict=True):
                if bootstrap.enrollment != enrollment:
                    raise ValueError("SELECTED_OWNER_INITIAL_ENROLLMENT_CHANGED")
                verified = bootstrap.verify_publication()
                if (verified.get("current") != current
                        or verified.get("financial_startup_authorized") is not False):
                    raise ValueError("SELECTED_OWNER_INITIAL_PUBLICATION_DRIFT")
        else:
            # PENDING is deliberately irrevocable within this owner. A partial
            # two-account inception cannot be retried or assumed completed.
            raise ValueError("SELECTED_OWNER_INITIAL_INCEPTION_UNKNOWN_RECONCILIATION_REQUIRED")
        return True

    def observe_verified_initial_inceptions(self, *, qd_bootstrap, hl_bootstrap):
        """Transition empty -> INITIAL readback only, not a financial lease.

        The actual native FS1/FS3 readers independently verify both account
        files, opening cash, zero positions and exact original directory IDs.
        Without an acknowledged real publisher result on BOTH lanes, this
        owner stays in an UNKNOWN state and cannot authorize a retry/start.
        """
        if self._phase != "PREINCEPTION" or self._initial_cuts is not None:
            raise ValueError("SELECTED_OWNER_INCEPTION_REPLAY_REFUSED")
        # Freeze the owner before examining any post-inception files. On any
        # failure, its terminal state is UNKNOWN rather than falsely EMPTY.
        self._phase = "INITIAL_READBACK_PENDING"
        self._verify_original_job()
        from scripts.observation_runtime.personal_paper_inception import (
            NativePersonalInitialReadback,
            PersonalInceptionBootstrap,
            validate_personal_inception,
        )
        if (type(qd_bootstrap) is not PersonalInceptionBootstrap
                or type(hl_bootstrap) is not PersonalInceptionBootstrap
                or qd_bootstrap is hl_bootstrap
                or type(qd_bootstrap.readback) is not NativePersonalInitialReadback
                or type(hl_bootstrap.readback) is not NativePersonalInitialReadback):
            raise ValueError("SELECTED_OWNER_TWO_GENUINE_NATIVE_PUBLISHERS_REQUIRED")
        qd_inception, hl_inception = qd_bootstrap.enrollment, hl_bootstrap.enrollment
        q_lane, q_enroll, _ = validate_personal_inception(qd_inception)
        h_lane, h_enroll, _ = validate_personal_inception(hl_inception)
        if (q_lane != "QUALITY_DIPS" or h_lane != "HYPERLIQUID"
                or digest(q_enroll) != self._qd
                or digest(h_enroll) != self._perp):
            raise ValueError("SELECTED_OWNER_INCEPTION_NOT_ORIGINAL_ACCOUNT_ROSTERS")
        roots = inspect_two_lane_native_roots()
        require_exact_r15_populated_root_identities(
            self._original_qd, self._original_perp, roots, self._native_binding)
        # The ACK comes from each original durable publication store, not a
        # caller-supplied JSON current. Its bootstrap reads genuine native
        # FS1/FS3 bound bytes before returning the acknowledged cut.
        q_verified = qd_bootstrap.verify_publication()
        h_verified = hl_bootstrap.verify_publication()
        if (q_verified.get("financial_startup_authorized") is not False
                or h_verified.get("financial_startup_authorized") is not False):
            raise ValueError("SELECTED_OWNER_ONLY_NONSTARTABLE_INITIAL_PROOFS_ALLOWED")
        self._initial_cuts = (
            (deepcopy(qd_inception), deepcopy(q_verified["current"])),
            (deepcopy(hl_inception), deepcopy(h_verified["current"])),
        )
        self._initial_bootstraps = (qd_bootstrap, hl_bootstrap)
        self._phase = "INITIAL_READBACK_ONLY"
        self.verify_still_running()
        return {
            "schema": "ATLAS_NATIVE_TWO_ACCOUNT_INITIAL_READBACK_HOLD_V1",
            "status": "TWO_INITIAL_NATIVE_ACCOUNTS_OBSERVED_NOT_FINANCIAL_LEASE",
            "both_initial_fs1_fs3_readbacks_verified": True,
            "original_twelve_native_roots_bound": True,
            "financial_writer_lease_issued": False,
            "financial_stop_flatness_accepted": False,
            "paper_start_authorized": False,
            "live_trading_authorized": False,
        }

    def require_exact_roster(self, *, qd, perp):
        if digest(qd) != self._qd or digest(perp) != self._perp:
            raise ValueError("SELECTED_OWNER_ENROLLMENT_CHANGED")
        roles, _, _ = validate_selected_two_lane_rosters(
            qd, perp, original_process=self._identity,
            release_digest=self.release_digest, image=self.image)
        if roles != self._roles:
            raise ValueError("SELECTED_OWNER_ORIGINAL_ROSTER_CHANGED")
        return self.verify_still_running()

    def structural_readback(self):
        self.verify_still_running()
        return {
            "schema": SCHEMA,
            "source_selected_and_installed_verified": True,
            "original_job_process_handles_retained": True,
            "kill_on_close_and_single_process_verified": True,
            "distinct_qd_and_hl_structural_writer_rosters_verified": True,
            "native_twelve_original_roots_preinception_verified":
                self._phase == "PREINCEPTION",
            "native_both_initial_fs1_fs3_readbacks_verified":
                self._phase == "INITIAL_READBACK_ONLY",
            "owner_inception_phase": self._phase,
            "financial_writer_lease_issued": False,
            "operator_activation_accepted": False,
            "financial_clock_lease_accepted": False,
            "market_source_rights_accepted": False,
            "financial_stop_flatness_accepted": False,
            "paper_start_authorized": False,
            "live_trading_authorized": False,
        }
