"""Two actual native strategies then exact retained test-child EOF; never kill.

Native lifetime evidence is real; roster acceptance is synthetic, not C1 approval.
"""
import asyncio
import ctypes
import json
import subprocess
import sys
from contextlib import closing
from ctypes import wintypes
from http.client import HTTPConnection
from threading import Thread
from urllib.parse import urlsplit

import pytest
import test_unified_actual_native_lanes as native_fixtures
from app.services.paper_financial_replay import digest
from app.services.unified_paper_runtime import UnifiedControlStopBridge
from test_quality_dips_autonomous_runtime_http import owner_module
from test_unified_actual_http import host
from test_unified_actual_native_lanes import cycle

system = native_fixtures.system


@pytest.mark.parametrize('damage', ['none', 'foreign', 'account', 'exit-ack', 'authority'])
def test_final_financial_drain_then_exact_owned_native_child_close(system, damage):
    s = system
    asyncio.run(cycle(s))
    children = [subprocess.Popen([sys._base_executable, '-B', '-c',
        'import sys;print("ready",flush=True);sys.stdin.readline()'], stdin=subprocess.PIPE,
        stdout=subprocess.PIPE, text=True, creationflags=subprocess.CREATE_NO_WINDOW) for _ in range(2)]
    try:
        assert all(p.stdout.readline().strip() == 'ready' for p in children)
        identities = [owner_module.observe_pid(p.pid) for p in children]
        assert all(owner_module.observe_handle(int(p._handle)) == row['created']
                   for p,row in zip(children,identities,strict=True))
        roster = {'schema':'ATLAS_UNIFIED_OWNED_ROSTER_V1', 'session_id':s.r.grant['session_id'],
            'processes':identities, 'writer_binding':s.binding['roster_digest'],
            'account_binding':digest({k:digest(w.manifest) for k,w in s.writers.items()})}
        calls=[]
        class Close:
            def close_verified(self, supplied):
                assert supplied == roster and s.journal.snapshot()['state']['finalized'] is not None
                observed=[]
                def competing_thread():
                    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
                    kernel.WaitForSingleObject.argtypes=[wintypes.HANDLE,wintypes.DWORD]
                    kernel.ReleaseMutex.argtypes=[wintypes.HANDLE]
                    code=kernel.WaitForSingleObject(s.journal.mutex,0)
                    if code==0: kernel.ReleaseMutex(s.journal.mutex)
                    observed.append(code)
                probe=Thread(target=competing_thread);probe.start();probe.join(2)
                assert observed==[258]  # Actual global writer mutex remains held through closure.
                for p,row in zip(children,identities,strict=True):
                    if p.poll() is None:
                        if owner_module.observe_pid(p.pid) != row: raise ValueError('FOREIGN_CHILD')
                        p.stdin.close();p.wait(timeout=12)
                    assert p.returncode == 0 and owner_module.observe_handle(int(p._handle)) == row['created']
                calls.append(supplied)
                return True
            def verify_exit(self, supplied):
                return damage != 'exit-ack' and supplied == roster and all(p.poll() == 0 for p in children)
        closer=Close()
        s.ownership.owned_roster=lambda *args: ({**roster,'writer_binding':'foreign'} if damage=='foreign' else
            {**roster,'account_binding':'foreign'} if damage=='account' else roster)
        s.a.verify_owned_shutdown=lambda context,cap,components: damage!='authority' and cap is closer and context['roster']==roster
        bridge=UnifiedControlStopBridge(s.r,owned_close=closer)
        if damage == 'none':
            h,token=host(s,owned_close=closer)
            ready=h.start()
            try:
                origin=f"http://127.0.0.1:{urlsplit(ready['url']).port}"
                with closing(HTTPConnection('127.0.0.1',urlsplit(ready['url']).port,timeout=35)) as connection:
                    connection.request('POST','/_atlas/control/stop',body=json.dumps({'mode':'SHUTDOWN_FLATTEN'}),
                        headers={'Origin':origin,'X-Atlas-Control':token,'Content-Type':'application/json'})
                    response=connection.getresponse()
                    assert response.status==200
                    result=json.loads(response.read())['outcome']
            finally:h.close(ready)
        else:result=bridge.request_stop('SHUTDOWN_FLATTEN')['outcome']
        assert result['position_state']=='FLAT'
        assert result['status']==('FLATTENED' if damage=='none' else 'SHUTDOWN_INCOMPLETE')
        assert result['process_shutdown']==('VERIFIED_EXIT' if damage=='none' else 'INCOMPLETE')
        assert bool(calls)==(damage in ('none','exit-ack'))
        if damage in ('foreign','account','authority'): assert all(p.poll() is None for p in children)
    finally:
        for p in children:
            if p.poll() is None:
                p.stdin.close();p.wait(timeout=12)
