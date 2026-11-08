"""Actual native readback code with in-memory OS ports; no native filesystem I/O."""
import copy
from pathlib import Path
from types import SimpleNamespace

import pytest
from app.services.paper_financial_replay import body, digest
from test_personal_paper_inception_memory import system

import scripts.observation_runtime.personal_paper_inception as module


def readback_ports(monkeypatch, s):
    paths={r['path']:role for role,r in s.n['resources'].items()}
    closed=[]

    class Output:
        def __init__(self,path):
            self.root=path;self.root_handle=paths[path]
        def close(self):closed.append(self.root_handle)
        def _verify(self):return True

    def read_bound(out,name,binding):
        value=s.files.values[out.root_handle,name]
        assert binding['sha256']==digest(value), 'synthetic native hash mismatch'
        return body(value).encode(),binding['id']

    native=SimpleNamespace(w=SimpleNamespace(WindowsOutput=Output),
        native=SimpleNamespace(file_identity=lambda role:s.n['resources'][role]['native_id']),
        read_bound=read_bound)
    monkeypatch.setattr(module.importlib.util,'spec_from_file_location',lambda *_:SimpleNamespace(loader=SimpleNamespace(exec_module=lambda _:None)))
    monkeypatch.setattr(module.importlib.util,'module_from_spec',lambda _:native)
    real_path=Path

    def path(value):
        if str(value) in paths:
            role=paths[str(value)]
            return SimpleNamespace(iterdir=lambda:iter(SimpleNamespace(name=n) for (r,n) in s.files.values if r==role))
        return real_path(value)
    monkeypatch.setattr(module,'Path',path)
    return closed


@pytest.mark.parametrize('lane',['QUALITY_DIPS','HYPERLIQUID'])
def test_actual_readback_verifies_two_separate_synthetic_accounts(monkeypatch,lane):
    s=system(lane)
    try:
        ready=s.pub.publish();closed=readback_ports(monkeypatch,s)
        assert module.NativePersonalInitialReadback().verify(s.e,ready['current']) is True
        assert sorted(closed)==['projection','report','source']
    finally:s.ledger.db.close()


@pytest.mark.parametrize('damage',['generation-bool','revision-bool','ack-bool','projection-bool','document-bool','document-float'])
def test_initial_readback_rejects_bool_or_float_revisions(monkeypatch,damage):
    s=system('QUALITY_DIPS')
    try:
        current=copy.deepcopy(s.pub.publish()['current'])
        if damage=='generation-bool':current['generation']=True
        elif damage=='revision-bool':current['revision']=False
        elif damage=='ack-bool':current['acknowledged_revision']=False
        elif damage=='projection-bool':current['projection']['required']=False
        else:
            doc=s.files.values['report','0001-report.json']
            doc['revision']=True if damage=='document-bool' else 1.0
            current['reports']['reports'][0]['sha256']=digest(doc)
        readback_ports(monkeypatch,s)
        with pytest.raises(ValueError):module.NativePersonalInitialReadback().verify(s.e,current)
    finally:s.ledger.db.close()


@pytest.mark.parametrize('lane',['QUALITY_DIPS','HYPERLIQUID'])
def test_initial_report_scope_cannot_bind_a_foreign_account(lane):
    s=system(lane)
    try:
        e=copy.deepcopy(s.e);e['report_scope']['account_id']='FOREIGN-ACCOUNT'
        with pytest.raises(ValueError):module.validate_personal_inception(e)
        assert not s.files.values and s.custody.row(s.b.scope()['operation_id']) is None
    finally:s.ledger.db.close()


def test_competing_write_during_readback_is_not_hidden_by_initial_inventory(monkeypatch):
    s=system('QUALITY_DIPS')
    try:
        current=s.pub.publish()['current'];readback_ports(monkeypatch,s)
        load=module.native_primitives
        def changed_backend():
            native=load();read=native.read_bound
            def read_then_inject(out,name,binding):
                value=read(out,name,binding)
                if name=='0001-report.json':s.files.values['report','unverified-late.json']={'SYNTHETIC':'COMPETING_WRITE'}
                return value
            native.read_bound=read_then_inject;return native
        monkeypatch.setattr(module,'native_primitives',changed_backend)
        with pytest.raises(ValueError,match='NAMESPACE'):module.NativePersonalInitialReadback().verify(s.e,current)
    finally:s.ledger.db.close()
