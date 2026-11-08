"""Actual export method under injected inspections; NOT native-handle acceptance.

No native store constructor,provisioning,writer,provider or financial mutation.
"""
import copy
import importlib.util
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest
from app.services.paper_financial_audit import audit_financial_events
from app.services.paper_financial_replay import replay_verified_events
from continuation_fixture import Custody, manifests, records

from scripts.observation_runtime.native_continuation_contract import (
    native_fixture_delta,
    native_fixture_rows,
)
from scripts.observation_runtime.offline_continuation import OfflineContinuation

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('continuation_native_export_contract',ROOT/'scripts/volume_inspector/financial_record_store.py')
f=importlib.util.module_from_spec(spec);spec.loader.exec_module(f)


def source(lane, qd_count=124):
    m=manifests()[lane];rows=records()[lane]
    if lane=='QUALITY_DIPS':rows=rows[:qd_count]
    state,head,ops=replay_verified_events(m,rows);audit=audit_financial_events(m,rows,state)
    pin={'schema':'FS2_TEST_PIN_V1','root':[1,2,3 if lane=='QUALITY_DIPS' else 4],
         'inception':{'synthetic':'binding'},'epoch':m['epoch'],'entries':[{'synthetic':'binding'} for _ in rows]}
    obj=f.FinancialRecordStore.__new__(f.FinancialRecordStore)
    obj.trust=SimpleNamespace(current=lambda:copy.deepcopy(pin))
    inspection=[pin,m,rows,state,head,ops,audit]
    obj._inspect_existing=lambda:copy.deepcopy(tuple(inspection))
    def forbidden(*args,**kwargs):raise AssertionError('Writer/guard/provision used by read export')
    obj.guard=obj.execute=obj.snapshot=forbidden
    return SimpleNamespace(**locals())


def exports():
    return {lane:source(lane).obj.export_continuation_fixture(expected_pin=source(lane).pin)
            for lane in ('QUALITY_DIPS','HYPERLIQUID')}


def test_native_fixture_export_has_exact_committed_rows_without_write_capabilities():
    s=source('QUALITY_DIPS');before=copy.deepcopy(s.inspection)
    out=s.obj.export_continuation_fixture(expected_pin=s.pin)
    assert out['rows']==s.rows and out['state']==s.state and out['remaining_operations']==4
    assert s.inspection==before
    out['rows'].clear();assert s.rows
    assert not out['startup_authorized']


@pytest.mark.parametrize('damage',['foreign-pin','operational-codec','missing-row','source-count','state-revision','audit-count','changed-during-read'])
def test_export_refuses_mixed_or_incomplete_cuts(damage):
    s=source('QUALITY_DIPS');expected=copy.deepcopy(s.pin)
    if damage=='foreign-pin':expected['root']=[99,99,99]
    elif damage=='operational-codec':s.obj.record_versions={**f.DEFAULT_RECORD_VERSIONS,'pin':'QD_AUTO_OP_PIN_V1'}
    elif damage=='missing-row':s.inspection[2].pop()
    elif damage=='source-count':s.inspection[0]['entries'].pop()
    elif damage=='state-revision':s.inspection[3]['revision']=True
    elif damage=='audit-count':s.inspection[6]['source_revision']-=1
    else:
        def inspect():
            value=copy.deepcopy(tuple(s.inspection));s.pin['root']=[99,99,99];return value
        s.obj._inspect_existing=inspect
    with pytest.raises(ValueError):s.obj.export_continuation_fixture(expected_pin=expected)


def test_bridge_produces_independently_replayed_separate_account_rows():
    value=exports();authority=SimpleNamespace(verify_native_fixture_exports=lambda *args:True)
    result=native_fixture_rows(value,manifests=manifests(),authority=authority)
    assert len(result['QUALITY_DIPS'])==124 and len(result['HYPERLIQUID'])==4
    assert sum(map(len,result.values()))==128


@pytest.mark.parametrize('damage',['authority','currency','state','digest','schema','root-alias','unavailable-authority'])
def test_bridge_refuses_unsupported_source_evidence(damage):
    value=exports();a=SimpleNamespace(verify_native_fixture_exports=lambda *args:damage!='authority')
    if damage=='currency':value['QUALITY_DIPS']['manifest']['currency']='USDC'
    elif damage=='state':value['QUALITY_DIPS']['state']['cash']='999999'
    elif damage=='digest':value['HYPERLIQUID']['head']='bad'
    elif damage=='schema':value['HYPERLIQUID']['source_pin']['schema']='PERP_OP_PIN_V1'
    elif damage=='root-alias':value['HYPERLIQUID']['source_pin']['root']=value['QUALITY_DIPS']['source_pin']['root']
    elif damage=='unavailable-authority':a=None
    with pytest.raises(ValueError):native_fixture_rows(value,manifests=manifests(),authority=a)


def test_export_to_existing_archive_and_native_delta_no_duplicate_effects():
    root=ROOT/'logs/diagnostics'/('continuation-fixture-'+uuid.uuid4().hex);root.mkdir()
    archive=OfflineContinuation(root/'archive',custody=Custody(root),manifests=manifests());archive.create()
    a=SimpleNamespace(verify_native_fixture_exports=lambda *args:True)
    first=exports()
    delta=native_fixture_delta(first,archived_view=archive.read(),manifests=manifests(),authority=a)
    view=archive.publish_committed_fixture_records('native-cut-1',delta)
    s=source('QUALITY_DIPS',128)
    second={**first,'QUALITY_DIPS':s.obj.export_continuation_fixture(expected_pin=s.pin)}
    delta=native_fixture_delta(second,archived_view=view,manifests=manifests(),authority=a)
    assert len(delta['QUALITY_DIPS'])==4 and delta['HYPERLIQUID']==[]
    final=archive.publish_committed_fixture_records('native-cut-2',delta)
    assert final['accounts']['QUALITY_DIPS']['state']['revision']==128
    assert final['accounts']['HYPERLIQUID']['state']['revision']==4
    assert native_fixture_delta(second,archived_view=final,manifests=manifests(),authority=a)=={
        'QUALITY_DIPS':[],'HYPERLIQUID':[]}
    assert s.obj.export_continuation_fixture(expected_pin=s.pin)['remaining_operations']==0


@pytest.mark.parametrize('damage',['source-rollback','prefix-conflict','bad-archive-state','joint-capacity','revoked'])
def test_native_delta_refuses_unverified_catchup(damage):
    ms=manifests();v=exports();a=SimpleNamespace(verify_native_fixture_exports=lambda *args:True)
    accounts={lane:{'state':replay_verified_events(ms[lane],v[lane]['rows'])[0],
                    'head':v[lane]['head']} for lane in v}
    archived={'schema':'OFFLINE_CONTINUATION_VIEW_V1','execution':'FIXTURE_ONLY','startup_authorized':False,
              'rows':{lane:copy.deepcopy(v[lane]['rows']) for lane in v},'accounts':accounts}
    if damage=='source-rollback':archived['rows']['QUALITY_DIPS'].append(archived['rows']['QUALITY_DIPS'][0])
    elif damage=='prefix-conflict':archived['rows']['QUALITY_DIPS'][0]['digest']='bad'
    elif damage=='bad-archive-state':archived['accounts']['QUALITY_DIPS']['state']['cash']='999999'
    elif damage=='joint-capacity':
        q=source('QUALITY_DIPS',128);v['QUALITY_DIPS']=q.obj.export_continuation_fixture(expected_pin=q.pin)
        for lane in v:
            state,head,_=replay_verified_events(ms[lane],[])
            archived['rows'][lane]=[];archived['accounts'][lane]={'state':state,'head':head}
    else:
        count=[0]
        def verify(*args):count[0]+=1;return count[0]==1
        a.verify_native_fixture_exports=verify
    with pytest.raises(ValueError):native_fixture_delta(v,archived_view=archived,manifests=ms,authority=a)
