"""Original selected Python process self-containment in a native Windows Job.

No child-PID adoption, orders, account writes or launch. This API must be
invoked from inside an already-selected installed native Python financial
owner. No capacity to claim a financial lease without the separate genuine
operator, clock, account and source gates. Job creation is explicitly invoked.

The owner process is put into its own new kill-on-last-close Job *before*
any financial operations. The process exits naturally after durable Stop,
closing the Job and draining its owned children. Closing its Job while it
is still running would terminate this process; no casual close method.
"""
from __future__ import annotations

import ctypes
import os
from ctypes import wintypes


class NativeFinancialReleaseAdmission:
    """Retained full release verification BEFORE fresh financial manifests.

    The original NativePersonalReleaseIdentity keeps every verified native
    file/directory handle. Each use rechecks those bindings, module cohort,
    actual process and exact current native selector. No cached JSON proof,
    financial authority, clock, filesystem publication or process launch.
    """
    def __init__(self, *, release):
        from scripts.observation_runtime.personal_release_identity import NativePersonalReleaseIdentity
        if type(release) is not NativePersonalReleaseIdentity:
            raise ValueError('FINANCIAL_RELEASE_RETAINED_NATIVE_IDENTITY_REQUIRED')
        self.release=release
        self._release=release
        self._digest=release.artifact_digest
        self._head=None
        self._revoked=False
        self.verify(release_digest=self._digest)

    def verify(self, *, release_digest):
        from pathlib import Path
        import sys
        from scripts.observation_runtime.personal_native_financial_release_origin import validate_origin
        from scripts.observation_runtime.personal_version_safe_release_clock import (
            CLOCK_RELATIVE, SELECTOR_NATIVE, admit_version_safe_clock_source,
        )
        from scripts.release_selection_store import NativeSelectionStore
        if self._revoked or self.release is not self._release or release_digest!=self._digest:
            self._revoked=True
            raise ValueError('FINANCIAL_RELEASE_RETAINED_ADMISSION_REVOKED')
        try:
            held=self.release.verify(release_digest=release_digest)
            module=Path(__file__).absolute().with_name('personal_activation_commission.py')
            if module.parents[2]!=self.release.root:
                raise ValueError('FINANCIAL_RELEASE_RETAINED_SOURCE_COHORT_CONFLICT')
            store=NativeSelectionStore(root=r'D:\AtlasRuntime\selection',native_root=list(SELECTOR_NATIVE))
            try:
                with store.locked():
                    head,spec=admit_version_safe_clock_source(
                        source_file=self.release.root/CLOCK_RELATIVE,records=store.records())
                    origin=validate_origin(module_path=module,executable=Path(sys.executable),
                                           selected=spec,release_digest=release_digest)
                if (held['source_commit']!=origin['selected_code_release']
                        or self._head is not None and head!=self._head):
                    raise ValueError('FINANCIAL_RELEASE_RETAINED_SELECTION_CHANGED')
                self._head=head
                return origin
            finally:store.close()
        except BaseException:
            self._revoked=True
            raise

from scripts.observation_runtime.atlas_r15_disposable_writer_process_audit import (
    _windows_handle_identity,
)
from scripts.observation_runtime.personal_native_job import ContainedChild
from scripts.observation_runtime.personal_native_windows_api import (
    JOB_OBJECT_EXTENDED_LIMIT_INFORMATION_CLASS,
    JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE,
    JOBOBJECT_EXTENDED_LIMIT_INFORMATION,
    WindowsJobAPI,
)
from scripts.observation_runtime.quality_dips_read_service import observe_self

DUPLICATE_SAME_ACCESS = 0x00000002
WAIT_TIMEOUT = 258


class NativeOriginalSelfJob:
    """Own Job and own original PROCESS handle; no arbitrary-process handles."""

    def __init__(self, api, child, identity):
        if (type(api) is not WindowsJobAPI or type(child) is not ContainedChild
                or child.api is not api or not child.job or not child.process
                or type(identity) is not dict or child.closed):
            raise ValueError("ORIGINAL_SELF_JOB_EXACT_NATIVE_HANDLES_REQUIRED")
        self.api, self.child, self.identity = api, child, dict(identity)
        self._pid = os.getpid()
        self.verify()

    def verify(self):
        if (os.name != "nt" or os.getpid() != self._pid
                or self.child.closed or self.child.api is not self.api
                or not self.child.job or not self.child.process
                or observe_self() != self.identity):
            raise ValueError("ORIGINAL_SELF_JOB_PROCESS_BINDING_CHANGED")
        k = self.api.kernel32
        k.GetProcessId.argtypes = [wintypes.HANDLE]
        k.GetProcessId.restype = wintypes.DWORD
        k.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        k.WaitForSingleObject.restype = wintypes.DWORD
        k.IsProcessInJob.argtypes = [
            wintypes.HANDLE, wintypes.HANDLE, ctypes.POINTER(wintypes.BOOL)]
        k.IsProcessInJob.restype = wintypes.BOOL
        present = wintypes.BOOL()
        limits = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
        native_identity = _windows_handle_identity(self.child.process)
        if (int(k.GetProcessId(self.child.process)) != self._pid
                or native_identity.get('creation_filetime') != self.identity['creation_filetime']
                or native_identity.get('image', '').casefold() != self.identity['image'].casefold()
                or k.WaitForSingleObject(self.child.process, 0) != WAIT_TIMEOUT
                or not k.IsProcessInJob(
                    self.child.process, self.child.job, ctypes.byref(present))
                or not present.value
                or self.api.active_processes(self.child.job) != 1
                or not k.QueryInformationJobObject(
                    self.child.job, JOB_OBJECT_EXTENDED_LIMIT_INFORMATION_CLASS,
                    ctypes.byref(limits), ctypes.sizeof(limits), None)
                or not limits.BasicLimitInformation.LimitFlags
                   & JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE):
            raise ValueError("ORIGINAL_SELF_JOB_NATIVE_KILL_ON_CLOSE_NOT_HELD")
        return True

    def selected_two_account_owner(self, *, qd, perp, release_digest,
                                   release_admission=None, successor_root_scope=None):
        """Reuses genuine native selected-finance owner admission, never fake."""
        from scripts.observation_runtime.personal_native_financial_release_origin import (
            require_selected_native_origin,
        )
        from scripts.observation_runtime.personal_native_selected_owned_job_preflight import (
            RetainedSelectedNativeOwnerPreflight,
        )

        self.verify()
        if release_admission is None:
            require_selected_native_origin(release_digest=release_digest)
        elif (type(release_admission) is not NativeFinancialReleaseAdmission
                or release_admission.verify(release_digest=release_digest) is None):
            raise ValueError('ORIGINAL_SELF_JOB_RETAINED_RELEASE_REQUIRED')
        owner = RetainedSelectedNativeOwnerPreflight(
            child=self.child, qd=qd, perp=perp, release_digest=release_digest,
            release_admission=release_admission,
            successor_root_scope=successor_root_scope)
        if (owner._identity != self.identity
                or owner.verify_still_running() is not True):
            raise ValueError("ORIGINAL_SELF_JOB_SELECTED_WRITER_PROOF_REFUSED")
        return owner

    def selected_readonly_recovery_owner(self, *, readback):
        """Fresh self-owned Job; preserve historical writers, never adopt them."""
        from scripts.observation_runtime.personal_owner_continuity_v2 import (
            NativeRecoveredReadOnlyOwner,
        )
        self.verify()
        return NativeRecoveredReadOnlyOwner(original_self_job=self, readback=readback)

    def readonly_recovery_activation_guard(self, *, qd, perp, release_digest, release_admission=None):
        """Identity-only READ approval guard; no writer/financial authority."""
        from scripts.observation_runtime.personal_owner_continuity_v2 import NativeReadOnlyRecoveryActivationGuard
        self.verify()
        return NativeReadOnlyRecoveryActivationGuard(job=self,qd=qd,perp=perp,
            release_digest=release_digest,release_admission=release_admission)


def create_original_self_job():
    """Purely native containment, NOT an origin, issuer, PAPER or account grant.

    Must run in a dedicated worker: closing its own kill-on-close Job kills
    itself. An ordinary caller must never create it in the UI/command shell.
    """
    if os.name != "nt":
        raise ValueError("ORIGINAL_SELF_JOB_WINDOWS_ONLY")
    api = WindowsJobAPI()
    k = api.kernel32
    k.GetCurrentProcess.argtypes = []
    k.GetCurrentProcess.restype = wintypes.HANDLE
    k.DuplicateHandle.argtypes = [
        wintypes.HANDLE, wintypes.HANDLE, wintypes.HANDLE,
        ctypes.POINTER(wintypes.HANDLE), wintypes.DWORD,
        wintypes.BOOL, wintypes.DWORD,
    ]
    k.DuplicateHandle.restype = wintypes.BOOL
    k.IsProcessInJob.argtypes = [
        wintypes.HANDLE, wintypes.HANDLE, ctypes.POINTER(wintypes.BOOL)]
    k.IsProcessInJob.restype = wintypes.BOOL
    pseudo = k.GetCurrentProcess()
    present = wintypes.BOOL()
    if not k.IsProcessInJob(pseudo, None, ctypes.byref(present)):
        raise ValueError("ORIGINAL_SELF_JOB_PREASSIGN_QUERY_REQUIRED")
    if present.value:
        raise ValueError("ORIGINAL_SELF_JOB_ALREADY_IN_ANOTHER_JOB_REFUSED")
    process_handle = wintypes.HANDLE()
    if not k.DuplicateHandle(
            pseudo, pseudo, pseudo, ctypes.byref(process_handle),
            0, False, DUPLICATE_SAME_ACCESS):
        raise ValueError("ORIGINAL_SELF_JOB_DUPLICATE_OWN_HANDLE_REQUIRED")
    process = process_handle.value
    job = None
    assigned = False
    try:
        job = api.create_job()
        api.configure_kill_on_close(job)
        # Only THIS process; never adopt a caller-supplied PID or open foreign
        # writer handles. All financial actions remain prohibited until a
        # separate installed-source/Job/native-clock/operator issuer admits.
        api.assign_child(job, process)
        assigned = True
        child = ContainedChild(api, job, process)
        return NativeOriginalSelfJob(api, child, observe_self())
    except BaseException:
        # After successful self-assignment closing the LAST Job handle would
        # kill the financial worker synchronously, bypassing orderly error
        # reporting. Preserve handles until its process exits instead.
        if not assigned:
            if job:
                api.close_handle(job)
            api.close_handle(process)
        raise
