"""Approved real Windows native fixture roots only;no operational resources."""
import os
import uuid
from pathlib import Path

import pytest
from app.services.paper_financial_replay import strict
from continuation_fixture import manifests, records
from native_continuation_session_fixture import canonical_records, case, ledger

ROOT=Path(os.environ['ATLAS_NATIVE_CONTINUATION_SESSION_ROOT'])


def test_native_smoke_creation_projection_and_same_scope_rollover():
    b,p,a=case(ROOT,'smoke-'+uuid.uuid4().hex)
    m=manifests()['QUALITY_DIPS'];commands=[strict(r['command']) for r in records()['QUALITY_DIPS'][:4]]
    rows=canonical_records(m,commands)
    store=ledger(b,p,a,'QD',m)
    try:
        store.create()
        for row in rows[:2]:store.append(row)
        before={x.name:x.read_bytes() for x in (store.base/'segment-0').iterdir()}
        cut=store.rollover()
        assert cut['global_revision']==2 and cut['local_revision']==0
        for row in rows[2:]:store.append(row)
        view=store.read()
        assert view['global_revision']==4 and view['local_revision']==2
        assert all((store.base/'segment-0'/name).read_bytes()==value for name,value in before.items())
        assert not view['startup_authorized']
    finally:store.close()

import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal

from native_continuation_session_fixture import Pins

from scripts.observation_runtime.native_fixture_budget import (
    BudgetRefused,
    NativeFixtureBudget,
)


def setup(name):
    b,p,a=case(ROOT,name+'-'+uuid.uuid4().hex);m=manifests()['QUALITY_DIPS']
    s=ledger(b,p,a,'QD',m);s.create()
    return b,p,a,m,s


def test_full_128_native_boundary_and_global_accounting():
    _b,_p,_a,m,s=setup('capacity')
    rows=canonical_records(m,[strict(r['command']) for r in records()['QUALITY_DIPS']])
    try:
        for row in rows[:128]:s.append(row)
        before={x.name:x.read_bytes() for x in (s.base/'segment-0').iterdir()}
        with pytest.raises(ValueError,match='LOCAL128'):s.append(rows[128])
        s.rollover()
        for row in rows[128:]:s.append(row)
        view=s.read()
        assert view['global_revision']==132 and view['local_revision']==4
        assert all(Decimal(x['remaining'])==0 for x in view['state']['state']['positions'].values())
        assert all((s.base/'segment-0'/n).read_bytes()==v for n,v in before.items())
        assert s.append(rows[0])==view
        with pytest.raises(ValueError,match='TWO_SEGMENTS'):s.rollover()
    finally:s.close()


@pytest.mark.parametrize('phase',['before_intent','intent','record','commit','projection','ack','current_ack'])
def test_abrupt_native_child_restart(phase):
    b,p,a,m,s=setup('crash');s.close()
    run=subprocess.run([sys.executable,str(Path(__file__).with_name('native_continuation_session_child.py')),str(ROOT),str(p),phase],capture_output=True,timeout=60,check=False)
    assert run.returncode==73,run.stderr.decode()
    restart=ledger(b,p,a,'QD',m)
    try:
        if phase in ('before_intent','current_ack'):
            assert restart.read()['global_revision']==(0 if phase=='before_intent' else 1)
        else:
            with pytest.raises(ValueError):restart.read()
            with pytest.raises(ValueError):restart.append(canonical_records(m,[strict(records()['QUALITY_DIPS'][0]['command'])])[0])
    finally:restart.close()


@pytest.mark.parametrize('phase',['before_prepare','prepared','selected'])
def test_rollover_interruption(phase):
    b,p,a,m,s=setup('roll-crash')
    def fail(stage):
        if stage==phase:raise RuntimeError('INJECTED')
    try:
        with pytest.raises(RuntimeError):s.rollover(fault=fail)
    finally:s.close()
    r=ledger(b,p,a,'QD',m)
    try:
        if phase=='prepared':
            with pytest.raises(ValueError):r.read()
        else:assert r.read()['global_revision']==0
    finally:r.close()


def test_concurrent_exact_owned_children_duplicate_publication():
    b,p,a,m,s=setup('concurrent');s.close()
    cmd=[sys.executable,str(Path(__file__).with_name('native_continuation_session_child.py')),str(ROOT),str(p),'never']
    with ThreadPoolExecutor(max_workers=2) as pool:runs=list(pool.map(lambda _:subprocess.run(cmd,capture_output=True,timeout=60,check=False),range(2)))
    assert [r.returncode for r in runs]==[0,0],[r.stderr.decode() for r in runs]
    r=ledger(b,p,a,'QD',m)
    try:assert r.read()['global_revision']==1
    finally:r.close()


@pytest.mark.parametrize('damage',['bytes','hardlink','foreign-pin','unavailable-custody','revocation'])
def test_native_evidence_refusal(damage):
    b,p,a,m,s=setup('damage')
    s.append(canonical_records(m,[strict(records()['QUALITY_DIPS'][0]['command'])])[0])
    target=s.base/'segment-0'/'0001-record.json'
    try:
        if damage=='bytes':
            with b.mutation(target,entries=0,size=target.stat().st_size+1):target.write_bytes(target.read_bytes()+b' ')
        elif damage=='hardlink':
            with b.mutation(p/'extra-link'):os.link(target,p/'extra-link')
        elif damage=='foreign-pin':
            old=s.custody.current();old['scope']='0'*64;b.write(s.custody.path,__import__('json').dumps(old).encode(),replace=True)
        elif damage=='unavailable-custody':s.custody.available=False
        else:a.valid=False
        with pytest.raises((ValueError,OSError)):s.read()
    finally:s.close()


def test_perp_native_funding_partial_close_and_replay():
    b,p,a=case(ROOT,'perp-'+uuid.uuid4().hex);m=manifests()['HYPERLIQUID'];s=ledger(b,p,a,'PERP',m)
    rows=canonical_records(m,[strict(r['command']) for r in records()['HYPERLIQUID']])
    try:
        s.create()
        for row in rows:s.append(row)
        v=s.read();assert v['global_revision']==4
        assert all(Decimal(x['remaining'])==0 for x in v['state']['state']['positions'].values())
        s.rollover();assert s.read()['state']==v['state']
    finally:s.close()


@pytest.mark.parametrize('boundary',['time','entries','bytes'])
def test_programmatic_budget_refuses_before_effect(monkeypatch,boundary):
    b=NativeFixtureBudget(ROOT);target=ROOT/'evidence'/('must-not-exist-'+uuid.uuid4().hex)
    if boundary=='time':
        monkeypatch.setattr('scripts.observation_runtime.native_fixture_budget.time.monotonic_ns',lambda:b.anchor['started_monotonic_ns']+1800*10**9)
    else:
        usage=b.usage();usage['entries' if boundary=='entries' else 'charged_bytes']=8192 if boundary=='entries' else 256*1024*1024
        monkeypatch.setattr('scripts.observation_runtime.native_fixture_budget.json.loads',lambda _:usage)
    with pytest.raises(BudgetRefused):b.write(target,b'x')
    assert not target.exists()

from app.services.paper_financial_replay import digest
from native_continuation_session_fixture import SwitchStatus

from scripts.volume_inspector.native_continuation_fixture import NativeSwitchFixture


def make_switch():
    from app.services.perp_resting_order import transition
    from app.services.unified_portfolio_custody import portfolio_transition
    b,p,a=case(ROOT,'switch-'+uuid.uuid4().hex);ms=manifests();journals={}
    for role,lane in [('QD_SOURCE','QUALITY_DIPS'),('PERP_SOURCE','HYPERLIQUID')]:
        journals[role]=ledger(b,p,a,role,ms[lane]);journals[role].create()
    for role,lane in [('QD_REPORT','QUALITY_DIPS'),('PERP_REPORT','HYPERLIQUID')]:
        def report_fold(rows,m=ms[lane]):
            from app.services.paper_daily_report import audit_daily_report
            from app.services.paper_financial_replay import replay_verified_events
            for row in rows:
                state,_,_=replay_verified_events(m,row['rows'])
                audit_daily_report(row['report'],row['scope'],m,row['pin'],row['rows'],state)
            return {'reports':rows}
        journals[role]=ledger(b,p,a,role,ms[lane],projected=False,kind='REPORT',derive=report_fold);journals[role].create()
    m=ms['HYPERLIQUID']
    def orders(rows):
        state={'revision':0,'last_clock':m['opened_at'],'orders':{}}
        for row in rows:state=transition({},m,state,row)
        return state
    def global_fold(rows):
        state={'revision':0,'last_clock':m['opened_at'],'session':None,'entry_closed':True,'sessions':[],'operations':{},'finalized':None}
        for row in rows:state=portfolio_transition({},m,state,row)
        return state
    journals['PERP_ORDERS']=ledger(b,p,a,'PERP_ORDERS',m,projected=False,kind='ORDERS',derive=orders)
    journals['GLOBAL']=ledger(b,p,a,'GLOBAL',m,projected=False,kind='GLOBAL',derive=global_fold)
    for k in ('PERP_ORDERS','GLOBAL'):journals[k].create()
    now=m['opened_at'];g=journals['GLOBAL']
    for kind,payload in [('SESSION',{'grant_digest':'synthetic-grant','session_id':'synthetic-session'}),('CLOSE',{'grant_digest':'synthetic-grant'}),('FINAL',{'grant_digest':'synthetic-grant','outcomes':{lane:{'state':'ACKNOWLEDGED_FLAT_AND_DRAINED'} for lane in ms}})]:
        g.append({'kind':kind,'order_id':'synthetic-'+kind,'at':now,'payload':payload})
    from datetime import datetime
    from zoneinfo import ZoneInfo

    from app.services.paper_daily_report import build_daily_report
    for role,lane in [('QD_REPORT','QUALITY_DIPS'),('PERP_REPORT','HYPERLIQUID')]:
        mm=ms[lane];scope={'schema':'FS3_REPORT_SCOPE_V1','account_id':'SYNTHETIC-'+lane,'epoch':mm['epoch'],'policy_digest':digest(mm),'timezone':mm['timezone']}
        pin={'epoch':mm['epoch'],'entries':[],'root':'SYNTHETIC-LOGICAL-COMPLETE-SOURCE','inception':digest(mm)}
        day=datetime.fromtimestamp(mm['opened_at'],ZoneInfo(mm['timezone'])).date().isoformat()
        report=build_daily_report(scope,mm,pin,[],day,mm['opened_at']+86400)
        journals[role].append({'scope':scope,'pin':pin,'rows':[],'report':report})
    switch=NativeSwitchFixture(base=p/'catalog',budget=b,custody=Pins(b,p/'custody','catalog'),status=SwitchStatus(b,p/'custody'/'switch-status.json'),authority=a,journals=journals)
    return switch,journals


@pytest.mark.parametrize('phase',['success','reserved','commit','selected:QD_SOURCE','catalog'])
def test_complete_role_catalog_switch_and_unknown_barrier(phase):
    switch,journals=make_switch()
    try:
        if phase=='success':
            result=switch.switch();assert result['status']=='ACKNOWLEDGED'
            assert all(len(v['pin']['segments'])==2 for v in result['cuts'].values())
            assert switch.switch()==result
        else:
            def fail(stage):
                if stage==phase:raise RuntimeError('INTERRUPTED_SWITCH')
            with pytest.raises(RuntimeError):switch.switch(fault=fail)
            assert switch.inspect()['status']=='UNKNOWN'
            for journal in journals.values():
                with pytest.raises(ValueError):journal.read()
    finally:
        switch.close()
        for journal in journals.values():journal.close()
