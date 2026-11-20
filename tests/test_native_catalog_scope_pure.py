"""No native constructors or filesystem effects:catalog pre-effect validation."""
import copy
from contextlib import ExitStack, nullcontext
from types import SimpleNamespace

import pytest
from app.services.paper_financial_replay import body, digest

from scripts.volume_inspector.native_continuation_fixture import (
    NativeContinuationUnknown,
    NativeSwitchFixture,
    f,
)


def fixture(monkeypatch):
    pin={'schema':'NATIVE_SWITCH_FIXTURE_PIN_V1','root':[1,2,3],'scope':{'id':[1,2,4],'sha256':'a'*64},'selection':None}
    state={'pin':pin,'valid':True,'root':[1,2,3]};calls=[]
    journal=SimpleNamespace(scope={'domain':'DISPOSABLE'},custody=SimpleNamespace(lease=nullcontext))
    scope={'schema':'NATIVE_SWITCH_FIXTURE_SCOPE_V1','roles':{'QD_SOURCE':digest(journal.scope)}}
    store=NativeSwitchFixture.__new__(NativeSwitchFixture);store.ExitStack=ExitStack;store.journals={'QD_SOURCE':journal}
    store.custody=SimpleNamespace(current=lambda:copy.deepcopy(state['pin']),verify=lambda p:state['valid'] and p==state['pin'],lease=nullcontext)
    store.out=SimpleNamespace(root_handle='MOCK-HANDLE');store.status=SimpleNamespace(pending=lambda:pytest.fail('publication preceded catalog verification'))
    monkeypatch.setattr(f.native,'file_identity',lambda _:state['root'])
    def read(*args):calls.append('read');return body(scope).encode(),None
    monkeypatch.setattr(f.s,'read_bound',read)
    return store,state,scope,calls


def test_verified_scope_reads_only_and_preserves_input(monkeypatch):
    store,state,_scope,calls=fixture(monkeypatch);before=copy.deepcopy(state)
    assert store._verified_catalog_scope()==state['pin'];assert state==before and calls==['read']


@pytest.mark.parametrize('damage',['schema','missing','root','custody','scope-version','scope-role','changed-during-read'])
def test_catalog_conflict_refuses_before_any_successor_effect(monkeypatch,damage):
    store,state,scope,calls=fixture(monkeypatch)
    if damage=='schema':state['pin']['schema']='QD_AUTO_OP_PIN_V1'
    elif damage=='missing':state['pin'].pop('scope')
    elif damage=='root':state['root']=[9,9,9]
    elif damage=='custody':state['valid']=False
    elif damage=='scope-version':scope['schema']='FOREIGN'
    elif damage=='scope-role':scope['roles']={}
    else:
        def read(*args):state['pin']['scope']['sha256']='b'*64;return body(scope).encode(),None
        monkeypatch.setattr(f.s,'read_bound',read)
    with pytest.raises(NativeContinuationUnknown):store.switch()
    if damage in ('schema','missing','root','custody'):assert calls==[]
