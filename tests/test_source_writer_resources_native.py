"""Read exact fixture resource handles and process identity; not C1 acceptance."""
import copy
import ctypes
import os
from ctypes import wintypes
from pathlib import Path
from types import SimpleNamespace

import pytest
import test_source_bound_two_lane_native as fixtures
from app.services.paper_financial_replay import digest
from app.services.unified_writer_roster import EXCLUSIONS, ROLES, UnifiedWriterRoster
from perp_order_native_fixture import native
from test_quality_dips_autonomous_runtime_http import owner_module

system=fixtures.system


def test_complete_selected_resource_contract_uses_actual_native_ids_and_birth(system):
    s,pub=system
    stores={
        'QD_DECISION':s.q.writer.runtime.runtime.engine.ledger.path,
        'QD_COORDINATION':s.q.writer.runtime.runtime.engine.ledger.path,
        'QD_SOURCE':s.q.writer.store.output.root,
        'QD_PROJECTION':s.q.writer.store.projection.output.root,
        'QD_REPORT':s.qstop.reports.archive.output.root,
        'QD_RANKING_PUBLICATION':pub.qpub.archive.root,
        'PERP_SOURCE':s.p.store.output.root,'PERP_FUNDING':s.p.store.output.root,'PERP_MARK':s.p.store.output.root,
        'PERP_PROJECTION':s.p.projection.output.root,'PERP_REPORT':s.p.archive.output.root,
        'PERP_ORDERS':s.p.orders.output.root,'PERP_MARKET_PUBLICATION':pub.ppub.archive.root,
        'GLOBAL_CUSTODY':s.journal.output.root,'SESSION_RESERVATION':s.journal.output.root}
    assert set(stores)==set(ROLES)
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.CreateFileW.argtypes=[wintypes.LPCWSTR,wintypes.DWORD,wintypes.DWORD,wintypes.LPVOID,wintypes.DWORD,wintypes.DWORD,wintypes.HANDLE]
    kernel.CreateFileW.restype=wintypes.HANDLE
    kernel.CloseHandle.argtypes=[wintypes.HANDLE]
    def identity(path):
        path=Path(path).absolute()
        assert path.is_relative_to(s.root) or path.is_relative_to(s.qd_root)
        assert all(not p.is_symlink() and not p.is_junction() for p in (path,*path.parents))
        handle=kernel.CreateFileW(str(path),0x80,7,None,3,0x02200000,None)
        if handle==wintypes.HANDLE(-1).value:raise ctypes.WinError(ctypes.get_last_error())
        try:return native.f.native.file_identity(handle)
        finally:kernel.CloseHandle(handle)
    process=owner_module.observe_pid(os.getpid())
    def roles():return {key:{'writer_id':key,'process':owner_module.observe_pid(os.getpid()),'resource':identity(path)} for key,path in stores.items()}
    e={'schema':'ATLAS_UNIFIED_WRITER_RESOURCES_V1','session_id':s.r.grant['session_id'],
       'account_binding':digest({k:digest(w.manifest) for k,w in s.writers.items()}),'writer_binding':s.binding['roster_digest'],
       'roles':roles(),'exclusions':dict.fromkeys(EXCLUSIONS,'EXPLICIT_SYNTHETIC_EXCLUSION_NOT_OPERATIONAL')}
    unknown=[]
    observer=SimpleNamespace(read=lambda expected:{'schema':'ATLAS_UNIFIED_WRITER_OBSERVATION_V1','observed_at':s.clock(),
        'roles':roles(),'unknown_writers':copy.deepcopy(unknown),'active_operations':dict.fromkeys(ROLES,0),'unknown_operations':False})
    authority=SimpleNamespace(verify_enrollment=lambda value,*args:value==e,
        verify_observation=lambda *args:True,verify_drain=lambda *args:True)
    roster=UnifiedWriterRoster(enrollment=e,writers=s.writers,observer=observer,authority=authority,clock=s.clock)
    with roster.lease(s.r.grant,s.writers,s.clock()) as lease:assert lease.check()
    assert roster.drain(s.r.grant,s.writers,s.clock())
    assert roster.owned_roster(s.r.grant,s.writers,s.clock())['processes']==[process]
    unknown.append('SYNTHETIC_UNREGISTERED_WRITER')
    with pytest.raises(ValueError):roster.owned_roster(s.r.grant,s.writers,s.clock())
