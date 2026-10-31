"""Read-host routing with explicit synthetic authority/reader/OS doubles only."""
import copy
import os
from types import SimpleNamespace

import pytest
from app.services.paper_financial_replay import digest
from app.services.personal_paper_runtime import PersonalOperatorInstallation
from app.services.quality_dips_operational_presentation import OperationalAutonomousSelectedRead
from fastapi.testclient import TestClient
from test_personal_paper_runtime import installed
from test_quality_dips_autonomous_enrollment import fixture

import scripts.observation_runtime.personal_paper_read as composition_module
from scripts.observation_runtime.personal_installation_technical import (
    NativePersonalTechnicalChecks,
)
from scripts.observation_runtime.personal_paper_read import PersonalReadOnlyAccountComposition
from scripts.observation_runtime.personal_runtime_current import PersonalRuntimeCurrent
from scripts.observation_runtime.personal_writer_ownership import NativePersonalWriterOwnership
from scripts.observation_runtime.quality_dips_read_service import build_app


def setup(monkeypatch):
    native=copy.deepcopy(fixture().e)
    original=copy.deepcopy(native)
    trace=[]
    clock=lambda:1000
    identity={'pid':os.getpid(),'creation_filetime':987,'image':'D:\\SYNTHETIC-READER.exe'}
    monkeypatch.setattr(composition_module,'observe_self',lambda:copy.deepcopy(identity))
    reader=object.__new__(OperationalAutonomousSelectedRead)
    reader.enrollment={'schema':'QD_AUTO_OP_READ_ENROLLMENT_V1','account_id':native['account_id'],'epoch':native['epoch']}
    payload={'status':'SYNTHETIC_TEST_ONLY'}
    reader.read_committed=lambda *args:trace.append('read') or copy.deepcopy(payload)
    reader.verify=lambda *args,**kw:{'verified':True}
    current=object.__new__(PersonalRuntimeCurrent)
    current.reader,current.clock=reader,clock
    current.bootstrap=SimpleNamespace(enrollment={'native_enrollment':native})
    current._capture=lambda now:trace.append('capture')
    owner=object.__new__(NativePersonalWriterOwnership)
    owner.read_only,owner.enrollment=True,native
    owner.identity={'schema':'QD_OP_PROCESS_ID_V1',**identity}
    owner._verify=lambda:trace.append('own-read-only')
    tech=object.__new__(NativePersonalTechnicalChecks)
    tech.current,tech.engine,tech.ownership=current,None,owner
    ports={'current':current,'reader':reader,'ownership':owner,'clock':clock}
    base=installed(accounts={'QUALITY_DIPS':digest(native)},ports=ports)
    base.reader.value['actions']=['READ_ONLY']
    tech.inspect=lambda request:copy.deepcopy(base.facts)
    installation=PersonalOperatorInstallation(policy=base.p,reader=base.reader,identity=base.owner,
            technical=tech,clock=clock,components=ports,release_digest=native['release_digest'],accounts=base.reader.value['accounts'])
    base.reader.value['release_digest']=native['release_digest']
    owner.authority=installation.identity
    composition=PersonalReadOnlyAccountComposition(current=current,installation=installation,ownership=owner)
    return SimpleNamespace(**locals())


def test_new_read_process_never_relabels_historical_writer_or_exposes_financial_actions(monkeypatch):
    s=setup(monkeypatch)
    assert s.composition.preflight()==s.payload
    assert s.native==s.original
    assert all(not hasattr(s.composition,name) for name in ('start','accept','dispatch','reserve_session'))
    assert s.composition.verify_control_bridge(object()) is False
    assert set(s.trace)<={'read','capture','own-read-only'}


@pytest.mark.parametrize('damage',['mode','account','process','revoked','financial-facts'])
def test_reader_change_or_missing_acceptance_refuses(monkeypatch,damage):
    s=setup(monkeypatch)
    if damage=='mode':s.owner.read_only=False
    elif damage=='account':s.composition.account='FOREIGN'
    elif damage=='process':s.identity['creation_filetime']+=1
    elif damage=='revoked':s.installation.revoke()
    else:s.base.facts['FINANCIAL_INTEGRITY']=False
    with pytest.raises(ValueError):s.composition.preflight()
    assert s.native==s.original


def test_original_selected_page_and_read_host_keep_all_commands_disabled(monkeypatch):
    s=setup(monkeypatch)
    app=build_app(s.composition,8765)
    with TestClient(app,base_url='http://127.0.0.1:8765') as client:
        assert client.get('/health').status_code==200
        assert client.get('/quality_dips.html?mode=selected-paper').status_code==200
        assert client.get('/api/investments/quality-dips').status_code==404
        assert client.post('/api/investments/quality-dips/selected-paper').status_code==403
        assert client.post('/_atlas/control/stop').status_code==403
    with pytest.raises(ValueError):build_app(s.composition,8765,control_bridge=object())
    assert set(s.trace)<={'read','capture','own-read-only'}
