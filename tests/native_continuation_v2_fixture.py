"""V2 native synthetic suite;all file effects require the shared approved budget."""
import copy
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from app.services.paper_financial_replay import (
    apply_event,
    body,
    digest,
    initial_state,
    strict,
)
from continuation_fixture import manifests
from native_continuation_session_fixture import (
    Authority,
    Pins,
    SwitchStatus,
    canonical_records,
    ledger,
)

from scripts.observation_runtime.native_fixture_budget import (
    BudgetRefused,
    NativeFixtureBudget,
)
from scripts.volume_inspector.native_continuation_fixture import NativeSwitchFixture

ROOT=Path(r'D:\Work\Project Atlas\logs\diagnostics\continuation-fixture-77a93d8995474d649d7bda5095d84ab5')


def financial_inputs():
    from app.investment.quality_dips_candidate_evidence import CandidateEvidenceAdapter
    from app.services.quality_dips_autonomous_paper import AutonomousPaper
    from test_perp_financial_v2 import entry
    from test_quality_dips_autonomous_paper import STAMP, candidate, quote
    ms=manifests();m=ms['QUALITY_DIPS']
    m.update(schema='PAPER_EPOCH_AUTONOMOUS_QD_V1',epoch='SYNTHETIC-V2-CONTINUATION',opened_at=STAMP,
        cost_policy='SIDE_NOTIONAL_FEE_SLIPPAGE_V1',autonomous_policy={'schema':'QD_AUTO_RISK_PARTIAL_THESIS_V1',
        'quote_age_seconds':5,'max_spread_bps':'50','participation':'0.5','quantity_step':'0.001','partial_fraction':'0.4','max_session_seconds':3600})
    n=SimpleNamespace(now=[STAMP],m=m)
    proof=lambda schema,payload:{'schema':schema,'verified':True,'binding':digest(payload),'receipt_id':'EXPLICIT_SYNTHETIC_AUTHORITY'}
    engine=AutonomousPaper.__new__(AutonomousPaper);engine.ledger=SimpleNamespace(manifest=m);engine.entry_admission_closed=False
    engine.grant={'schema':'QD_AUTO_SESSION_FIXTURE_V1','session_id':'synthetic-session','epoch':m['epoch'],
        'issued_at':STAMP,'expires_at':STAMP+3600,'capabilities':['AUTO_ENTRY','AUTO_EXIT'],'feed_id':'synthetic-L1','calendar_id':'synthetic-NYSE-2026'}
    engine.candidates=CandidateEvidenceAdapter(ranking_authority=SimpleNamespace(verify_current=lambda v,now:proof('QD_RANKING_VERIFIED_V1',v)),execution_authority=SimpleNamespace(verify=lambda v,now:proof('QD_EXECUTION_VERIFIED_V1',v)))
    state=initial_state(m);commands=[];bundle=candidate(n)
    for index,current in enumerate([None,{'evidence_quality':'HIGH','fundamentals_score':60},{'classification':'THESIS_BROKEN'}]):
        n.now[0]=STAMP+index
        q=quote(n,bundle,bid=str(100+10*index),ask=str(100+10*index+.1)) if index else quote(n,bundle)
        obs=None if current is None else {'symbol':bundle['instrument']['symbol'],'instrument':bundle['instrument'],'observed_at':n.now[0],'current':current}
        request={'bundles':[bundle] if index==0 else [],'quotes':[q],'observation':obs}
        c=engine._decide(state,'SYNTHETIC-V2-'+str(index),request,proof('QD_AUTO_SESSION_PROOF_V1',engine.grant),proof('QD_AUTO_SOURCE_PROOF_V1',request),'RUNNING',n.now[0]);commands.append(c);state,_=apply_event(m,state,c)
    qd=canonical_records(m,commands)
    pm=ms['HYPERLIQUID'];c=entry('synthetic-filled-order')
    c.update(schema='PAPER_PERP_MAKER_FILL_V1',liquidity='MAKER')
    c['evidence']['maker_execution']={'schema':'SIMULATED_MAKER_QUEUE_FILL_V1','order_id':c['origin_ref'],'limit_price':'100','rested_at':3601,'queue_ahead':'1','traded_quantity':'10','trade_price':'100','trade_side':'SELL','trade_at':3602,'source_ref':'SYNTHETIC-EXECUTABLE-TRADE','requested_quantity':'0.5','filled_quantity':'0.5','cancelled_quantity':'0'}
    state=initial_state(pm);state,_=apply_event(pm,state,c);pid=next(iter(state['positions']));pc=[c]
    for kind,qty,stamp,op in [('EXIT','0.2',3603,'synthetic-partial'),('FUNDING',None,7201,'synthetic-funding'),('EXIT','0.3',7202,'synthetic-final')]:
        command={'schema':'PAPER_PERP_COMMAND_V2','epoch':pm['epoch'],'operation_id':op,'kind':kind,'expected_source_revision':state['revision'],'timestamp':stamp,'position_id':pid,'expected_position_revision':state['positions'][pid]['revision']}
        if kind=='FUNDING':command['evidence']={'source':'synthetic-funding','symbol':'BTC','settlement_at':7200,'interval_seconds':3600,'rate':'0.001','oracle':'100','source_id':'hour-7200'}
        else:
            ev=copy.deepcopy(entry()['evidence']);ev.update(bid='102',ask='103',observed_at=stamp,sequence=op)
            command.update(quantity=qty,liquidity='TAKER',evidence=ev)
        pc.append(command);state,_=apply_event(pm,state,command)
    return ms,{'QUALITY_DIPS':qd,'HYPERLIQUID':canonical_records(pm,pc)}


class V2Authority(Authority):
    clock_valid=True
    def verify_switch(self,*args):return self.valid and self.clock_valid and self.admitted()
    def admitted(self):
        if not self.marker.exists():return not (self.marker.parent.parent/'catalog'/'intent.json').exists()
        try:
            value=strict(self.marker.read_text());pin=strict((self.marker.parent/'catalog-pin.json').read_text())
            return value=={'status':'ACKNOWLEDGED','catalog':digest(pin)}
        except (ValueError,OSError):return False


class Suite:
    def __init__(self,path,*,create=False):
        self.b=NativeFixtureBudget(ROOT);self.path=Path(path)
        if not self.path.is_relative_to(ROOT/'native'):raise ValueError('EXACT_CASE_CONFINEMENT')
        if create:
            if (ROOT/'evidence'/'session-complete.json').exists():raise ValueError('V2_SESSION_ALREADY_CONSUMED')
            if self.b.check()>=1500:raise BudgetRefused('TEST_ADMISSION_CLOSED')
            self.b.directory(self.path);self.b.directory(self.path/'custody')
            ms,rows=financial_inputs();self.b.write(self.path/'spec.json',body({'manifests':ms,'rows':rows}).encode())
        self.b.confined_path(self.path/'spec.json')
        if not create:
            for name in ('QD_SOURCE','PERP_SOURCE','QD_REPORT','PERP_REPORT','PERP_ORDERS','GLOBAL','catalog'):
                self.b.confined_path(self.path/'custody'/(name+'-pin.json'));self.b.confined_path(self.path/'custody'/(name+'-lock'))
        spec=strict((self.path/'spec.json').read_text());self.ms,self.rows=spec['manifests'],spec['rows']
        self.aux={}
        aux_pin=self.path/'aux-pin.json'
        if create:
            from scripts.volume_inspector.native_continuation_fixture import (
                BoundedOutput,
                f,
            )
            bindings={}
            for role in ('QD_DECISION','QD_COORDINATION','QD_RANKING_PUBLICATION','PERP_MARKET_PUBLICATION','SESSION_RESERVATION'):
                target=self.path/('AUX-'+role);self.b.directory(target,native_factory=f.w.WindowsOutput.create_root)
                output=BoundedOutput(f.w.WindowsOutput(str(target)),self.b);self.aux[role]=output
                bindings[role]={'root':f.native.file_identity(output.root_handle),'file':output.write_bound('resource.json',f.encoded({'role':role,'state':'SYNTHETIC_CLOSED_DRAINED','revision':1}))}
            self.b.write(aux_pin,body(bindings).encode())
        else:
            from scripts.volume_inspector.native_continuation_fixture import (
                BoundedOutput,
                f,
            )
            for role in strict(aux_pin.read_text()):self.aux[role]=BoundedOutput(f.w.WindowsOutput(str(self.path/('AUX-'+role))),self.b)
        self.b.confined_path(aux_pin)
        self.aux_bindings=strict(aux_pin.read_text())
        self.a=V2Authority(self.path/'custody'/'switch-status.json');self.j={};self.switch=None
        for role,lane in [('QD_SOURCE','QUALITY_DIPS'),('PERP_SOURCE','HYPERLIQUID')]:self.j[role]=ledger(self.b,self.path,self.a,role,self.ms[lane])
        for role,lane in [('QD_REPORT','QUALITY_DIPS'),('PERP_REPORT','HYPERLIQUID')]:
            def reports(rows,m=self.ms[lane]):
                from app.services.paper_daily_report import audit_daily_report
                from app.services.paper_financial_replay import replay_verified_events
                for revision,row in enumerate(rows,1):
                    if row['revision']!=revision:raise ValueError('REPORT_REVISION_GAP')
                    state,_,_=replay_verified_events(m,row['rows']);audit_daily_report(row['report'],row['scope'],m,row['pin'],row['rows'],state)
                return {'reports':rows}
            self.j[role]=ledger(self.b,self.path,self.a,role,self.ms[lane],projected=False,kind='REPORT',derive=reports)
        def orders(rows):
            from app.services.perp_resting_order import transition
            m=self.ms['HYPERLIQUID'];state={'revision':0,'last_clock':m['opened_at'],'orders':{}}
            for row in rows:
                if row['kind']=='ACK':
                    c=strict(self.rows['HYPERLIQUID'][0]['command']);p=row['payload']
                    if p!={'operation_id':c['operation_id'],'payload_digest':digest(c),'financial_receipt':strict(self.rows['HYPERLIQUID'][0]['receipt'])}:raise ValueError('ORDER_FINANCIAL_ACK_UNVERIFIED')
                state=transition({},m,state,row)
            return state
        def global_fold(rows):
            from app.services.unified_portfolio_custody import portfolio_transition
            m=self.ms['HYPERLIQUID'];state={'revision':0,'last_clock':m['opened_at'],'session':None,'entry_closed':True,'sessions':[],'operations':{},'finalized':None}
            for row in rows:state=portfolio_transition({},m,state,row)
            return state
        for role,kind,fold in [('PERP_ORDERS','ORDERS',orders),('GLOBAL','GLOBAL',global_fold)]:self.j[role]=ledger(self.b,self.path,self.a,role,self.ms['HYPERLIQUID'],projected=False,kind=kind,derive=fold)
        if create:
            for journal in self.j.values():journal.create()
            for role,lane in [('QD_SOURCE','QUALITY_DIPS'),('PERP_SOURCE','HYPERLIQUID')]:
                for row in self.rows[lane]:self.j[role].append(row)
            self.seed_orders();self.seed_reports();self.seed_final()
        self.switch=NativeSwitchFixture(base=self.path/'catalog',budget=self.b,custody=Pins(self.b,self.path/'custody','catalog'),status=SwitchStatus(self.b,self.path/'custody'/'switch-status.json'),authority=self.a,journals=self.j,ownership=OwnershipMap(self))

    def seed_orders(self):
        journal=self.j['PERP_ORDERS'];m=self.ms['HYPERLIQUID'];c=strict(self.rows['HYPERLIQUID'][0]['command'])
        def order(ident):return {'schema':'PERP_RESTING_ORDER_V1','epoch':m['epoch'],'order_id':ident,'symbol':'BTC','side':'LONG','quantity':'0.5','limit_price':'100','stop_price':'99','risk_price':'1','leverage':'2','created_at':3601,'expires_at':4000,'source_id':'SYNTHETIC-DISCOVERY','source_revision':1,'source_digest':digest('SYNTHETIC-BOOK'),'session_id':'synthetic-session','plan':{'execution_policy':'STATIC_SETUP_TP1_V1','quantity_step':'0.1'}}
        events=[('ARM','synthetic-cancelled-order',3601,order('synthetic-cancelled-order')),('CANCEL','synthetic-cancelled-order',3601,{'reason':'NO_FINANCIAL_EFFECT'}),('ARM',c['origin_ref'],3601,order(c['origin_ref'])),('FILL_PENDING',c['origin_ref'],3602,c),('ACK',c['origin_ref'],3602,{'operation_id':c['operation_id'],'payload_digest':digest(c),'financial_receipt':strict(self.rows['HYPERLIQUID'][0]['receipt'])})]
        for kind,ident,at,payload in events:journal.append({'kind':kind,'order_id':ident,'at':at,'payload':payload})

    def seed_reports(self):
        from app.services.paper_daily_report import build_daily_report
        for role,lane in [('QD_REPORT','QUALITY_DIPS'),('PERP_REPORT','HYPERLIQUID')]:
            m=self.ms[lane];rows=self.rows[lane];scope={'schema':'FS3_QD_REPORT_SCOPE_V2' if lane=='QUALITY_DIPS' else 'FS3_PERP_REPORT_SCOPE_V3','account_id':'SYNTHETIC-'+lane,'epoch':m['epoch'],'policy_digest':digest(m),'timezone':m['timezone'],'session_reporting_policy':'ACKNOWLEDGED_EVENT_TIME_INCLUSIVE_CUT_V1'}
            if lane=='HYPERLIQUID':scope['funding_reporting_policy']='POSTED_CASH_AND_SETTLEMENT_ACCRUAL_V1'
            pin={'epoch':m['epoch'],'entries':[row['digest'] for row in rows],'root':'SYNTHETIC-COMPLETE-GLOBAL-HISTORY','inception':digest(m)}
            day=datetime.fromtimestamp(m['opened_at'],ZoneInfo(m['timezone'])).date()
            for index in range(2):
                date=(day+timedelta(days=index)).isoformat();observed=m['opened_at']+(index+2)*86400
                report=build_daily_report(scope,m,pin,rows,date,observed)
                self.j[role].append({'revision':index+1,'scope':scope,'pin':pin,'rows':rows,'report':report})
            if lane=='QUALITY_DIPS':
                cutoff=max(strict(r['command'])['timestamp'] for r in rows);session={'session_id':'synthetic-session','started_at':m['opened_at'],'cutoff_at':cutoff}
                report=build_daily_report(scope,m,pin,rows,day.isoformat(),cutoff+1,session=session)
                self.j[role].append({'revision':3,'scope':scope,'pin':pin,'rows':rows,'report':report})

    def seed_final(self):
        for kind,payload in [('SESSION',{'grant_digest':'synthetic-grant','session_id':'synthetic-session'}),('CLOSE',{'grant_digest':'synthetic-grant'}),('FINAL',{'grant_digest':'synthetic-grant','outcomes':{lane:{'state':'ACKNOWLEDGED_FLAT_AND_DRAINED'} for lane in self.ms}})]:self.j['GLOBAL'].append({'kind':kind,'order_id':'synthetic-'+kind,'at':8000,'payload':payload})

    def close(self):
        if self.switch:self.switch.close()
        for journal in self.j.values():journal.close()
        for output in self.aux.values():output.close()


def new_suite():return Suite(ROOT/'native'/('v2-'+uuid.uuid4().hex),create=True)


class OwnershipMap:
    """Native fixture evidence only;historical process map is not startup authority."""
    def __init__(self,suite):self.s=suite
    def resources(self,pins):
        from scripts.volume_inspector.native_continuation_fixture import f
        out={}
        for role,binding in self.s.aux_bindings.items():
            handle=self.s.aux[role]
            if f.native.file_identity(handle.root_handle)!=binding['root']:raise ValueError('AUXILIARY_ROOT_CHANGED')
            value=strict(f.s.read_bound(handle,'resource.json',binding['file'])[0].decode())
            if value!={'role':role,'state':'SYNTHETIC_CLOSED_DRAINED','revision':1}:raise ValueError('AUXILIARY_NOT_DRAINED')
            out[role]=binding['root']
        for role in ('QD_SOURCE','PERP_SOURCE','QD_REPORT','PERP_REPORT','PERP_ORDERS'):
            out[role]=pins[role]['segments'][-1]['root']
        for role in ('QD_PROJECTION','PERP_PROJECTION'):
            source=role.replace('PROJECTION','SOURCE');out[role]=pins[source]['segments'][-1]['projection']['root']
        out['PERP_FUNDING']=out['PERP_SOURCE'];out['PERP_MARK']=out['PERP_SOURCE'];out['GLOBAL_CUSTODY']=pins['GLOBAL']['segments'][-1]['root']
        return out
    def prepare(self,cuts,selected):
        from app.services.unified_writer_roster import (
            EXCLUSIONS,
            ROLES,
            validate_roster,
        )
        from native_continuation_v2_owned import self_identity
        before=self.resources({k:v['pin'] for k,v in cuts.items()});after=self.resources(selected);process=self_identity()
        roster={'schema':'ATLAS_UNIFIED_WRITER_RESOURCES_V1','session_id':'SYNTHETIC-CONTINUATION','account_binding':digest(self.s.ms),'writer_binding':digest(after),
            'roles':{k:{'writer_id':'SYNTHETIC-'+k,'resource':after[k],'process':process} for k in ROLES},'exclusions':{k:'SYNTHETIC-EXCLUDED-'+k for k in EXCLUSIONS}}
        validate_roster(roster)
        return {'schema':'NATIVE_CONTINUATION_OWNERSHIP_FIXTURE_V2','roster':roster,'before':before,'after':after,
            'aliases':{'PERP_FUNDING':'PERP_SOURCE','PERP_MARK':'PERP_SOURCE'},'drain':dict.fromkeys(ROLES,0),'unknown':False}
    def verify(self,mapping,cuts):
        from app.services.unified_writer_roster import (
            EXCLUSIONS,
            ROLES,
            validate_roster,
        )
        try:
            roster=validate_roster(mapping['roster']);resources=self.resources({k:v['pin'] for k,v in cuts.items()})
            return (set(mapping)=={'schema','roster','before','after','aliases','drain','unknown'} and mapping['schema']=='NATIVE_CONTINUATION_OWNERSHIP_FIXTURE_V2'
                and set(mapping['before'])==set(ROLES) and mapping['after']==resources
                and {k:v['resource'] for k,v in roster['roles'].items()}==resources
                and roster['account_binding']==digest(self.s.ms) and roster['writer_binding']==digest(resources)
                and set(roster['exclusions'])==set(EXCLUSIONS)
                and mapping['aliases']=={'PERP_FUNDING':'PERP_SOURCE','PERP_MARK':'PERP_SOURCE'}
                and mapping['drain']==dict.fromkeys(ROLES,0) and mapping['unknown'] is False)
        except (ValueError,KeyError,TypeError):return False
