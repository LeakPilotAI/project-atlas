"""Actual personal native cuts/read/report/drain; synthetic session authority only.

No accepted installation, provider, operational account or process-close claim.
Measures a lower bound on installed Stop, not a substitute for its acceptance.
"""
from contextlib import contextmanager
from time import perf_counter
from types import SimpleNamespace

from app.services.paper_financial_replay import body, digest
from app.services.quality_dips_autonomous_integration import AutonomousCoordinationRead
from app.services.quality_dips_autonomous_runtime import PROFILE
from app.services.quality_dips_operational_presentation import OperationalAutonomousSelectedRead
from app.services.quality_dips_operational_runtime import OperationalRuntime
from app.services.quality_dips_shutdown import flatten_and_stop
from test_quality_dips_autonomous_paper import candidate, quote

from scripts.observation_runtime.personal_runtime_current import (
    PersonalNativeReadAuthority,
    PersonalRuntimeCurrent,
)


def complete_financial_stop(*, n, native, bootstrap, pins, reports, ownership, admission,
                            module, projection, service, clock, process, timings, timed):
    read={'schema':'QD_AUTO_OP_READ_ENROLLMENT_V1','account_id':native['account_id'],'epoch':native['epoch'],
        'manifest_digest':digest(n.m),'policy_digest':native['policy_digest'],'inception':pins.current()['inception'],
        **{r+'_root':native['resources'][r]['native_id'] for r in ('source','projection','report')}}
    native_reader=module.OperationalAutonomousReader(enrollment=native,trust=pins,authority=admission,
        clock=clock,projection=projection)
    read_auth=PersonalNativeReadAuthority(bootstrap=bootstrap,source=pins,reports=reports,ownership=ownership,enrollment=read)
    reader=OperationalAutonomousSelectedRead(enrollment=read,authority=read_auth,clock=clock,port=native_reader,
        coordination=AutonomousCoordinationRead(n.engine))
    custody=PersonalRuntimeCurrent(bootstrap=bootstrap,source=pins,reports=reports,reader=reader,native_reader=native_reader,clock=clock)
    scope={'schema':'QD_AUTO_LOCAL_RUNTIME_V3','profile':PROFILE,'scope':'LOCAL_ENROLLED',
        'reader_enrollment':read,'process_identity':{'pid':process['pid'],'created':process['creation_filetime'],'image':process['image']},
        'writer_roster':['decision','source','projection','report','coordination'],'disposable_root':None}
    grant={'schema':'QD_AUTO_LOCAL_SESSION_V3','profile':PROFILE,'enrollment_digest':digest(scope),
        'engine_grant':n.grant,'max_observations':16}
    class Clock:
        def sample(self):return {'schema':'QD_AUTO_CLOCK_V3','utc':clock(),'monotonic_ns':1000,
            'uncertainty_ms':0,'source_id':'SYNTHETIC_NOT_UTC_AUTHORITY'}
    class Authority:
        def verify(self,kind,request,now):
            if now!=clock() or kind not in ('CLOCK','SESSION','CURRENT','DRAIN'):
                raise ValueError('SYNTHETIC_PROOF_SCOPE')
            return {'schema':'QD_AUTO_LOCAL_AUTHORITY_V3','kind':kind,'verified':True,
                'binding':digest(request),'scope':'LOCAL_ENROLLED','issuer_id':'SYNTHETIC_NOT_INSTALLED'}
    runtime=OperationalRuntime(enrollment=scope,engine=n.engine,reader=reader,reports=service,
        authority=Authority(),ownership=ownership,clock=Clock(),custody=custody)
    runtime.grant=grant
    runtime.halted=False
    profile={}
    fixture_before=dict(getattr(n.ledger.images,'_fixture_costs',{}))
    def instrument(port,name,label):
        original=getattr(port,name)
        def measured(*args,**kwargs):
            start=perf_counter()
            try:return original(*args,**kwargs)
            finally:
                row=profile.setdefault(label,{'calls':0,'inclusive_seconds':0})
                row['calls']+=1
                row['inclusive_seconds']+=perf_counter()-start
        setattr(port,name,measured)
    for port,name,label in ((custody,'_capture','current_capture'),(native_reader,'read_committed','native_replay'),
            (reader,'read_committed','selected_read'),(reader,'verify','selected_verify'),
            (service,'publish','report_publication'),(ownership,'drain','native_drain'),
            (n.ledger.images,'_publish','coordination_image_publication'),
            (n.ledger.images.output,'write_bound','coordination_native_file_write'),
            (n.engine.publication.store.output,'write_bound','financial_native_file_write'),
            (projection.output,'write_bound','projection_native_file_write'),
            (service.archive.output,'write_bound','report_native_file_write')):
        instrument(port,name,label)
    authority_trace=[]
    @contextmanager
    def action():
        # Real native writer lease and unchanged acknowledged account/cut.
        with ownership.lease({'enrollment':scope,'grant':grant},now=clock()) as lease:
            authority_trace.append('SYNTHETIC_STOP_AUTHORITY_WITH_REAL_NATIVE_OWNERSHIP')
            if lease.check(lease.snapshot,clock()) is not True:raise ValueError('STOP_NATIVE_OWNER')
            yield
            if lease.check(lease.snapshot,clock()) is not True:raise ValueError('STOP_NATIVE_OWNER_CHANGED')
    def observe(position,timeout):
        assert timeout==2
        n.now[0]+=1
        return {'quotes':[quote(n,candidate(n),bid='120',ask='120.1')],
            'observation':{'symbol':position['symbol'],'instrument':position['instrument'],'observed_at':clock(),'current':{}}}
    owner=SimpleNamespace(runtime=runtime,_action=action,stop=runtime.stop,failed=False)
    outcome=timed('complete_native_financial_stop',lambda:flatten_and_stop(owner,SimpleNamespace(observe=observe)))
    final=timed('final_acknowledged_native_readback',lambda:custody._capture(clock()))
    assert outcome['status']=='FLATTENED' and outcome['process_shutdown_allowed'],outcome
    assert final[0]['source_revision']==3 and outcome['positions']=={}
    before=body(pins.current())
    assert flatten_and_stop(owner,SimpleNamespace(observe=observe))==outcome and body(pins.current())==before
    assert authority_trace
    for key,value in getattr(n.ledger.images,'_fixture_costs',{}).items():
        profile['fixture_'+key]={'calls':1,'inclusive_seconds':value-fixture_before[key]}
    print(__import__('json').dumps({'synthetic_stop_profile_inclusive':profile,
        'installed_authority_clock_process_close_included':False,
        'eight_second_lower_bound_passed':timings['complete_native_financial_stop']+
            timings['final_acknowledged_native_readback']<=8}))
    return outcome
