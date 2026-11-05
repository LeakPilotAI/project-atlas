"""Bounded context-wire identity and failed-handshake cleanup, no OS child."""

import base64
import hashlib
import json
import time
from collections import deque
from types import SimpleNamespace

import pytest

from scripts.observation_runtime.aip06_offline_context import ContextWire, ContextPipes, IsolatedFixtureContext


def wire():
    queued=deque()
    api=SimpleNamespace(recv=lambda *a:queued.popleft() if queued else None)
    w=ContextWire.__new__(ContextWire)
    w.channels=api;w.incoming=1;w.outgoing=2;w.nonce='a'*32;w.context=1;w.peer=2
    w.deadline=time.monotonic()+2;w.sent=w.received=w.total=0
    raw=b'{}'
    packet={'schema':'AIP06_OFFLINE_CONTEXT_V1','nonce':w.nonce,'context':2,'peer':1,
            'sequence':1,'kind':'DATA','payload':base64.b64encode(raw).decode(),'sha256':hashlib.sha256(raw).hexdigest()}
    return w,queued,packet


@pytest.mark.parametrize('field',['schema','nonce','context','peer','sequence','payload','sha256'])
def test_wire_rejects_unbound_context_or_payload(field):
    w,q,p=wire();p[field]='wrong';q.append(json.dumps(p).encode())
    with pytest.raises((ValueError,TypeError)):w.receive()
    assert w.received==0


def test_wire_replay_and_expired_observation_refuse():
    w,q,p=wire();raw=json.dumps(p).encode();q.extend([raw,raw])
    assert w.receive()==('DATA',b'{}')
    with pytest.raises(ValueError):w.receive()
    w.deadline=time.monotonic()-1
    with pytest.raises(ValueError):w.receive(wait=False)


def test_abort_control_can_only_refuse_and_cannot_be_an_ack():
    w,q,p=wire();p['kind']='ABORT';q.append(json.dumps(p).encode())
    pipes=ContextPipes(w)
    with pytest.raises(ValueError,match='ABORTED_NO_ACCEPTANCE'):pipes.pump()
    assert not pipes.control and not any(pipes.buffers.values())


@pytest.mark.parametrize('failure_cleanup',[False,True])
def test_unread_terminal_data_is_cleaned_but_never_accepted(monkeypatch,failure_cleanup):
    import _xxinterpchannels as channels
    import _xxsubinterpreters as interpreters
    ctx=IsolatedFixtureContext(entry_sha256='a'*64)
    queue=deque([b'owned-unread-terminal-record']);closed=[]
    monkeypatch.setattr(channels,'recv',lambda *a:queue.popleft() if queue else None)
    monkeypatch.setattr(channels,'close',lambda c:closed.append(('close',c)))
    monkeypatch.setattr(channels,'destroy',lambda c:closed.append(('destroy',c)))
    monkeypatch.setattr(interpreters,'list_all',lambda:[0])
    ctx.channels=[1];ctx.interpreter=2
    ctx.wire=SimpleNamespace(deadline=time.monotonic()+1)
    ctx.executed.set();ctx.destroyed.set()
    ctx.thread=SimpleNamespace(join=lambda n:None,is_alive=lambda:False)
    if failure_cleanup:
        value=ctx.close(failed=True);assert value['passed'] is False and value['discarded']==1
    else:
        with pytest.raises(ValueError,match='UNREAD_OUTPUT'):ctx.close()
    assert ctx.closed and ctx.destroy_requested.is_set() and closed==[('close',1),('destroy',1)]


@pytest.mark.parametrize('payload',[{}, {'domain':'OPERATIONAL','native_acceptance':False},
                                   {'domain':'INJECTED_OFFLINE','native_acceptance':True}])
def test_context_refuses_operational_domain_before_creation(payload):
    ctx=IsolatedFixtureContext(entry_sha256='a'*64)
    with pytest.raises(ValueError):ctx.start(payload)
    assert ctx.interpreter is None and not ctx.channels
