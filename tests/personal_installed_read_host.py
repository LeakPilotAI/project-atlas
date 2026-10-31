"""Bounded installed-candidate HTTP fixture over a genuinely reopened native cut.

No operational authority, provider, financial command, service or writer.
EOF retires only this host. Original installed assets/routes are reused.
"""
import json
import os
import sys
import threading
import uuid
from http.server import BaseHTTPRequestHandler

from fastapi.testclient import TestClient
from personal_readonly_restart_child import reopen_readonly_fixture

from scripts.observation_runtime.bounded_http import BoundedHTTPServer
from scripts.observation_runtime.quality_dips_read_service import (
    build_app,
    observe_self,
)


def fixture_composition(opened):
    """Explicit fixture adapter around the real native read capability."""
    reader=opened['reader'];identity=observe_self();state={'refused':False}
    class Composition:
        account=opened['native']['account_id'];epoch=opened['native']['epoch']
        host_id='SYNTHETIC-INSTALLED-'+uuid.uuid4().hex
        clock=staticmethod(opened['clock'])
        def admitted(self,fn):
            if state['refused']:raise ValueError('SYNTHETIC_READ_DISCONNECTED')
            return fn()
        def read_committed(self,a,e):return self.admitted(lambda:reader.read_committed(a,e))
        def verify(self,payload,**scope):return reader.verify(payload,**scope)
        def preflight(self):return self.read_committed(self.account,self.epoch)
    composition=Composition();composition.identity=identity
    composition.observer=observe_self;composition.host_claim_lock=threading.Lock();composition.host_claimed=False
    return composition,state


def main():
    raw=sys.stdin.buffer.readline(65537)
    if len(raw)>65536:raise ValueError('TEST_INPUT_BOUND')
    value=json.loads(raw)
    with reopen_readonly_fixture(value) as opened:
        composition,state=fixture_composition(opened);identity=composition.identity
        composition.preflight()
        class Handler(BaseHTTPRequestHandler):
            protocol_version='HTTP/1.0'
            def log_message(self,*args):pass
            def do_GET(self):self.dispatch()
            def do_POST(self):self.dispatch()
            def dispatch(self):
                if len(self.headers.get_all('Host',[]))!=1 or len(self.headers.get_all('Origin',[]))>1:
                    self.server.record_status(403);self.send_error(403);return
                response=client.request(self.command,self.path,headers=dict(self.headers))
                self.server.record_status(response.status_code)
                self.send_response(response.status_code)
                for key,val in response.headers.items():
                    if key.lower() not in ('connection','transfer-encoding'):self.send_header(key,val)
                self.send_header('Connection','close')
                self.send_header('X-Atlas-Test-Domain','SYNTHETIC_NATIVE_INSTALLATION')
                self.end_headers();self.wfile.write(response.content)
        server=BoundedHTTPServer(('127.0.0.1',0),Handler,limit=96,seconds=180)
        port=server.server_address[1];app=build_app(composition,port)
        with TestClient(app,base_url=f'http://127.0.0.1:{port}') as client:
            thread=threading.Thread(target=server.serve_forever);thread.start()
            def control():
                for line in sys.stdin:
                    if line.strip()=='REFUSE':state['refused']=True
                    elif line.strip()=='RESUME_READ':state['refused']=False
                    elif line.strip()=='CLOSE':break
                server.shutdown()
            worker=threading.Thread(target=control,daemon=True);worker.start()
            print(json.dumps({'ready':True,'url':f'http://127.0.0.1:{port}/quality_dips.html?mode=selected-paper',
                'host_id':composition.host_id,'process':identity,'native_cash':opened['result']['cash'],
                'source_root':opened['result']['source_root'],'synthetic_only':True}),flush=True)
            thread.join(185)
            if thread.is_alive():raise ValueError('BOUNDED_TEST_HOST_NOT_RELEASED')
            print(json.dumps({'closed':True,'counts':server.counts(),'pid':os.getpid()}),flush=True)


if __name__=='__main__':main()
