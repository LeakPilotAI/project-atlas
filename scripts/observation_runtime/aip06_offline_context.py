"""Explicit isolated interpreters for injected source qualification only.

No OS process launcher, financial-worker backend or native-acceptance capability.
Only the fixed, independently hash-checked test entry can execute. Interpreters
share immutable serialized bytes, never guards, ledgers or Python objects.
"""

import base64
import hashlib
import json
from pathlib import Path
import secrets
import threading
import time

from scripts.observation_runtime.aip06_harness import need


ENTRY = Path(__file__).resolve().parents[2] / 'tests' / 'aip06_joined_context_child.py'
MAX_PACKET = 1024 * 1024
MAX_TOTAL = 32 * 1024 * 1024


class ContextWire:
    def __init__(self, incoming, outgoing, *, nonce, context, peer, deadline):
        import _xxinterpchannels as channels
        self.channels, self.incoming, self.outgoing = channels, incoming, outgoing
        self.nonce, self.context, self.peer, self.deadline = nonce, context, peer, deadline
        self.sent = self.received = self.total = 0

    def send(self, kind, raw):
        need(type(raw) is bytes and len(raw) <= MAX_PACKET and time.monotonic() < self.deadline,
             'OFFLINE_CONTEXT_SEND_BOUND')
        self.sent += 1
        value = {'schema':'AIP06_OFFLINE_CONTEXT_V1','nonce':self.nonce,'context':self.context,
                 'peer':self.peer,'sequence':self.sent,'kind':kind,
                 'payload':base64.b64encode(raw).decode(),'sha256':hashlib.sha256(raw).hexdigest()}
        data = json.dumps(value,sort_keys=True,separators=(',',':')).encode()
        self.total += len(data)
        need(self.total <= MAX_TOTAL,'OFFLINE_CONTEXT_TOTAL_BOUND')
        self.channels.send(self.outgoing,data)

    def receive(self, *, wait=True):
        while True:
            need(time.monotonic() < self.deadline,'OFFLINE_CONTEXT_RECEIVE_BOUND')
            data = self.channels.recv(self.incoming,None)
            if data is None:
                if not wait:return None
                time.sleep(.001);continue
            need(type(data) is bytes and len(data) <= 2*MAX_PACKET,'OFFLINE_CONTEXT_PACKET')
            value = json.loads(data)
            need(set(value)=={'schema','nonce','context','peer','sequence','kind','payload','sha256'}
                 and value['schema']=='AIP06_OFFLINE_CONTEXT_V1' and value['nonce']==self.nonce
                 and value['context']==self.peer and value['peer']==self.context
                 and type(value['sequence']) is int and value['sequence']==self.received+1,
                 'OFFLINE_CONTEXT_IDENTITY_OR_SEQUENCE')
            raw=base64.b64decode(value['payload'],validate=True)
            need(len(raw)<=MAX_PACKET and hashlib.sha256(raw).hexdigest()==value['sha256'],
                 'OFFLINE_CONTEXT_PAYLOAD')
            self.received+=1;self.total+=len(data)
            need(self.total<=MAX_TOTAL,'OFFLINE_CONTEXT_TOTAL_BOUND')
            return value['kind'],raw


class ContextPipes:
    """Injected byte-pipe API for the existing credited transport.

    The integers below are offline endpoint selectors, never Windows handles.
    Only two finite input buffers exist; no arbitrary endpoint or object query.
    """
    def __init__(self, wire, handles=(1,2,3,4), control_handler=None):
        need(len(handles)==4 and len(set(handles))==4,'OFFLINE_PIPE_DISTINCT_ENDPOINTS')
        self.handles=tuple(handles);self.control_handler=control_handler
        self.wire=wire;self.buffers={handles[0]:bytearray(),handles[2]:bytearray()};self.control=[]

    def capacity(self, handle):
        need(handle in self.handles,'OFFLINE_PIPE_ENDPOINT');return 65536

    def pump(self):
        while True:
            item=self.wire.receive(wait=False)
            if item is None:return
            kind,raw=item
            if kind=='ABORT':
                need(False,'OFFLINE_CONTEXT_ABORTED_NO_ACCEPTANCE')
            if kind in ('DATA','CREDIT'):
                target=self.handles[0] if kind=='DATA' else self.handles[2]
                need(len(self.buffers[target])+len(raw)<=65536,'OFFLINE_PIPE_CAPACITY')
                self.buffers[target].extend(raw)
            elif self.control_handler is not None:self.control_handler(kind,raw)
            else:self.control.append(item)

    def available(self, handle):
        need(handle in self.buffers,'OFFLINE_PIPE_READ_ENDPOINT');self.pump()
        return len(self.buffers[handle])

    def read(self, handle, count):
        need(type(count) is int and 0<count<=self.available(handle),'OFFLINE_PIPE_READ_BOUND')
        raw=bytes(self.buffers[handle][:count]);del self.buffers[handle][:count];return raw

    def write(self, handle, raw):
        need(handle in (self.handles[1],self.handles[3]) and type(raw) is bytes and 0<len(raw)<=65536,'OFFLINE_PIPE_WRITE_BOUND')
        self.wire.send('DATA' if handle==self.handles[1] else 'CREDIT',raw);return len(raw)

    def pause(self):
        self.pump();time.sleep(.001)


class IsolatedFixtureContext:
    def __init__(self, *, entry_sha256, seconds=15):
        # Wall-clock watchdog for the injected test host, not the simulated
        # six-second IPC or eight-second Stop deadline. Journal verification
        # and independent probes remain inside the canonical 180-second case.
        need(type(seconds) is int and 0<seconds<=180,'OFFLINE_CONTEXT_TIME_BOUND')
        need(type(entry_sha256) is str and len(entry_sha256)==64,'OFFLINE_ENTRY_PIN')
        self.pin,self.seconds=entry_sha256,seconds
        self.interpreter=self.thread=self.wire=None
        self.channels=[];self.error=None;self.closed=False
        self.created=threading.Event();self.executed=threading.Event();self.destroy_requested=threading.Event()
        self.destroyed=threading.Event()

    def start(self, payload):
        import _xxsubinterpreters as interpreters
        import _xxinterpchannels as channels
        import sys
        need(self.interpreter is None and type(payload) is dict
             and payload.get('domain')=='INJECTED_OFFLINE' and payload.get('native_acceptance') is False,
             'OFFLINE_CONTEXT_ONLY_EXPLICIT_INJECTED_DOMAIN')
        raw=ENTRY.read_bytes();need(hashlib.sha256(raw).hexdigest()==self.pin,'OFFLINE_ENTRY_CHANGED')
        self.channels=[channels.create(),channels.create()]
        current=int(interpreters.get_current())
        nonce=secrets.token_hex(16);deadline=time.monotonic()+self.seconds
        config={'entry':str(ENTRY),'pin':self.pin,'payload':payload,'paths':list(sys.path),
                'incoming':int(self.channels[0]),'outgoing':int(self.channels[1]),
                'nonce':nonce,'peer':current,'deadline':deadline}
        code="""import sys,json,traceback
sys.dont_write_bytecode=True
c=json.loads(config);sys.path=c['paths']
try:
 from scripts.observation_runtime.aip06_offline_context import isolated_entry
 isolated_entry(c)
except BaseException:
 traceback.print_exc()
 raise
"""
        def run():
            try:
                # Creation, execution and destruction use the same embedding
                # thread; imported threading state must not be torn down from
                # an unrelated thread at process exit.
                self.interpreter=interpreters.create();config['context']=int(self.interpreter)
                self.created.set()
                encoded=json.dumps(config).encode();need(len(encoded)<=MAX_PACKET,'OFFLINE_CONTEXT_CONFIG_BOUND')
                interpreters.run_string(self.interpreter,code,{'config':encoded})
            except BaseException as error:self.error=error
            finally:
                self.created.set();self.executed.set()
                self.destroy_requested.wait(max(0,deadline-time.monotonic())+1)
                if self.interpreter is not None:
                    try:interpreters.destroy(self.interpreter);self.destroyed.set()
                    except BaseException as error:self.error=error
        self.thread=threading.Thread(target=run,name='aip06-isolated-injected-context')
        self.thread.start()
        need(self.created.wait(min(3,self.seconds)) and self.interpreter is not None,
             'OFFLINE_CONTEXT_CREATE_FAILED')
        child=int(self.interpreter);need(current!=child,'OFFLINE_CONTEXT_NOT_ISOLATED')
        self.wire=ContextWire(int(self.channels[1]),int(self.channels[0]),nonce=nonce,
                              context=current,peer=child,deadline=deadline)
        return self.wire

    def close(self, *, failed=False):
        import _xxsubinterpreters as interpreters
        import _xxinterpchannels as channels
        need(not self.closed and self.thread is not None,'OFFLINE_CONTEXT_CLOSE_ONCE')
        need(self.executed.wait(max(0,self.wire.deadline-time.monotonic())+1),
             'OFFLINE_CONTEXT_STILL_RUNNING_NO_FORCED_DESTROY')
        # All messages must have an owner; silence or discarded queued output
        # is not a clean handshake. The caller drains the final DONE record.
        discarded=0
        for channel in self.channels:
            while channels.recv(channel,None) is not None:
                discarded+=1
                need(discarded<=4096,'OFFLINE_CONTEXT_UNREAD_OUTPUT_CAPACITY')
        ident=int(self.interpreter);self.destroy_requested.set();self.thread.join(3)
        need(not self.thread.is_alive() and self.destroyed.is_set(),'OFFLINE_CONTEXT_DESTROY_UNCONFIRMED')
        need(ident not in [int(i) for i in interpreters.list_all()],'OFFLINE_CONTEXT_DESTROY_UNCONFIRMED')
        for channel in self.channels:channels.close(channel);channels.destroy(channel)
        self.closed=True
        need(failed or discarded==0,'OFFLINE_CONTEXT_UNREAD_OUTPUT')
        need(failed or self.error is None,'OFFLINE_CONTEXT_EXECUTION_FAILED')
        return {'context':ident,'closed':True,'native_acceptance':False,'financial_worker':False,
                'passed':not failed and self.error is None,'discarded':discarded}


def isolated_entry(config):
    import _xxsubinterpreters as interpreters
    import sys
    need(int(interpreters.get_current())==config['context']!=config['peer'],'OFFLINE_ACTUAL_CONTEXT_ID')
    raw=Path(config['entry']).read_bytes()
    need(Path(config['entry'])==ENTRY and hashlib.sha256(raw).hexdigest()==config['pin'],
         'OFFLINE_CHILD_ENTRY_PIN_OR_PATH')
    def policy(event,args):
        if event in ('subprocess.Popen','_winapi.CreateProcess','os.system','os.spawn','os.posix_spawn',
                     'socket.bind','socket.connect','socket.getaddrinfo','ctypes.dlopen'):
            raise PermissionError('OFFLINE_CONTEXT_NO_NATIVE_OR_NETWORK_CAPABILITY')
    sys.addaudithook(policy)
    wire=ContextWire(config['incoming'],config['outgoing'],nonce=config['nonce'],context=config['context'],
                     peer=config['peer'],deadline=config['deadline'])
    namespace={'__name__':'aip06_pinned_offline_child','__file__':str(ENTRY)}
    exec(compile(raw,str(ENTRY),'exec'),namespace)
    namespace['run'](wire,config['payload'])
