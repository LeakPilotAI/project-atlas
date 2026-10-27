"""Personal inception recipe on existing once-only publisher/FS1/FS3;not installed."""
import importlib.util
import time
from contextlib import contextmanager
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

from app.services.paper_daily_report import audit_daily_report, build_daily_report
from app.services.paper_financial_audit import audit_financial_events
from app.services.paper_financial_replay import (
    body,
    digest,
    initial_state,
    replay_verified_events,
    strict,
    validate_manifest,
)
from app.services.personal_paper_runtime import PROFILE, validate_policy

from scripts.observation_runtime.quality_dips_one_time_publisher import OneTimePublisher


def native_primitives():
    # Existing-only native access;source tests may inject OS doubles explicitly.
    spec=importlib.util.spec_from_file_location('personal_inception_bound',Path(__file__).parents[1]/'volume_inspector/snapshot_store.py')
    native=importlib.util.module_from_spec(spec);spec.loader.exec_module(native)
    return native


def validate_personal_inception(value):
    e=strict(body(value))
    if type(e) is not dict or set(e)!={'profile','personal_policy','lane','native_enrollment','parameters','report_scope'}:raise ValueError('PERSONAL_INCEPTION_SCHEMA')
    policy=validate_policy(e['personal_policy']);lane=e['lane'];m=e['parameters']
    if lane=='QUALITY_DIPS':
        from app.services.quality_dips_autonomous_enrollment import validate_enrollment
    elif lane=='HYPERLIQUID':
        from app.services.perp_operational_contract import validate_enrollment
    else:raise ValueError('PERSONAL_INCEPTION_LANE')
    n=validate_enrollment(e['native_enrollment']);validate_manifest(m)
    if (e['profile']!=PROFILE or m['opening_cash']!='1000' or Decimal(m['initial_net_r'])!=0 or n['epoch']!=m['epoch']
            or n['inception_digest']!=digest(m) or n['release_digest']!=m['release']
            or m['schema']!=('PAPER_EPOCH_AUTONOMOUS_QD_V1' if lane=='QUALITY_DIPS' else 'PAPER_EPOCH_PERP_OPERATIONAL_V1')):
        raise ValueError('PERSONAL_INCEPTION_ACCOUNT_BINDING')
    if lane=='QUALITY_DIPS':
        if (m.get('provenance')!='ACCEPTED_AUTONOMOUS_PAPER_PARAMETERS_V1' or n['policy_digest']!=digest(m['autonomous_policy'])
                or m['fees_bps']!=policy['accounts'][lane]['fee_bps_per_side'] or m['slippage_bps']!=policy['accounts'][lane]['slippage_bps_per_side']):raise ValueError('PERSONAL_QD_PARAMETERS')
    else:
        p=m['perp_policy']
        if (m.get('provenance')!='ACCEPTED_PERP_PAPER_PARAMETERS_V1' or n['policy_digest']!=digest(p)
                or not set(p['symbols'])<=set(policy['accounts'][lane]['universe']) or Decimal(p['risk_limit'])>1
                or p['max_positions']>3 or Decimal(p['session_stop'])>Decimal(-3)):raise ValueError('PERSONAL_PERP_PARAMETERS')
    expected_scope={'schema':'FS3_QD_REPORT_SCOPE_V2' if lane=='QUALITY_DIPS' else 'FS3_PERP_REPORT_SCOPE_V3',
                    'account_id':n['account_id'],'epoch':n['epoch'],'policy_digest':digest(m),'timezone':m['timezone'],
                    'session_reporting_policy':'ACKNOWLEDGED_EVENT_TIME_INCLUSIVE_CUT_V1'}
    if lane=='HYPERLIQUID':expected_scope['funding_reporting_policy']='POSTED_CASH_AND_SETTLEMENT_ACCRUAL_V1'
    if body(e['report_scope'])!=body(expected_scope):raise ValueError('PERSONAL_REPORT_ACCOUNT_SCOPE_CONFLICT')
    return lane,n,m


def validate_initial_current(enrollment,value):
    from app.investment.quality_dips_operational_contract import hashed, native_id
    lane,n,m=validate_personal_inception(enrollment);current=strict(body(value))
    if (type(current) is not dict or set(current)!={'schema','profile','enrollment_digest','lane','source','reports',
            'state_digest','revision','acknowledged_revision','generation','status','projection'}
            or current['schema']!='PERSONAL_INITIAL_CURRENT_V1' or current['profile']!=PROFILE
            or current['enrollment_digest']!=digest(n) or current['lane']!=lane
            or current['status']!='ACKNOWLEDGED'
            or any(type(current[k]) is not int for k in ('generation','revision','acknowledged_revision'))
            or current['generation']!=1 or current['revision']!=0 or current['acknowledged_revision']!=0):
        raise ValueError('PERSONAL_INITIAL_CUT_TYPE_OR_BINDING')
    hashed(current['state_digest'])
    source,reports,projection=(current[k] for k in ('source','reports','projection'))
    if (type(source) is not dict or set(source)!={'schema','root','inception','epoch','entries'}
            or source['schema']!=('QD_AUTO_OP_PIN_V1' if lane=='QUALITY_DIPS' else 'PERP_AUTO_OP_PIN_V1')
            or source['root']!=n['resources']['source']['native_id'] or source['epoch']!=n['epoch'] or source['entries']!=[]
            or type(reports) is not dict or set(reports)!={'schema','root','scope','reports'}
            or reports['schema']!=('FS3_REPORT_PIN_V1' if lane=='QUALITY_DIPS' else 'PERP_AUTO_OP_REPORT_PIN_V1')
            or reports['root']!=n['resources']['report']['native_id'] or type(reports['reports']) is not list or len(reports['reports'])!=1
            or type(projection) is not dict or set(projection)!={'root','required','acknowledged'}
            or projection['root']!=n['resources']['projection']['native_id']
            or any(type(projection[k]) is not int or projection[k]!=0 for k in ('required','acknowledged'))):
        raise ValueError('PERSONAL_INITIAL_PIN_OR_PROJECTION_CONFLICT')
    for root in (source['root'],reports['root'],projection['root']):native_id(root)
    for binding in (source['inception'],reports['scope'],*reports['reports']):
        if type(binding) is not dict or set(binding)!={'id','sha256'}:raise ValueError('PERSONAL_INITIAL_FILE_BINDING')
        native_id(binding['id']);hashed(binding['sha256'])
    return lane,n,m,current


class PersonalInceptionPublisher(OneTimePublisher):
    writer_context_schema='PERSONAL_GENESIS_WRITER_V1'
    pending_schema='PERSONAL_GENESIS_PENDING_V1'
    commit_schema='PERSONAL_GENESIS_COMMIT_V1'
    def _build_current(self,e,files,now,boundary):
        lane,n,m=validate_personal_inception(e)
        schema,pin_schema=('QD_AUTO_OP_INCEPTION_V1','QD_AUTO_OP_PIN_V1') if lane=='QUALITY_DIPS' else ('PERP_AUTO_OP_INCEPTION_V1','PERP_AUTO_OP_PIN_V1')
        source=files.write('source','inception.json',{'schema':schema,'enrollment_digest':digest(n),'parameters':m,'execution':'SIMULATED'})
        source_pin={'schema':pin_schema,'root':n['resources']['source']['native_id'],'inception':source,'epoch':m['epoch'],'entries':[]}
        state,head,_=replay_verified_events(m,[]);audit_financial_events(m,[],state)
        if state!=initial_state(m) or state['positions'] or head!=digest(m):raise ValueError('PERSONAL_INITIAL_AUDIT')
        # Zero operations imply zero required projection documents. The existing
        # FS3 projection root must remain empty;do not invent a projection fill.
        scope=e['report_scope'];scope_pin=files.write('report','scope.json',scope)
        deadline=time.monotonic()+2
        observed=boundary()
        while observed<=m['opened_at']:
            if time.monotonic()>=deadline:raise ValueError('PERSONAL_INCEPTION_CLOCK_DID_NOT_ADVANCE')
            time.sleep(.01);observed=boundary()
        logical={'epoch':m['epoch'],'entries':[],'root':source_pin['root'],'inception':source}
        day=datetime.fromtimestamp(observed,ZoneInfo(m['timezone'])).date().isoformat()
        report=build_daily_report(scope,m,logical,[],day,observed);audit_daily_report(report,scope,m,logical,[],state)
        doc={'schema':'FS3_REPORT_DOCUMENT_V1' if lane=='QUALITY_DIPS' else 'PERP_AUTO_OP_REPORT_DOCUMENT_V1','revision':1,'previous':scope_pin,'report_id':digest(report),'report':report}
        report_binding=files.write('report','0001-report.json',doc)
        return {'schema':'PERSONAL_INITIAL_CURRENT_V1','profile':PROFILE,'enrollment_digest':digest(n),'lane':lane,
            'source':source_pin,'reports':{'schema':'FS3_REPORT_PIN_V1' if lane=='QUALITY_DIPS' else 'PERP_AUTO_OP_REPORT_PIN_V1','root':n['resources']['report']['native_id'],'scope':scope_pin,'reports':[report_binding]},
            'state_digest':digest(state),'revision':0,'acknowledged_revision':0,'generation':1,'status':'ACKNOWLEDGED',
            'projection':{'root':n['resources']['projection']['native_id'],'required':0,'acknowledged':0}}


class NativePersonalInceptionFiles:
    """Existing-only,empty financial roots. Creates files,never directories.

    Invocation is excluded until the separately approved activation bundle.
    """
    @contextmanager
    def open(self,enrollment):
        enrollment=strict(body(enrollment));_,e,_=validate_personal_inception(enrollment)
        native=native_primitives()
        outputs={};expected={r:{} for r in ('source','projection','report')}
        try:
            for role in expected:
                root=e['resources'][role]
                outputs[role]=native.w.WindowsOutput(root['path'])
                if native.native.file_identity(outputs[role].root_handle)!=root['native_id'] or list(Path(root['path']).iterdir()):raise ValueError('PERSONAL_EMPTY_ENROLLED_ROOT_REQUIRED')
            class Files:
                def write(self,role,name,value):
                    if role not in expected:raise ValueError('PERSONAL_FINANCIAL_ROLE')
                    binding=outputs[role].write_bound(name,body(value).encode());expected[role][name]=binding;self.verify();return binding
                def verify(self):
                    for role,out in outputs.items():
                        out._verify()
                        if {p.name for p in Path(out.root).iterdir()}!=set(expected[role]):raise ValueError('PERSONAL_INCEPTION_NAMESPACE_CHANGED')
                        for name,binding in expected[role].items():native.read_bound(out,name,binding)
            yield Files()
        finally:
            for out in outputs.values():out.close()


class PersonalPublicationIssuer:
    """The same sole-operator activation;no independent issuer role."""
    def __init__(self,installation):self.installation=installation
    @contextmanager
    def lease(self,scope,now):
        from types import SimpleNamespace

        from app.services.personal_paper_runtime import checked_personal_installation
        request={'schema':'ATLAS_PERSONAL_INCEPTION_REQUEST_V1','action':'INITIALIZE_SIMULATED_ACCOUNTS','scope':scope}
        with self.installation.lease(request) as lease:
            original=checked_personal_installation(lease,request)
            yield SimpleNamespace(check=lambda candidate,t:candidate==scope and now<=t<=now+30 and lease.check(original))


class PersonalInceptionBootstrap:
    """Pure plan + accepted local reservation/readback. No implicit publication."""
    def __init__(self,*,enrollment,publication,issuer,clock,readback):
        if any(x is None for x in (enrollment,publication,issuer,clock,readback)):raise ValueError('PERSONAL_INCEPTION_DEPENDENCIES_REQUIRED')
        self.enrollment=strict(body(enrollment));validate_personal_inception(self.enrollment)
        self.publication,self.issuer,self.clock,self.readback=publication,issuer,clock,readback
    def scope(self):
        e=self.enrollment;n=e['native_enrollment']
        intent={'schema':'PERSONAL_GENESIS_INTENT_V1','profile':PROFILE,'operation_id':'personal-inception:'+digest([n['account_id'],n['epoch']]),'enrollment_digest':digest(e),'account_id':n['account_id'],'epoch':n['epoch'],'lane':e['lane']}
        if e['lane']=='QUALITY_DIPS':
            from app.services.quality_dips_autonomous_enrollment import (
                publication_intent,
            )
            intent['native_intent']=publication_intent(n)
            intent['operation_id']=intent['native_intent']['operation_id']
        return intent
    def prepare(self):
        scope=self.scope()
        with self.issuer.lease(scope,self.clock()) as lease:
            if lease.check(scope,self.clock()) is not True or self.publication.row(scope['operation_id']) is not None:raise ValueError('PERSONAL_INCEPTION_NOT_UNPUBLISHED')
        return scope
    def verify_publication(self):
        current,ack=self.publication.acknowledged(self.scope()['operation_id'])
        if self.readback.verify(self.enrollment,current) is not True:raise ValueError('PERSONAL_INITIAL_READBACK_REFUSED')
        return {'schema':'PERSONAL_GENESIS_READY_V1','publication_digest':digest(ack),'current_digest':digest(current),'current':current,'financial_startup_authorized':False}


    def native_publication(self):
        # The actual V4 intent is durably inside the personal reservation;this
        # view binds its original identity,never renames a fixture/manual effect.
        scope=self.scope()
        if self.enrollment['lane']!='QUALITY_DIPS' or 'native_intent' not in scope:raise ValueError('PERSONAL_QD_PUBLICATION_ONLY')
        ready=self.verify_publication();_,ack=self.publication.acknowledged(scope['operation_id'])
        if ready['publication_digest']!=digest(ack):raise ValueError('PERSONAL_PUBLICATION_CHANGED')
        return {'schema':'QD_AUTO_NATIVE_PUBLICATION_V4','intent_digest':digest(scope['native_intent']),
                'operation_id':scope['native_intent']['operation_id'],'status':'ACKNOWLEDGED','ack_id':digest(ack)}


class NativePersonalInitialReadback:
    """Existing native immutable bytes + separate FS1/FS3 arithmetic audit."""
    def verify(self,enrollment,current):
        original_enrollment,original_current=enrollment,current
        sealed_enrollment,sealed_current=body(enrollment),body(current)
        enrollment=strict(sealed_enrollment)
        lane,n,expected_manifest,current=validate_initial_current(enrollment,current)
        native=native_primitives();outputs={}
        try:
            for role in ('source','projection','report'):
                out=native.w.WindowsOutput(n['resources'][role]['path']);outputs[role]=out
                if native.native.file_identity(out.root_handle)!=n['resources'][role]['native_id']:raise ValueError('PERSONAL_INITIAL_ROOT_SUBSTITUTION')
            def inventory():
                for role,out in outputs.items():
                    out._verify()
                    if native.native.file_identity(out.root_handle)!=n['resources'][role]['native_id']:raise ValueError('PERSONAL_INITIAL_ROOT_SUBSTITUTION')
                if ({p.name for p in Path(outputs['source'].root).iterdir()}!={'inception.json'} or list(Path(outputs['projection'].root).iterdir())
                        or {p.name for p in Path(outputs['report'].root).iterdir()}!={'scope.json','0001-report.json'}):raise ValueError('PERSONAL_INITIAL_NAMESPACE')
            inventory()
            source=current['source'];report_pin=current['reports']
            value=strict(native.read_bound(outputs['source'],'inception.json',source['inception'])[0].decode())
            expected_schema='QD_AUTO_OP_INCEPTION_V1' if enrollment['lane']=='QUALITY_DIPS' else 'PERP_AUTO_OP_INCEPTION_V1'
            if value!={'schema':expected_schema,'enrollment_digest':digest(n),'parameters':expected_manifest,'execution':'SIMULATED'}:raise ValueError('PERSONAL_INITIAL_PARAMETERS_CHANGED')
            scope=strict(native.read_bound(outputs['report'],'scope.json',report_pin['scope'])[0].decode())
            doc=strict(native.read_bound(outputs['report'],'0001-report.json',report_pin['reports'][0])[0].decode())
            state,_,_=replay_verified_events(expected_manifest,[]);audit_financial_events(expected_manifest,[],state)
            if (source['entries']!=[] or source['root']!=n['resources']['source']['native_id'] or source['epoch']!=n['epoch']
                    or report_pin['root']!=n['resources']['report']['native_id']
                    or type(doc) is not dict or set(doc)!={'schema','revision','previous','report_id','report'}
                    or type(doc['revision']) is not int or doc['revision']!=1 or doc['previous']!=report_pin['scope']
                    or doc['schema']!=('FS3_REPORT_DOCUMENT_V1' if lane=='QUALITY_DIPS' else 'PERP_AUTO_OP_REPORT_DOCUMENT_V1')
                    or scope!=enrollment['report_scope'] or doc['report_id']!=digest(doc['report']) or current['state_digest']!=digest(state)
                    or current['revision']!=0 or current['acknowledged_revision']!=0 or current['status']!='ACKNOWLEDGED'):
                raise ValueError('PERSONAL_INITIAL_CUT_CONFLICT')
            logical={'epoch':n['epoch'],'entries':[],'root':source['root'],'inception':source['inception']}
            audit_daily_report(doc['report'],scope,expected_manifest,logical,[],state)
            inventory()
            if body(original_enrollment)!=sealed_enrollment or body(original_current)!=sealed_current:raise ValueError('PERSONAL_INITIAL_READ_INPUT_CHANGED')
            return True
        finally:
            for out in outputs.values():out.close()
