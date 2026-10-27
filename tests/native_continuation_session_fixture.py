"""One-root native fixtures. All signing/currentness/final proofs SYNTHETIC."""
import json
import time
from contextlib import contextmanager

from app.services.paper_financial_replay import body, digest

from scripts.observation_runtime.native_fixture_budget import NativeFixtureBudget
from scripts.volume_inspector.native_continuation_fixture import (
    NativeSegmentFixture,
    financial_derive,
)


class Pins:
    def __init__(self,budget,parent,name):
        self.budget=budget;self.path=parent/(name+'-pin.json');self.lock=parent/(name+'-lock')
        self.available=True
        if not self.lock.exists():budget.write(self.lock,b'0')
    @contextmanager
    def lease(self):
        import msvcrt
        self.budget.check()
        with self.lock.open('r+b') as stream:
            deadline=time.monotonic()+30
            while True:
                self.budget.check()
                try:
                    msvcrt.locking(stream.fileno(),msvcrt.LK_NBLCK,1);break
                except OSError:
                    if time.monotonic()>=deadline:raise ValueError('SYNTHETIC_LOCK_TIMEOUT')
                    time.sleep(0.02)
            try:yield
            finally:stream.seek(0);msvcrt.locking(stream.fileno(),msvcrt.LK_UNLCK,1)
    def current(self):
        self.budget.check()
        if not self.available:raise ValueError('SYNTHETIC_CUSTODY_UNAVAILABLE')
        if not self.path.exists():return None
        if self.path.stat().st_size>1024*1024:raise ValueError('CUSTODY_BOUND')
        return json.loads(self.path.read_text(encoding='utf8'))
    def verify(self,pin):return self.available and self.current()==pin
    def advance(self,before,after):
        if self.current()!=before:raise ValueError('SYNTHETIC_CAS_CONFLICT')
        self.budget.write(self.path,body(after).encode(),replace=self.path.exists())


class Authority:
    def __init__(self,marker):self.marker=marker;self.valid=True
    def admitted(self):return not self.marker.exists() or json.loads(self.marker.read_text())['status']=='ACKNOWLEDGED'
    def verify_switch(self,*args):return self.valid and self.admitted()
    def verify_scope(self,*args):return self.valid
    def verify_read(self,*args):return self.valid and self.admitted()
    def verify_append(self,*args):return self.valid and self.admitted()
    def verify_rollover(self,*args):return self.valid and self.admitted()


def case(root,name):
    b=NativeFixtureBudget(root);p=b.root/'native'/name
    b.directory(p);b.directory(p/'custody')
    return b,p,Authority(p/'custody'/'switch-status.json')


def ledger(b,p,a,name,manifest,*,projected=True,kind='FINANCIAL',derive=None):
    scope={'domain':'NATIVE_CONTINUATION_DISPOSABLE_V1','name':name,'kind':kind,'manifest':manifest}
    result=NativeSegmentFixture(base=p/name,budget=b,custody=Pins(b,p/'custody',name),authority=a,scope=scope,
        derive=derive or (lambda rows:financial_derive(manifest,rows)),projection=projected)
    return result


def canonical_records(m,commands):
    from app.services.paper_financial_replay import (
        apply_event,
        event_stream_record,
        initial_state,
        strict,
    )
    state=initial_state(m);head=digest(m);rows=[]
    for command in commands:
        command=strict(body(command));state,receipt=apply_event(m,state,command);receipt['projection_required']=True
        checksum=digest([head,command,receipt])
        rows.append(event_stream_record(state['revision'],command['operation_id'],body(command),head,checksum,body(receipt)))
        head=checksum
    return rows


class SwitchStatus:
    def __init__(self,budget,path):self.budget,self.path=budget,path
    def pending(self):self.budget.write(self.path,b'{"status":"PENDING"}',replace=self.path.exists())
    def acknowledge(self,pin_digest):
        self.budget.write(self.path,body({'status':'ACKNOWLEDGED','catalog':pin_digest}).encode(),replace=True)
    def acknowledged(self):return self.path.exists() and json.loads(self.path.read_text())['status']=='ACKNOWLEDGED'
