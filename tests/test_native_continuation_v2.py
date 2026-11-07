"""Seven approved V2 groups;synthetic native resources only."""
import copy
import hashlib
import os
import uuid
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest
from app.services.paper_financial_replay import body, digest, strict
from native_continuation_v2_fixture import ROOT, Suite, new_suite
from native_continuation_v2_owned import OwnedChild, owned_junction

from scripts.observation_runtime.native_fixture_budget import (
    BudgetRefused,
    NativeFixtureBudget,
)
from scripts.volume_inspector.native_continuation_fixture import f


def hashes(path):
    return {str(p.relative_to(path)):hashlib.sha256(p.read_bytes()).hexdigest() for p in path.rglob('*') if p.is_file()}


def test_populated_two_currency_rollover_and_projection_report_parity():
    s=new_suite()
    try:
        before={k:j.read() for k,j in s.j.items()};original={k:hashes(j.base) for k,j in s.j.items()}
        cut=s.switch.switch();assert cut['status']=='ACKNOWLEDGED'
        assert s.switch.switch()==cut
        for k,j in s.j.items():
            after=j.read();assert after['state']==before[k]['state'] and after['rows']==before[k]['rows']
            assert after['global_revision']==before[k]['global_revision'] and after['local_revision']==0
            assert all(hashes(j.base)[name]==value for name,value in original[k].items())
        qd=s.j['QD_SOURCE'].read()['state']['state'];perp=s.j['PERP_SOURCE'].read()['state']['state']
        assert {k:Decimal(qd[k]) for k in ('cash','gross','costs','net')}=={'cash':Decimal('1015.9136'),'gross':Decimal(16),'costs':Decimal('0.0864'),'net':Decimal('15.9136')}
        assert Decimal(perp['cash'])==Decimal(1000)+Decimal(perp['net'])
        assert all(Decimal(p['remaining'])==0 for p in qd['positions'].values())
        assert all(Decimal(p['remaining_entry_costs'])==0 for p in qd['positions'].values())
        assert all(Decimal(p['remaining'])==0 for p in perp['positions'].values())
        assert Decimal(perp['reserved_margin'])==0
        assert [len(before[k]['state']['reports']) for k in ('QD_REPORT','PERP_REPORT')]==[3,2]
        for k in ('QD_SOURCE','PERP_SOURCE'):
            assert s.j[k].append(before[k]['rows'][0])==s.j[k].read()
        order=s.j['PERP_ORDERS'];old=order.read();assert old['state']['orders']['synthetic-cancelled-order']['state']=='CANCELLED'
        assert old['state']['orders']['synthetic-filled-order']['state']=='ACKNOWLEDGED'
        assert order.append(old['rows'][0])==old
        conflicting=copy.deepcopy(old['rows'][0]);conflicting['at']=8000;conflicting['payload']['created_at']=8000;conflicting['payload']['expires_at']=9000
        with pytest.raises(ValueError):order.append(conflicting)
        new_order=copy.deepcopy(old['rows'][0]['payload']);new_order.update(order_id='SYNTHETIC-SUCCESSOR-CANCEL',created_at=8000,expires_at=9000)
        order.append({'kind':'ARM','order_id':new_order['order_id'],'at':8000,'payload':new_order})
        order.append({'kind':'CANCEL','order_id':new_order['order_id'],'at':8001,'payload':{'reason':'NO_FINANCIAL_EFFECT'}})
        assert order.read()['global_revision']==7 and order.read()['local_revision']==2
        assert order.read()['state']['orders']['synthetic-filled-order']==old['state']['orders']['synthetic-filled-order']
        # Native successor receives a new report revision without financial effects.
        report=s.j['QD_REPORT'];row=copy.deepcopy(report.read()['rows'][-1]);row['revision']=4
        report.append(row);assert report.read()['local_revision']==1 and report.read()['global_revision']==4
        with pytest.raises(ValueError):s.switch.inspect() # old switch receipt is not the advanced current cut
        s.b.write(ROOT/'evidence'/('accounting-parity-'+s.path.name+'.json'),body({'QD':qd,'PERP':perp,'report_counts':[3,2],'startup_authorized':False}).encode())
    finally:s.close()


PHASES=['before_reservation','reserved','intent']+['prepared:'+r for r in ('QD_SOURCE','PERP_SOURCE','QD_REPORT','PERP_REPORT','PERP_ORDERS','GLOBAL')]+['record','commit']+['selected:'+r for r in ('QD_SOURCE','PERP_SOURCE','QD_REPORT','PERP_REPORT','PERP_ORDERS','GLOBAL')]+['ack','catalog','admitted']


@pytest.mark.parametrize('phase',PHASES)
def test_exact_child_catalog_death_and_fresh_restart(phase):
    s=new_suite();path=s.path;before={k:hashes(j.base) for k,j in s.j.items()};s.close()
    child=OwnedChild(path,'switch',phase);code,_out,err=child.finish();assert code==73,err.decode()
    observer=OwnedChild(path,'inspect');code,out,err=observer.finish();assert code==0,err.decode()
    value=strict(out.decode())
    if phase=='before_reservation':
        assert value['status']=='UNSELECTED'
    elif phase=='admitted':assert value['status']=='ACKNOWLEDGED'
    else:assert value['status']=='UNKNOWN'
    r=Suite(path)
    try:
        if phase not in ('before_reservation','admitted'):
            for journal in r.j.values():
                with pytest.raises(ValueError):journal.read()
            with pytest.raises(ValueError):r.switch.switch()
        for k,j in r.j.items():assert all(hashes(j.base)[n]==v for n,v in before[k].items())
    finally:r.close()


@pytest.mark.parametrize('damage',['old-marker','missing-marker-field','partial-pin','foreign-scope','root-map','source-revision','revoked','clock','custody-unavailable'])
def test_inconsistent_native_current_cut_refuses(damage):
    s=new_suite()
    try:
        s.switch.switch();path=s.path/'custody'/'switch-status.json';marker=strict(path.read_text())
        if damage=='old-marker':marker['catalog']=digest('stale')
        elif damage=='missing-marker-field':marker.pop('catalog')
        elif damage=='partial-pin':
            pin=s.switch.custody.current();pin['selection'].pop('commit');s.b.write(s.switch.custody.path,body(pin).encode(),replace=True);marker['catalog']=digest(pin)
        elif damage in ('foreign-scope','root-map','source-revision'):
            pin=s.j['QD_SOURCE'].custody.current()
            if damage=='foreign-scope':pin['scope']=digest('foreign')
            elif damage=='root-map':pin['segments'][-1]['root']=[99,99,99]
            else:pin['segments'][0]['entries'].pop()
            s.b.write(s.j['QD_SOURCE'].custody.path,body(pin).encode(),replace=True)
        elif damage=='revoked':s.a.valid=False
        elif damage=='clock':s.a.clock_valid=False
        else:s.switch.custody.available=False
        s.b.write(path,body(marker).encode(),replace=True)
        try:value=s.switch.inspect()
        except (ValueError,KeyError):value={'status':'UNKNOWN'}
        assert value['status']=='UNKNOWN'
    finally:s.close()


def test_complete_actual_roster_with_retained_child_and_all_exclusions():
    from app.services.unified_writer_roster import (
        EXCLUSIONS,
        ROLES,
        UnifiedWriterRoster,
        validate_roster,
    )
    s=new_suite();child=OwnedChild(s.path,'hold')
    try:
        observed=strict(child.p.stdout.readline().decode());assert observed==child.id;child.verify()
        resources={k:s.j[k].read()['pin']['segments'][0]['root'] for k in s.j}
        mapping={'QD_SOURCE':'QD_SOURCE','QD_PROJECTION':'QD_SOURCE','QD_REPORT':'QD_REPORT','PERP_SOURCE':'PERP_SOURCE','PERP_PROJECTION':'PERP_SOURCE','PERP_REPORT':'PERP_REPORT','PERP_ORDERS':'PERP_ORDERS','PERP_FUNDING':'PERP_SOURCE','PERP_MARK':'PERP_SOURCE','GLOBAL_CUSTODY':'GLOBAL'}
        roles={}
        for role in ROLES:
            key=mapping.get(role);resource=resources[key] if key else s.aux_bindings[role]['root']
            if role.endswith('PROJECTION'):resource=s.j[key].read()['pin']['segments'][0]['projection']['root']
            roles[role]={'writer_id':'SYNTHETIC-'+role,'process':child.id,'resource':resource}
        writers={lane:SimpleNamespace(manifest=m) for lane,m in s.ms.items()};now=[9000]
        enrollment={'schema':'ATLAS_UNIFIED_WRITER_RESOURCES_V1','session_id':'synthetic-session','account_binding':digest({k:digest(w.manifest) for k,w in writers.items()}),'writer_binding':digest(roles),'roles':roles,'exclusions':{k:'SYNTHETIC-EXCLUDED-'+k for k in EXCLUSIONS}}
        observation={'schema':'ATLAS_UNIFIED_WRITER_OBSERVATION_V1','observed_at':9000,'roles':copy.deepcopy(roles),'unknown_writers':[],'active_operations':dict.fromkeys(ROLES,0),'unknown_operations':False}
        def read(_):child.verify();return copy.deepcopy(observation)
        authority=SimpleNamespace(verify_enrollment=lambda *_:True,verify_observation=lambda *_:True,verify_drain=lambda *_:True)
        roster=UnifiedWriterRoster(enrollment=enrollment,writers=writers,observer=SimpleNamespace(read=read),authority=authority,clock=lambda:now[0]);grant={'session_id':'synthetic-session'}
        assert roster.drain(grant,writers,9000)
        with roster.lease(grant,writers,9000) as lease:assert lease.check()
        for role in ROLES:
            observation['active_operations'][role]=1;assert not roster.drain(grant,writers,9000);observation['active_operations'][role]=0
        for excluded in EXCLUSIONS:
            observation['unknown_writers']=[excluded]
            with pytest.raises(ValueError):roster.drain(grant,writers,9000)
            observation['unknown_writers']=[]
        for mutation in ('missing-role','duplicate-writer','changed-incarnation','foreign-root','stale','unknown-operation'):
            saved=copy.deepcopy(observation)
            if mutation=='missing-role':observation['roles'].pop('QD_SOURCE')
            elif mutation=='duplicate-writer':
                bad=copy.deepcopy(enrollment);bad['roles']['QD_SOURCE']['writer_id']=bad['roles']['PERP_SOURCE']['writer_id']
                with pytest.raises(ValueError):validate_roster(bad)
                continue
            elif mutation=='changed-incarnation':observation['roles']['QD_SOURCE']['process']['created']+=1
            elif mutation=='foreign-root':observation['roles']['QD_SOURCE']['resource']=[99,99,99]
            elif mutation=='stale':observation['observed_at']=8990
            else:observation['unknown_operations']=True
            with pytest.raises(ValueError):roster.drain(grant,writers,9000)
            observation.clear();observation.update(saved)
        assert roster.owned_roster(grant,writers,9000)['processes']==[child.id]
        assert child.finish(input=b'close\n')[0]==0
    finally:
        if child.p.poll() is None:child.finish(input=b'close\n')
        s.close()


@pytest.mark.parametrize('kind',['junction','symlink'])
def test_confined_native_namespace_probe(kind):
    b=NativeFixtureBudget(ROOT);base=ROOT/'attacks'/('probe-'+uuid.uuid4().hex);b.directory(base);target=base/'target';links=base/'links';b.directory(links)
    b.directory(target,native_factory=f.w.WindowsOutput.create_root)
    out=f.w.WindowsOutput(str(target))
    try:binding=b.native_write(out,'sentinel.json',b'{"synthetic":true}')
    finally:out.close()
    before=hashes(target);link=links/'owned-link'
    try:
        with b.mutation(link):
            if kind=='symlink':os.symlink(target,link,target_is_directory=True)
            else:
                code,_out,err,receipt=owned_junction(link,target,b)
                assert code==0,err.decode(errors='replace')
        if kind=='junction':b.write(ROOT/'evidence'/('junction-child-'+str(receipt['process']['pid'])+'.json'),body(receipt).encode())
        raw=os.readlink(link);normalized=raw.removeprefix('\\\\?\\')
        assert Path(normalized)==target
        with pytest.raises((ValueError,OSError)):f.w.WindowsOutput(str(link))
        with pytest.raises(BudgetRefused):b.write(link/'escaped.json',b'x')
        assert before==hashes(target)
        reader=f.w.WindowsOutput(str(target))
        try:assert f.s.read_bound(reader,'sentinel.json',binding)[0]==b'{"synthetic":true}'
        finally:reader.close()
    except OSError as exc:
        if kind=='symlink' and getattr(exc,'winerror',None)==1314:
            b.write(ROOT/'evidence'/'symlink-not-executed.json',body({'status':'NOT_EXECUTED','winerror':1314}).encode());pytest.skip('NOT EXECUTED:Windows symlink privilege unavailable')
        raise
    finally:
        if link.is_symlink() or link.is_junction():
            assert Path(os.readlink(link).removeprefix('\\\\?\\'))==target
            os.rmdir(link) if link.is_junction() else link.unlink()
        assert before==hashes(target)


def test_concurrent_catalog_requests_select_one_cut():
    s=new_suite();path=s.path;s.close()
    children=[OwnedChild(path,'switch') for _ in range(2)]
    for child in children:
        code,out,err=child.finish();assert code==0,(out,err)
    r=Suite(path)
    try:
        result=r.switch.inspect();assert result['status']=='ACKNOWLEDGED'
        assert all(len(v['pin']['segments'])==2 for v in result['cuts'].values())
        assert {k:v['global_revision'] for k,v in result['cuts'].items()}=={'QD_SOURCE':3,'PERP_SOURCE':4,'QD_REPORT':3,'PERP_REPORT':2,'PERP_ORDERS':5,'GLOBAL':3}
    finally:r.close()


def test_pending_orders_block_switch_without_financial_replay():
    s=new_suite()
    try:
        journal=s.j['PERP_ORDERS'];first=copy.deepcopy(journal.read()['rows'][0]['payload'])
        first.update(order_id='SYNTHETIC-PENDING',created_at=8000,expires_at=9000)
        journal.append({'kind':'ARM','order_id':first['order_id'],'at':8000,'payload':first})
        with pytest.raises(ValueError,match='RESTING_ORDER'):s.switch.switch()
        command=strict(s.rows['HYPERLIQUID'][0]['command']);command.update(operation_id='synthetic-uncertain-fill',origin_ref=first['order_id'],timestamp=8001,expected_source_revision=4)
        command['evidence'].update(observed_at=8001,sequence='synthetic-pending')
        command['evidence']['maker_execution'].update(order_id=first['order_id'],rested_at=8000,trade_at=8001)
        journal.append({'kind':'FILL_PENDING','order_id':first['order_id'],'at':8001,'payload':command})
        with pytest.raises(ValueError,match='RESTING_ORDER'):s.switch.switch()
        with pytest.raises(ValueError):journal.append({'kind':'CANCEL','order_id':first['order_id'],'at':8002,'payload':{'reason':'NO_FINANCIAL_EFFECT'}})
        assert s.j['PERP_SOURCE'].read()['global_revision']==4
    finally:s.close()



def test_restart_missing_control_lock_refuses_without_repair():
    s=new_suite();path=s.path;b=s.b;s.close();lock=path/'custody'/'QD_SOURCE-lock';saved=lock.with_name('retained-original-lock')
    with b.mutation(saved,entries=0):lock.rename(saved)
    before=hashes(path)
    with pytest.raises(BudgetRefused):Suite(path)
    assert not lock.exists() and saved.exists() and hashes(path)==before
