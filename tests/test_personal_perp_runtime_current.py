"""Source-only current-reader contracts. All native ports are offline mocks."""
import copy
from contextlib import contextmanager, nullcontext
from types import SimpleNamespace

import pytest

from app.services.paper_daily_report import audit_daily_report
from app.services.paper_financial_replay import body, digest, initial_state
from app.services.personal_current_pins import PersonalCurrentPins
from test_personal_paper_inception_memory import system
from scripts.observation_runtime import personal_perp_runtime_current as target


@pytest.fixture
def model(monkeypatch):
    s = system('HYPERLIQUID')
    ready = s.pub.publish()['current']
    db = s.ledger.db
    db.execute('CREATE TABLE projections(id TEXT PRIMARY KEY,receipt TEXT)')
    db.execute('CREATE TABLE personal_current(name TEXT PRIMARY KEY,body TEXT,generation INTEGER)')
    db.executemany('INSERT INTO personal_current VALUES(?,?,0)',
                   [('source',body(ready['source'])),('reports',body(ready['reports']))])
    db.commit()
    class Images: pass
    s.ledger.images, s.ledger.manifest = Images(), s.m
    s.ledger.read_view = nullcontext
    s.ledger._load = lambda db: None
    class Operator:
        _lane = 'HYPERLIQUID'
        def __init__(self):
            self.enrollment, self.clock = s.n, lambda:s.now[0]
            self.calls = []
        def activation(self, action):
            assert action == 'READ_ONLY'
            self.calls.append(action)
            return {'action':action}
    class Ownership:
        read_only = True
        def __init__(self, operator):
            self.authority, self.enrollment, self.ledger = operator, s.n, s.ledger
            self.requests = []
        @contextmanager
        def lease(self, request, now):
            assert request['schema']=='PERSONAL_NATIVE_READ_LEASE_V1'
            assert request['reader_enrollment']['schema']=='PERP_AUTO_OP_READ_ENROLLMENT_V1'
            self.requests.append(copy.deepcopy(request))
            yield SimpleNamespace(snapshot={'mock':True},check=lambda *_:True)
    monkeypatch.setattr(target,'NativePersonalOperatorAuthority',Operator)
    monkeypatch.setattr(target,'NativePersonalWriterOwnership',Ownership)
    monkeypatch.setattr(target,'PersonalNativeCoordination',type(s.ledger))
    monkeypatch.setattr(target,'NativePersonalCoordinationImages',Images)
    operator=Operator();ownership=Ownership(operator)
    source=PersonalCurrentPins(ledger=s.ledger,name='source',clock=operator.clock)
    reports=PersonalCurrentPins(ledger=s.ledger,name='reports',clock=operator.clock)
    authority=target.NativePersonalPerpReadAuthority(
        operator=operator,ownership=ownership,source=source,reports=reports)
    documents=[copy.deepcopy(s.files.values['report','0001-report.json'])]
    class Projection: pass
    monkeypatch.setattr(target,'ProjectionTarget',Projection)
    class Store:
        def __init__(self):
            self.enrollment,self.trust,self.authority=s.n,source,authority
            self.projection=Projection()
        def verified_cut(self):
            request={'schema':'PERP_AUTO_OP_ADMISSION_REQUEST_V1',
                     'enrollment':self.enrollment,'current':source.current(),'command':None}
            with authority.lease(request,s.now[0]) as lease:
                assert lease.check(lease.snapshot,s.now[0])
                return {'manifest':s.m,'root':source.current()['root'],
                        'pin_schema':source.current()['schema'],
                        'state':initial_state(s.m),'head':digest(s.m)}
    class Archive:
        def __init__(self):
            self.enrollment,self.trust,self.authority=s.n,reports,authority
            self.clock=operator.clock
    class Reporting:
        def __init__(self,store):self.store,self.archive=store,Archive()
        def history(self):
            request={'schema':'PERP_AUTO_OP_REPORT_REQUEST_V1','enrollment':s.n,
                     'current':reports.current(),'action':'READ'}
            with authority.lease(request,s.now[0]):
                pin=source.current()
                logical={'epoch':s.n['epoch'],'entries':[],
                         'root':pin['root'],'inception':pin['inception']}
                for doc in documents:
                    audit_daily_report(doc['report'],s.scope,s.m,logical,[],initial_state(s.m))
                return copy.deepcopy(documents)
    monkeypatch.setattr(target,'OperationalPerpStore',Store)
    monkeypatch.setattr(target,'OperationalPerpReportArchive',Archive)
    monkeypatch.setattr(target,'OperationalPerpReportService',Reporting)
    store=Store();reporting=Reporting(store)
    current=target.PersonalPerpRuntimeCurrent(bootstrap=s.b,source=source,reports=reports,
                                            store=store,reporting=reporting,clock=operator.clock)
    yield SimpleNamespace(**locals())
    s.ledger.db.close()


def test_existing_current_capture_is_readonly_and_reaudits_reports(model):
    before=model.db.total_changes
    result=model.current.capture()
    assert result['source_revision']==0 and result['report_revision']==0
    assert result['financial_write_authority'] is False
    assert model.db.total_changes==before
    assert set(model.operator.calls)=={'READ_ONLY'}


def test_append_only_audited_report_is_accepted_without_rerunning_initial_reader(model):
    first=model.current.capture()
    doc=copy.deepcopy(model.documents[0]);doc['revision']=2
    old=model.reports.current();doc['previous']=old['reports'][-1]
    model.documents.append(doc)
    new=copy.deepcopy(old);new['reports'].append({'id':[1,500,0],'sha256':digest(doc)})
    model.db.execute('UPDATE personal_current SET body=?,generation=1 WHERE name=?',(body(new),'reports'))
    model.db.commit()
    second=model.current.capture()
    assert second['source']==first['source'] and second['report_revision']==1
    assert second['genesis_ack_digest']==first['genesis_ack_digest']


@pytest.mark.parametrize('kind',['source-write','report-write','extra-field','foreign-account'])
def test_read_authority_cannot_be_promoted_to_financial_or_report_writer(model,kind):
    req={'schema':'PERP_AUTO_OP_ADMISSION_REQUEST_V1','enrollment':model.s.n,
         'current':model.source.current(),'command':None}
    if kind=='source-write':req['command']={'operation':'UNAUTHORIZED'}
    elif kind=='report-write':
        req={'schema':'PERP_AUTO_OP_REPORT_REQUEST_V1','enrollment':model.s.n,
             'current':model.reports.current(),'action':'PUBLISH'}
    elif kind=='extra-field':req['authority']=True
    else:req['enrollment']={**model.s.n,'account_id':'FOREIGN'}
    before=model.db.total_changes
    with pytest.raises(ValueError),model.authority.lease(req,model.s.now[0]):
        pytest.fail('READ_ONLY_PORT_GRANTED_WRITE')
    assert model.db.total_changes==before


@pytest.mark.parametrize('damage',['pending','unknown','pin-generation','foreign-source',
                                  'manifest','incomplete-reports','component','projection','authority'])
def test_missing_conflicting_or_incomplete_current_evidence_refuses(model,damage):
    if damage in ('pending','unknown'):
        model.db.execute('UPDATE personal_publications SET state=?',(damage.upper(),))
    elif damage=='pin-generation':
        model.db.execute("UPDATE personal_current SET generation=1 WHERE name='source'")
    elif damage=='foreign-source':
        pin=model.source.current();pin['root']=[9,99,0]
        model.db.execute("UPDATE personal_current SET body=? WHERE name='source'",(body(pin),))
    elif damage=='manifest':model.s.m['opening_cash']='1001'
    elif damage=='incomplete-reports':model.documents.clear()
    elif damage=='projection':model.store.projection=object()
    elif damage=='authority':model.store.authority=object()
    else:model.current.store=object()
    model.db.commit()
    with pytest.raises(ValueError):model.current.capture()


def test_expired_read_lease_refuses_without_a_delivery_or_commit_ack(model):
    req={'schema':'PERP_AUTO_OP_ADMISSION_REQUEST_V1','enrollment':model.s.n,
         'current':model.source.current(),'command':None}
    with pytest.raises(ValueError,match='LEASE_CHANGED'):
        with model.authority.lease(req,model.s.now[0]) as lease:
            model.s.now[0]+=6
            assert not lease.check(lease.snapshot,model.s.now[0])


def test_untyped_or_writable_ownership_refuses_before_capture(model):
    model.ownership.read_only=False
    with pytest.raises(ValueError):
        target.NativePersonalPerpReadAuthority(operator=model.operator,
            ownership=model.ownership,source=model.source,reports=model.reports)
