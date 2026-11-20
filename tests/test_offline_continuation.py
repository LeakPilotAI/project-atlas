"""Real confined file/subprocess tests of continuation; no financial dispatch."""
import copy
import os
import subprocess
import sys
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from app.services.paper_financial_replay import replay_verified_events
from continuation_fixture import Custody, manifests, records

from scripts.observation_runtime.offline_continuation import (
    MAX_RECORDS,
    OfflineContinuation,
    Uncertain,
)

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def system():
    root = ROOT/'logs/diagnostics'/('continuation-fixture-'+uuid.uuid4().hex)
    root.mkdir()
    custody = Custody(root)
    archive = OfflineContinuation(root/'archive', custody=custody, manifests=manifests())
    archive.create()
    return root, custody, archive


def batches():
    rows = records()
    return rows, {'QUALITY_DIPS':rows['QUALITY_DIPS'][:124],'HYPERLIQUID':rows['HYPERLIQUID']}, {'QUALITY_DIPS':rows['QUALITY_DIPS'][124:],'HYPERLIQUID':[]}


def test_two_account_rollover_matches_uninterrupted_replay_and_preserves_bytes(system):
    root, custody, archive = system
    rows, first, second = batches()
    archive.publish_committed_fixture_records('batch1', first)
    before = {p.name:p.read_bytes() for p in archive.root.iterdir()}
    result = archive.publish_committed_fixture_records('batch2', second)
    assert all((archive.root/name).read_bytes()==value for name,value in before.items())
    assert len(custody.current()['segments'])==2 and MAX_RECORDS==128
    for lane in rows:
        state, head, _ = replay_verified_events(manifests()[lane], rows[lane])
        assert result['accounts'][lane]=={'state':state,'head':head}
    assert result['accounts']['QUALITY_DIPS']['state']['revision']==132
    assert result['accounts']['HYPERLIQUID']['state']['revision']==4
    assert not result['startup_authorized']
    restarted = OfflineContinuation(root/'archive',custody=Custody(root),manifests=manifests())
    assert restarted.read()==result
    assert restarted.publish_committed_fixture_records('batch2',second)==result
    assert len(custody.current()['segments'])==2


@pytest.mark.parametrize('phase',['before_intent','intent','record','commit','current_commit','ack','acknowledged','partial_record'])
def test_abrupt_child_exit_and_restart_never_replays_uncertain_publication(system,phase):
    root,_custody,archive=system
    run=subprocess.run([sys.executable,str(ROOT/'tests/continuation_crash_child.py'),str(root),phase],
                       capture_output=True,timeout=30,check=False)
    assert run.returncode==73,run.stderr
    restarted=OfflineContinuation(root/'archive',custody=Custody(root),manifests=manifests())
    _,first,_=batches()
    if phase=='before_intent':
        assert restarted.read()['accounts']['QUALITY_DIPS']['state']['revision']==0
        restarted.publish_committed_fixture_records('SYNTHETIC-BATCH-1',first)
    elif phase=='acknowledged':
        assert restarted.read()['accounts']['QUALITY_DIPS']['state']['revision']==124
        assert restarted.publish_committed_fixture_records('SYNTHETIC-BATCH-1',first)==restarted.read()
    else:
        with pytest.raises((Uncertain,ValueError,FileNotFoundError)):restarted.read()
        before={p.name:p.read_bytes() for p in archive.root.iterdir()}
        recovery=restarted.inspect_recovery()
        assert recovery['status']=='UNKNOWN' and recovery['view'] is None and not recovery['admission_authorized']
        with pytest.raises((Uncertain,ValueError,FileNotFoundError)):
            restarted.publish_committed_fixture_records('SYNTHETIC-BATCH-1',first)
        assert before=={p.name:p.read_bytes() for p in archive.root.iterdir()}


@pytest.mark.parametrize('damage',['hash','missing','duplicate-json','substitution','hardlink','rollback-authority'])
def test_corruption_and_foreign_evidence_refuse(system,damage):
    root,custody,archive=system
    _,first,_=batches()
    archive.publish_committed_fixture_records('batch1',first)
    path=archive.root/'0001-record.json'
    if damage=='hash':path.write_bytes(path.read_bytes()+b' ')
    elif damage=='missing':path.rename(root/'removed-record.json')
    elif damage=='duplicate-json':path.write_bytes(b'{"schema":1,"schema":2}')
    elif damage=='substitution':
        raw=path.read_bytes();path.rename(root/'original-record.json');path.write_bytes(raw)
    elif damage=='hardlink':os.link(path,root/'linked-record.json')
    else:custody.valid=False
    with pytest.raises((ValueError,FileNotFoundError)):archive.read()


@pytest.mark.parametrize('damage',['duplicate-id','revision','receipt','too-many','foreign-account'])
def test_bad_batches_refuse_before_intent(system,damage):
    _,_,archive=system
    _,first,_=batches()
    if damage=='duplicate-id':first['QUALITY_DIPS'].append(copy.deepcopy(first['QUALITY_DIPS'][0]))
    elif damage=='revision':first['QUALITY_DIPS'][0]['revision']=True
    elif damage=='receipt':first['QUALITY_DIPS'][0]['receipt']='{}'
    elif damage=='too-many':first['QUALITY_DIPS']*=2
    else:first['UNENROLLED']=[]
    before={p.name:p.read_bytes() for p in archive.root.iterdir()}
    with pytest.raises((ValueError,TypeError)):archive.publish_committed_fixture_records('bad',first)
    assert before=={p.name:p.read_bytes() for p in archive.root.iterdir()}


def test_concurrent_duplicate_publication_is_one_segment(system):
    root,custody,archive=system
    _,first,_=batches()
    def publish(_):
        return OfflineContinuation(root/'archive',custody=Custody(root),manifests=manifests()).publish_committed_fixture_records('same',first)
    with ThreadPoolExecutor(2) as pool:values=list(pool.map(publish,range(2)))
    assert values[0]==values[1] and len(custody.current()['segments'])==1
    changed=copy.deepcopy(first);changed['QUALITY_DIPS']=changed['QUALITY_DIPS'][:122]
    with pytest.raises(Uncertain):archive.publish_committed_fixture_records('same',changed)


def test_open_predecessor_refuses_rollover_and_second_inception(system):
    _,_,archive=system
    rows=records()
    archive.publish_committed_fixture_records('open',{'QUALITY_DIPS':rows['QUALITY_DIPS'][:1],'HYPERLIQUID':[]})
    with pytest.raises(Uncertain):archive.publish_committed_fixture_records('next',{'QUALITY_DIPS':rows['QUALITY_DIPS'][1:2],'HYPERLIQUID':[]})
    with pytest.raises(Uncertain):archive.create()


def test_bounded_segment_count_never_resets_original_inception():
    from scripts.observation_runtime.offline_continuation import MAX_SEGMENTS
    assert MAX_SEGMENTS==16
    root=ROOT/'logs/diagnostics'/('continuation-fixture-'+uuid.uuid4().hex);root.mkdir()
    archive=OfflineContinuation(root/'archive',custody=Custody(root),manifests=manifests());archive.create()
    rows=records()['QUALITY_DIPS']
    for index in range(MAX_SEGMENTS):
        archive.publish_committed_fixture_records(str(index),{'QUALITY_DIPS':rows[index*2:index*2+2],'HYPERLIQUID':[]})
    with pytest.raises(ValueError,match='CAPACITY'):
        archive.publish_committed_fixture_records('exhausted',{'QUALITY_DIPS':rows[32:34],'HYPERLIQUID':[]})
    assert archive.read()['accounts']['QUALITY_DIPS']['state']['revision']==32
    assert len(list(archive.root.iterdir()))==65


def test_cross_segment_duplicate_effect_refuses_even_with_new_batch_id(system):
    _,_,archive=system
    _,first,_=batches();archive.publish_committed_fixture_records('batch1',first)
    with pytest.raises(ValueError):archive.publish_committed_fixture_records('different',first)
    assert len(archive.read()['rows']['QUALITY_DIPS'])==124


def test_missing_drain_authority_refuses_without_publication(system,monkeypatch):
    _,custody,archive=system
    monkeypatch.setattr(custody,'verify_boundary',lambda value:False)
    _,first,_=batches()
    with pytest.raises(Uncertain):archive.publish_committed_fixture_records('no-permission',first)
    assert {p.name for p in archive.root.iterdir()}=={'scope.json'}


def test_oversized_payload_refuses_without_publication(system):
    _,_,archive=system
    _,first,_=batches();first['QUALITY_DIPS'][0]['command']='x'*32769
    with pytest.raises(ValueError,match='BOUNDED'):archive.publish_committed_fixture_records('oversized',first)
    assert {p.name for p in archive.root.iterdir()}=={'scope.json'}


def test_fs3_historical_reports_match_unsegmented_stream_after_rollover(system):
    from datetime import datetime
    from zoneinfo import ZoneInfo

    from app.services.paper_daily_report import audit_daily_report, build_daily_report
    from app.services.paper_financial_replay import digest
    _,_,archive=system
    original,first,second=batches()
    archive.publish_committed_fixture_records('one',first)
    view=archive.publish_committed_fixture_records('two',second)
    for lane, m in manifests().items():
        scope={'schema':'FS3_REPORT_SCOPE_V1','account_id':'SYNTHETIC-'+lane,'epoch':m['epoch'],
               'policy_digest':digest(m),'timezone':m['timezone']}
        day=datetime.fromtimestamp(m['opened_at'],ZoneInfo(m['timezone'])).date().isoformat()
        observed=max(__import__('json').loads(row['command'])['timestamp'] for row in original[lane])+86400
        pin={'epoch':m['epoch'],'entries':[row['digest'] for row in original[lane]],
             'root':'SYNTHETIC-LOGICAL-COMPLETE-SOURCE','inception':digest(m)}
        expected=build_daily_report(scope,m,pin,original[lane],day,observed)
        actual=build_daily_report(scope,m,pin,view['rows'][lane],day,observed)
        assert actual==expected
        assert audit_daily_report(actual,scope,m,pin,view['rows'][lane],view['accounts'][lane]['state'])
        assert actual['currency']==m['currency']


def test_no_scope_authority_or_foreign_root_is_default_refusal(system):
    root,custody,_=system
    custody.valid=False
    with pytest.raises(ValueError):OfflineContinuation(root/'archive',custody=custody,manifests=manifests())
    with pytest.raises(ValueError):OfflineContinuation(ROOT/'archive',custody=Custody(root),manifests=manifests())


def test_cross_process_same_batch_is_one_acknowledged_segment(system):
    root,custody,archive=system
    command=[sys.executable,str(ROOT/'tests/continuation_crash_child.py'),str(root),'no-crash']
    children=[subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE) for _ in range(2)]
    for child in children:
        _,errors=child.communicate(timeout=30)
        assert child.returncode==0,errors
    assert len(custody.current()['segments'])==1
    assert archive.inspect_recovery()['status']=='ACKNOWLEDGED'
    assert len(archive.read()['rows']['QUALITY_DIPS'])==124


def test_actual_autonomous_qd_decision_records_replay_without_financial_dispatch():
    from types import SimpleNamespace

    from app.investment.quality_dips_candidate_evidence import CandidateEvidenceAdapter
    from app.services.paper_financial_replay import (
        apply_event,
        body,
        digest,
        event_stream_record,
        initial_state,
    )
    from app.services.quality_dips_autonomous_paper import AutonomousPaper
    from test_quality_dips_autonomous_paper import STAMP, candidate, quote

    ms=manifests()
    m=ms['QUALITY_DIPS']
    m.update(schema='PAPER_EPOCH_AUTONOMOUS_QD_V1',epoch='SYNTHETIC-AUTO-CONTINUATION',opened_at=STAMP,
             cost_policy='SIDE_NOTIONAL_FEE_SLIPPAGE_V1',autonomous_policy={
                 'schema':'QD_AUTO_RISK_PARTIAL_THESIS_V1','quote_age_seconds':5,'max_spread_bps':'50',
                 'participation':'0.5','quantity_step':'0.001','partial_fraction':'0.4','max_session_seconds':3600})
    n=SimpleNamespace(now=[STAMP],m=m)
    proof=lambda schema,payload:{'schema':schema,'verified':True,'binding':digest(payload),
                                'receipt_id':'EXPLICIT_SYNTHETIC_AUTHORITY'}
    engine=AutonomousPaper.__new__(AutonomousPaper)
    engine.ledger=SimpleNamespace(manifest=m)  # NO store,connect method or writer.
    engine.entry_admission_closed=False
    engine.grant={'schema':'QD_AUTO_SESSION_FIXTURE_V1','session_id':'synthetic-session','epoch':m['epoch'],
                  'issued_at':STAMP,'expires_at':STAMP+3600,'capabilities':['AUTO_ENTRY','AUTO_EXIT'],
                  'feed_id':'synthetic-L1','calendar_id':'synthetic-NYSE-2026'}
    engine.candidates=CandidateEvidenceAdapter(
        ranking_authority=SimpleNamespace(verify_current=lambda v,now:proof('QD_RANKING_VERIFIED_V1',v)),
        execution_authority=SimpleNamespace(verify=lambda v,now:proof('QD_EXECUTION_VERIFIED_V1',v)))
    state=initial_state(m);head=digest(m);out=[];snapshots=[];b=candidate(n)
    for index,current in enumerate([None,{'evidence_quality':'HIGH','fundamentals_score':60},{'classification':'THESIS_BROKEN'}]):
        n.now[0]=STAMP+index
        q=quote(n,b,bid=str(100+10*index),ask=str(100+10*index+.1)) if index else quote(n,b)
        obs=None if current is None else {'symbol':b['instrument']['symbol'],'instrument':b['instrument'],
                                         'observed_at':n.now[0],'current':current}
        request={'bundles':[b] if index==0 else [],'quotes':[q],'observation':obs}
        command=engine._decide(state,'SYNTHETIC-AUTO-'+str(index),request,
                               proof('QD_AUTO_SESSION_PROOF_V1',engine.grant),
                               proof('QD_AUTO_SOURCE_PROOF_V1',request),'RUNNING',n.now[0])
        state,receipt=apply_event(m,state,command);receipt['projection_required']=False
        snapshots.append(copy.deepcopy(state))
        checksum=digest([head,command,receipt]);out.append(event_stream_record(state['revision'],command['operation_id'],
                        body(command),head,checksum,body(receipt)));head=checksum
    root=ROOT/'logs/diagnostics'/('continuation-fixture-'+uuid.uuid4().hex);root.mkdir()
    custody=Custody(root)
    # Explicit synthetic enrollment of this different manifest,never operational authority.
    custody.verify_scope=lambda path,accounts:Path(path)==root/'archive' and accounts==ms
    archive=OfflineContinuation(root/'archive',custody=custody,manifests=ms);archive.create()
    archive.publish_committed_fixture_records('auto',{'QUALITY_DIPS':out,'HYPERLIQUID':[]})
    result=archive.publish_committed_fixture_records('perp',{'QUALITY_DIPS':[],'HYPERLIQUID':records()['HYPERLIQUID']})
    assert result['accounts']['QUALITY_DIPS']=={'state':state,'head':head}
    assert [__import__('json').loads(r['command'])['manual'] for r in out]==[False]*3
    from app.services.paper_financial_replay import number
    assert state['revision']==3 and all(number(p['remaining'])==0 for p in state['positions'].values())
    assert [number(__import__('json').loads(r['command'])['quantity']) for r in out]==[number('1'),number('0.4'),number('0.6')]

    # Exact Decimal equalities,not text padding or a floating-point tolerance.
    # Retain original entry cost/basis as history;remaining exposure/cost must be zero.
    from app.services.paper_financial_audit import audit_financial_events
    pid=next(iter(state['positions']))
    position=state['positions'][pid]
    assert [number(s['positions'][pid]['remaining']) for s in snapshots]==[number('1'),number('0.6'),number('0')]
    assert [number(s['positions'][pid]['remaining_entry_costs']) for s in snapshots]==[number('0.04'),number('0.024'),number('0')]
    assert number(position['quantity'])==1 and number(position['entry'])==100
    assert number(position['entry_costs'])==number('0.04')  # Historical evidence remains intact.
    assert number(position['remaining'])*number(position['entry'])==0
    assert number(position['realized_net'])==number('15.9136')
    assert {key:number(state[key]) for key in ('cash','gross','costs','net')}=={
        'cash':number('1015.9136'),'gross':number('16'),'costs':number('0.0864'),'net':number('15.9136')}
    assert number(state['cash'])==number(m['opening_cash'])+number(state['net'])
    audit=audit_financial_events(m,out,state)
    assert audit['source_revision']==3 and not audit['startup_authorized']
    print({'synthetic_remaining_text':position['remaining'],'remaining_entry_costs':position['remaining_entry_costs'],
           'cash':state['cash'],'gross':state['gross'],'costs':state['costs'],'net':state['net'],
           'exact_zero_basis':True,'independent_audit_revision':audit['source_revision']})


def test_scope_revocation_after_construction_prevents_new_publication(system,monkeypatch):
    _,custody,archive=system
    _,first,_=batches()
    before={p.name:p.read_bytes() for p in archive.root.iterdir()}
    monkeypatch.setattr(custody,'verify_scope',lambda *args:False)
    with pytest.raises(Uncertain):archive.publish_committed_fixture_records('revoked',first)
    assert before=={p.name:p.read_bytes() for p in archive.root.iterdir()}
    assert archive.inspect_recovery()['status']=='UNKNOWN'


def test_creation_revocation_refuses_before_archive_directory_creation():
    root=ROOT/'logs/diagnostics'/('continuation-fixture-'+uuid.uuid4().hex);root.mkdir()
    custody=Custody(root)
    archive=OfflineContinuation(root/'archive',custody=custody,manifests=manifests())
    custody.valid=False
    with pytest.raises(Uncertain):archive.create()
    assert not archive.root.exists() and custody.current() is None


def test_fixture_custody_refuses_foreign_path_before_creating_any_file():
    foreign=ROOT/'logs/diagnostics'/('not-a-continuation-fixture-'+uuid.uuid4().hex)
    with pytest.raises(ValueError,match='BEFORE_IO'):Custody(foreign)
    assert not foreign.exists()
