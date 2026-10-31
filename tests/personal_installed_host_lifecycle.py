"""Actual installed OwnedReadHost/Uvicorn lifecycle, synthetic read authority only."""
import json
import socket
import sys
import time
from contextlib import closing
from http.client import HTTPConnection

from personal_installed_read_host import fixture_composition
from personal_readonly_restart_child import reopen_readonly_fixture

from scripts.observation_runtime.quality_dips_read_service import OwnedReadHost


def main():
    raw=sys.stdin.buffer.read(65537)
    if len(raw)>65536:raise ValueError('INPUT_CAPACITY')
    value=json.loads(raw);start=time.monotonic();outcomes=[]
    for attempt in (1,2):
        with reopen_readonly_fixture(value) as opened:
            composition,_=fixture_composition(opened);host=OwnedReadHost(composition);ready=None
            try:
                ready=host.open_read_only_session();port=host.listener.getsockname()[1]
                assert host.verify_read_only_session(ready)
                with closing(HTTPConnection('127.0.0.1',port,timeout=4)) as conn:
                    conn.request('GET','/api/investments/quality-dips/selected-paper')
                    response=conn.getresponse();payload=json.loads(response.read());assert response.status==200
                    assert payload['cash']=='1015.9136' and payload['positions']=={}
                try:host.close_read_only_session({**ready,'host_id':'FOREIGN'})
                except ValueError:pass
                else:raise AssertionError('Foreign closure accepted')
                assert host.listener is not None
            finally:
                if host.listener is not None:host.close_read_only_session(ready)
            with socket.socket() as probe:assert probe.connect_ex(('127.0.0.1',port))!=0
            try:host.open_read_only_session()
            except ValueError as error:assert 'RETIRED' in str(error)
            else:raise AssertionError('Retired host restarted')
            outcomes.append({'attempt':attempt,'ready_verified':True,'wrong_identity_refused':True,
                'owned_close':True,'port_released':True,'retired_restart_refused':True,'cash':payload['cash']})
    print(json.dumps({'synthetic_only':True,'actual_installed_uvicorn':True,'cycles':outcomes,
        'seconds':round(time.monotonic()-start,3),'financial_writes':0,'provider_actions':0}))


if __name__=='__main__':main()
