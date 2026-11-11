"""Retain real Windows writer PROCESS HANDLES before native PAPER activation.

This is a liveness and anti-PID-reuse precondition, NOT a financial writer lease.
Caller must independently accept account/provider/clock/financial authority.
No process creation, adoption, termination, account files or trading.
"""
import ctypes
import ntpath
import os
from contextlib import ExitStack, contextmanager
from ctypes import wintypes

from app.services.quality_dips_autonomous_enrollment import WRITERS as QD_WRITERS
from app.services.perp_operational_contract import WRITERS as PERP_WRITERS

QUERY_LIMITED_INFORMATION = 0x1000
SYNCHRONIZE = 0x00100000
WAIT_TIMEOUT = 258


def _identity(value):
    if (type(value) is not dict
            or set(value) != {'schema','pid','creation_filetime','image'}
            or value['schema'] != 'QD_OP_PROCESS_ID_V1'
            or type(value['pid']) is not int or value['pid'] <= 0
            or type(value['creation_filetime']) is not int
            or value['creation_filetime'] <= 0
            or type(value['image']) is not str
            or not value['image'].startswith('D:\\')
            or ntpath.normpath(value['image']) != value['image']
            or len(value['image']) > 1024
            or any(c in value['image'][2:] for c in (':','%','\x00','/'))):
        raise ValueError('PERSONAL_ACTIVATION_EXACT_REAL_WRITER_IDENTITY_REQUIRED')
    return (value['pid'],value['creation_filetime'],
            ntpath.normcase(value['image']))


def writer_roster(qd,perp,*,release_digest):
    if (type(qd) is not dict or type(perp) is not dict
            or qd.get('release_digest') != release_digest
            or perp.get('release_digest') != release_digest
            or type(qd.get('writers')) is not dict
            or type(perp.get('writers')) is not dict
            or set(qd['writers']) != set(QD_WRITERS)
            or set(perp['writers']) != set(PERP_WRITERS)):
        raise ValueError('PERSONAL_ACTIVATION_BOTH_WRITER_ROSTERS_REQUIRED')
    roster={}
    by_pid={}
    for lane,roles,enrollment in (
            ('QUALITY_DIPS',QD_WRITERS,qd),('HYPERLIQUID',PERP_WRITERS,perp)):
        for role in roles:
            key=_identity(enrollment['writers'][role])
            previous=by_pid.setdefault(key[0],key)
            if previous != key:
                raise ValueError('PERSONAL_ACTIVATION_REUSED_PID_OR_WRITER_IMAGE')
            roster[(lane,role)]=key
    unique=set(roster.values())
    if not 1 <= len(unique) <= 12:
        raise ValueError('PERSONAL_ACTIVATION_EXACT_PROCESS_COUNT_REQUIRED')
    from scripts.observation_runtime.atlas_r15_paper_offline_commissioning import (
        ARTIFACT,RELEASE,SELECTED_HEAD,selected_code,
    )
    selection=None
    if release_digest == ARTIFACT:
        selection=selected_code()
        if (selection.get('revision') != 14
                or selection.get('selected_native_head') != SELECTED_HEAD
                or selection.get('financial_authority') is not False):
            raise ValueError('PERSONAL_ACTIVATION_SELECTED_R15_UNVERIFIED')
        expected=ntpath.normcase(str(RELEASE/'python/python.exe'))
        if any(key[2] != expected for key in unique):
            raise ValueError('PERSONAL_ACTIVATION_SELECTED_R15_EXECUTABLE_MISMATCH')
    return roster,selection


class WindowsRetainedWriter:
    def __init__(self,identity):
        if os.name != 'nt':
            raise ValueError('PERSONAL_ACTIVATION_WRITER_WINDOWS_ONLY')
        self.identity=identity
        self.kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        k=self.kernel
        k.OpenProcess.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD]
        k.OpenProcess.restype=wintypes.HANDLE
        k.CloseHandle.argtypes=[wintypes.HANDLE]
        k.CloseHandle.restype=wintypes.BOOL
        k.WaitForSingleObject.argtypes=[wintypes.HANDLE,wintypes.DWORD]
        k.WaitForSingleObject.restype=wintypes.DWORD
        k.GetProcessId.argtypes=[wintypes.HANDLE]
        k.GetProcessId.restype=wintypes.DWORD
        self.handle=k.OpenProcess(QUERY_LIMITED_INFORMATION|SYNCHRONIZE,
                                  False,identity[0])
        if not self.handle:
            raise ValueError('PERSONAL_ACTIVATION_ACTUAL_PROCESS_HANDLE_UNAVAILABLE')
        try:self.check()
        except BaseException:
            self.close()
            raise

    def check(self):
        if not self.handle:
            raise ValueError('PERSONAL_ACTIVATION_PROCESS_HANDLE_EXPIRED')
        k=self.kernel
        if k.WaitForSingleObject(self.handle,0)!=WAIT_TIMEOUT:
            raise ValueError('PERSONAL_ACTIVATION_WRITER_PROCESS_EXITED')
        if k.GetProcessId(self.handle)!=self.identity[0]:
            raise ValueError('PERSONAL_ACTIVATION_PROCESS_HANDLE_PID_CHANGED')
        from scripts.observation_runtime.atlas_r15_disposable_writer_process_audit import (
            _windows_handle_identity,
        )
        native=_windows_handle_identity(self.handle)
        if (native['creation_filetime'] != self.identity[1]
                or ntpath.normcase(ntpath.normpath(native['image'])) != self.identity[2]):
            raise ValueError('PERSONAL_ACTIVATION_PROCESS_INCARCATION_OR_IMAGE_CHANGED')
        return True

    def close(self):
        if self.handle:
            self.kernel.CloseHandle(self.handle)
            self.handle=None


@contextmanager
def retain_live_enrollment_writers(qd,perp,*,release_digest):
    """Hold genuine Windows PROCESS HANDLES through the publisher call."""
    roster,selection=writer_roster(qd,perp,release_digest=release_digest)
    handles={}
    with ExitStack() as stack:
        for key in sorted(set(roster.values())):
            lease=WindowsRetainedWriter(key)
            stack.callback(lease.close)
            handles[key]=lease

        class Lease:
            def verify_still_running(self):
                if any(h.check() is not True for h in handles.values()):
                    raise ValueError('PERSONAL_ACTIVATION_NATIVE_PROCESS_LIFETIME_REFUSED')
                if selection is not None:
                    from scripts.observation_runtime.atlas_r15_paper_offline_commissioning import (
                        selected_code,
                    )
                    if selected_code()!=selection:
                        raise ValueError('PERSONAL_ACTIVATION_R15_SELECTOR_CHANGED')
                return True

        bound=Lease()
        bound.verify_still_running()
        yield bound
        bound.verify_still_running()
