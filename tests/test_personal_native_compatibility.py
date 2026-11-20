"""NOT EXECUTED. Requires a separately approved exact disposable native scope."""
import copy
import json
import os
from pathlib import Path

import pytest
from app.services.paper_financial_replay import digest
from personal_native_compatibility_fixture import NativeCase, OwnedChild, checked_budget

from scripts.observation_runtime import personal_paper_inception as inception
from scripts.observation_runtime.personal_native_scope import (
    AUTHORIZATION,
    assess_python_layout,
)


@pytest.fixture(autouse=True)
def native_execution_approval():
    if os.environ.get('ATLAS_PERSONAL_NATIVE_TEST_APPROVAL')!=AUTHORIZATION:pytest.skip('NOT EXECUTED: exact personal native scope requires separate operator approval')


@pytest.fixture
def make_case(monkeypatch):
    b=checked_budget()
    if b.check()>=420:pytest.fail('NATIVE_TEST_ADMISSION_CLOSED')
    original=inception.native_primitives
    def create(lane,name):
        case=NativeCase(b.root/'native'/('case-'+name),lane,create=True)
        return case
    try:yield create
    finally:monkeypatch.setattr(inception,'native_primitives',original)


@pytest.mark.parametrize('lane',['QUALITY_DIPS','HYPERLIQUID'])
def test_native_once_only_publication_codec_and_nonmutating_reads(make_case,lane):
    case=make_case(lane,'success-'+lane.lower());pub=case.publisher();ready=pub.publish()
    before=case.hashes();state=case.decode_existing_source(ready['current'])
    assert state['cash']=='1000' and state['positions']=={} and all(state[k]=='0' for k in ('gross','costs','net'))
    assert case.e['parameters']['currency']==('USD' if lane=='QUALITY_DIPS' else 'USDC')
    assert pub.bootstrap.verify_publication()['current']==ready['current']
    assert not list((case.path/'projection').iterdir()) and case.hashes()==before
    with pytest.raises(ValueError):pub.publish()
    assert case.hashes()==before


@pytest.mark.parametrize('lane',['QUALITY_DIPS','HYPERLIQUID'])
@pytest.mark.parametrize('phase,state',[('before_reservation',None),('pending','PENDING'),('source','PENDING'),('commit','COMMITTED'),('ack','ACKNOWLEDGED')])
def test_abrupt_native_publication_and_fresh_process_inspection(make_case,lane,phase,state):
    case=make_case(lane,'death-'+lane.lower()+'-'+phase)
    child=OwnedChild(['--case',str(case.path),'--lane',lane,'--phase',phase])
    result=child.finish();assert result['returncode']==23 and result['reaped']
    reopened=NativeCase(case.path,lane);pub=reopened.publisher();row=reopened.custody.row(pub.bootstrap.scope()['operation_id'])
    assert (None if row is None else row[2])==state
    before=reopened.hashes()
    if state is None:
        assert not before # child died before durable reservation and financial effects
    elif state=='ACKNOWLEDGED':
        assert pub.bootstrap.verify_publication()['current']['revision']==0
        with pytest.raises(ValueError):pub.publish()
    else:
        with pytest.raises(ValueError):pub.bootstrap.verify_publication()
        with pytest.raises(ValueError):pub.publish()
    assert reopened.hashes()==before


@pytest.mark.parametrize('damage',['root','revision','report'])
def test_native_readback_refuses_inconsistent_pins_without_repair(make_case,damage):
    case=make_case('QUALITY_DIPS','bad-cut-'+damage);pub=case.publisher();current=copy.deepcopy(pub.publish()['current']);before=case.hashes()
    if damage=='root':current['source']['root']=[999,888,777]
    elif damage=='revision':current['acknowledged_revision']=False
    else:current['reports']['reports'][0]['sha256']='f'*64
    with pytest.raises((ValueError,OSError)):inception.NativePersonalInitialReadback().verify(case.e,current)
    assert case.hashes()==before


def test_missing_authority_refuses_before_native_financial_effects(make_case):
    case=make_case('QUALITY_DIPS','no-authority');case.allowed=False
    with pytest.raises(ValueError):case.publisher().publish()
    assert not case.hashes()


def test_actual_development_interpreter_is_reported_without_faking_d_readiness():
    from personal_native_compatibility_child import observed_development_layout
    b=checked_budget();observed=observed_development_layout();result=assess_python_layout(observed)
    b.write(b.root/'evidence'/'actual-python-layout.json',json.dumps({'observed':observed,'assessment':result},indent=2).encode())
    assert not result['startup_authorized']
    if any(not observed[k].startswith('D:\\') for k in ('native_image','base_executable','base_prefix','stdlib')):
        assert result['state']=='NOT_READY'
    assert Path(observed['native_image']).is_file() and len(digest(observed))==64
