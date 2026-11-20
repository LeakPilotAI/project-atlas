"""Injected Windows adapter qualification; no OS loads, sockets or children."""

import copy
import hashlib
import ntpath
from types import SimpleNamespace

import pytest

from app.services.paper_financial_replay import digest
from scripts.observation_runtime.aip06_acceptance_grade import IndependentGrader, READERS
from scripts.observation_runtime.aip06_async_review import assess_observed_branch
from scripts.observation_runtime.aip06_harness import LIMITS, ROOTS, SCOPE_HASH
from scripts.observation_runtime.aip06_native_scenario_bindings import bindings, contracts
from scripts.observation_runtime.aip06_windows_acceptance_adapters import (
    BootstrapObjectEvidence, ColdArchiveEvidence, ColdLedgerEvidence, PinnedWindowsRead, RetainedFinancialEvidence,
    WindowsAcceptanceOwner, WindowsCapacityEvidence, WindowsJobEvidence, WindowsProcessEvidence, WindowsReaderSet,
)
from scripts.observation_runtime.aip06_cleanup_providers import CimSockets, GuardedNetstat, StrictProcessCleanup, TcpTables
from scripts.observation_runtime.aip06_windows_process import NativeProcessObserver
from scripts.observation_runtime.launch_ownership import LaunchRequest, RetainedLaunchBinding, identity
from test_aip06_native_session_stop import fixture as guarded_fixture


class Clock:
    def __init__(self): self.now = 10**9
    def __call__(self): self.now += 1000; return self.now


class Files:
    def __init__(self):
        self.raw = b'INJECTED FILE'; self.path = r'D:\INJECTED\python.exe'; self.opened = False; self.did_close = False
        self.info = {'kind':'file','reparse':False,'links':1,'id':[1,2,3],'bytes':len(self.raw)}
        self.acl_error = False
    def open_image(self, path): assert path == self.path; self.opened = True; return 90
    def describe(self, handle): assert handle == 90; return copy.deepcopy(self.info)
    def final_path(self, handle): return self.path
    def acl(self, handle, sid):
        if self.acl_error: raise ValueError('ACL refused')
    def read(self, handle, maximum): return self.raw
    def close(self, handle): self.did_close = True
    def closed(self, handle): return self.did_close


def file_fixture():
    x = guarded_fixture(); files = Files(); clock = Clock()
    reader = PinnedWindowsRead(files=files, allocations=x.alloc, clock_ns=clock, sid='S-INJECTED',
        pins={files.path:{'file_id':[1,2,3],'sha256':hashlib.sha256(files.raw).hexdigest()}})
    return x, files, clock, reader


def test_native_pin_reader_uses_actual_allocation_interface_and_closes_original():
    x, files, clock, reader = file_fixture()
    assert reader.read_bytes(files.path, maximum_bytes=100, deadline_ns=clock()+10**9) == files.raw
    assert files.did_close and not reader.failed and not x.alloc.live


@pytest.mark.parametrize('damage',['file-id','hash','reparse','hardlink','directory','acl','changed-path','deadline','close'])
def test_pin_refusals_latch_and_never_silently_accept_metadata(damage):
    x, files, clock, reader = file_fixture()
    path = files.path
    if damage == 'file-id': files.info['id'] = [9,9,9]
    elif damage == 'hash': files.raw = b'wrong'
    elif damage == 'reparse': files.info['reparse'] = True
    elif damage == 'hardlink': files.info['links'] = 2
    elif damage == 'directory': files.info['kind'] = 'directory'
    elif damage == 'acl': files.acl_error = True
    elif damage == 'changed-path': files.final_path = lambda h:r'D:\foreign.exe'
    elif damage == 'deadline': files.read = lambda *a:(setattr(clock,'now',clock.now+2*10**9) or files.raw)
    else: files.closed = lambda h:False
    with pytest.raises(ValueError): reader.read_bytes(path, maximum_bytes=100, deadline_ns=clock()+10**9)
    assert reader.failed
    with pytest.raises(ValueError): reader.read_bytes(path, maximum_bytes=100, deadline_ns=clock()+10**9)
    if damage == 'close': assert x.alloc.live
    else: assert not x.alloc.live


def test_pin_reader_refuses_outside_declared_files_before_open():
    x, files, clock, reader = file_fixture()
    with pytest.raises(ValueError): reader.read_bytes(r'C:\private', maximum_bytes=100, deadline_ns=clock()+10**9)
    assert not files.opened and not x.alloc.live


def test_ambiguous_open_failure_keeps_reservation_instead_of_inventing_a_release():
    x,files,clock,reader=file_fixture()
    def failed(path): raise RuntimeError('unknown acquisition outcome')
    files.open_image=failed
    with pytest.raises(RuntimeError): reader.read_bytes(files.path,maximum_bytes=100,deadline_ns=clock()+10**9)
    assert reader.failed and x.alloc.live


class Calls:
    def __init__(self):
        self.rows = {p:{'pid':p,'created':p*100,'image':r'D:\INJECTED\python.exe',
                       'parent_pid':5 if p==10 else 10,'command_line':str(p)} for p in (10,20,30)}
        self.jobs = {100:{20},200:{30},500:{10,20,30}}
        self.exits = set();self.memory = {};self.current_handle = 30
        self.limits = {'processes':8};self.cpu = 1
    def current(self): return self.current_handle
    def native(self,h): return {k:self.rows[h][k] for k in ('pid','created','image')}
    def lifecycle(self,h): return {'pid':h,'created':self.rows[h]['created'],'exited':h in self.exits,'exit_code':0 if h in self.exits else None}
    def in_job(self,h,job): return h in self.jobs[job]
    def members(self,job): return set(self.jobs[job])
    def job_limits(self,job): return self.limits
    def job_accounting(self,job): return {'active':len(self.jobs[job]),'user_ns':self.cpu,'kernel_ns':0,'total':3,'terminated':0}
    def usage(self,h): return self.memory.get(h,1),self.cpu


def process_fixture():
    calls=Calls();clock=Clock()
    cim=SimpleNamespace(process=lambda pid,deadline_ns:copy.deepcopy(calls.rows[pid]))
    images={ntpath.normcase(calls.rows[10]['image']):{'file_id':[1,2,3],'sha256':'a'*64}}
    def observer(job):
        value=NativeProcessObserver(calls=calls,cim=cim,images=images,clock_ns=clock);value.job=job;value.parent=10;return value
    def binding(pid,job):
        api=observer(job);image=(calls.rows[pid]['image'],(1,2,3),'a'*64)
        request=LaunchRequest('acceptance_worker',str(pid%10)*32,'direct',image,image,str(pid),str(pid))
        value=RetainedLaunchBinding(api,request,10,pid)
        value.bind_runtime(pid,{'pid':pid,'nonce':request.nonce,'role':request.role});return value
    worker=binding(20,100);reader=binding(30,200)
    evidence=WindowsProcessEvidence(observer=observer(100),reader_binding=reader,clock_ns=clock)
    return SimpleNamespace(**locals())


def test_independent_process_capture_survives_exit_using_original_handle_not_exited_pid_query():
    x=process_fixture();x.evidence.capture(x.worker,deadline_ns=x.clock()+10**9)
    x.calls.exits.add(20);x.calls.jobs[100].clear()
    x.cim.process=lambda pid,deadline_ns:copy.deepcopy(x.calls.rows[pid]) if pid!=20 else (_ for _ in ()).throw(AssertionError('no exited PID query'))
    cut=x.evidence.read(deadline_ns=x.clock()+10**9)
    assert cut['complete'] and cut['rows'][0]['lifecycle']['exited'] and cut['observer']==identity(x.reader.runtime)


@pytest.mark.parametrize('damage',['self-certify','pid-reuse','command','job','missing-reader','deadline'])
def test_independent_process_source_refuses_missing_or_conflicting_native_evidence(damage):
    x=process_fixture()
    if damage=='self-certify': x.evidence.reader_binding=x.worker;x.calls.current_handle=20
    elif damage=='missing-reader': x.calls.rows[30]['created']+=1
    elif damage=='command': x.calls.rows[20]['command_line']='foreign'
    elif damage=='job': x.calls.jobs[100].add(999)
    elif damage=='deadline': x.clock.now+=2*10**9
    else:
        x.evidence.capture(x.worker,deadline_ns=x.clock()+10**9);x.calls.rows[20]['created']+=1
    with pytest.raises(ValueError):
        if damage=='pid-reuse': x.evidence.read(deadline_ns=x.clock()+10**9)
        else: x.evidence.capture(x.worker,deadline_ns=10**9+10**8)


@pytest.mark.parametrize('damage',['unknown-child','missing-child','changed-limits','wrong-native','missing-job'])
def test_complete_job_reader_refuses_ambiguity(damage):
    x=process_fixture();expected=[(h,x.calls.native(h)) for h in (10,20,30)]
    provider=WindowsJobEvidence(calls=x.calls,job=500,expected=expected,limits={'processes':8},clock_ns=x.clock)
    if damage=='unknown-child': x.calls.jobs[500].add(999)
    elif damage=='missing-child': x.calls.jobs[500].remove(20)
    elif damage=='changed-limits': x.calls.limits['processes']=9
    elif damage=='wrong-native': x.calls.rows[20]['created']+=1
    else: provider.job=None
    with pytest.raises(ValueError): provider.read(deadline_ns=x.clock()+10**9)


def test_capacity_reader_measures_kernel_counters_and_does_not_claim_load_acceptance():
    x=process_fixture();expected=[(h,x.calls.native(h)) for h in (10,20,30)]
    jobs=WindowsJobEvidence(calls=x.calls,job=500,expected=expected,limits={'processes':8},clock_ns=x.clock)
    ledger=SimpleNamespace(read=lambda **kw:{'scope':SCOPE_HASH,'unknown':False,'entries':1,'charged_bytes':4096})
    provider=WindowsCapacityEvidence(calls=x.calls,job_reader=jobs,processes=expected,parent_handle=10,ledger_reader=ledger,clock_ns=x.clock)
    assert provider.read(deadline_ns=x.clock()+10**9)['load_acceptance'] is False
    x.calls.memory[20]=LIMITS['child_private_bytes']+1
    with pytest.raises(ValueError,match='PER_PROCESS'): provider.read(deadline_ns=x.clock()+10**9)


def test_cold_ledger_reader_replays_existing_chain_without_new_commit_or_owner_summary():
    x=guarded_fixture();before=copy.deepcopy(x.ledger.journal.rows)
    processes=SimpleNamespace(check_reader=lambda **kw:('INJECTED_INDEPENDENT_READER',))
    provider=ColdLedgerEvidence(journal=x.ledger.journal,expected_head=x.ledger.head,process_evidence=processes,clock_ns=lambda:x.now[0])
    result=provider.read(deadline_ns=x.now[0]+10**9)
    assert result['head']==x.ledger.head and x.ledger.journal.rows==before and result['unknown'] is False
    provider.head='f'*64
    with pytest.raises(ValueError): provider.read(deadline_ns=x.now[0]+10**9)


def test_owner_authorization_and_incompatible_supervisor_role_refuse_without_launch_or_reservation():
    x=guarded_fixture();x.controller.require_ready=lambda:None;x.controller.process_port=x.port
    owner=WindowsAcceptanceOwner(controller=x.controller,guard=x.guard,
        capacity=SimpleNamespace(read=lambda **kw:{'observed':True}),clock_ns=lambda:x.now[0])
    before=list(x.calls.events)
    with pytest.raises(ValueError,match='AUTHORIZATION'): owner.start()
    with pytest.raises(ValueError,match='AUTHORIZATION'): owner.launch_controller('no','no',deadline_ns=x.now[0]+10**9)
    with x.guard.installed(),pytest.raises(ValueError,match='BOOTSTRAP_ROLE'):
        owner.reserve(dict(LIMITS),deadline_ns=x.now[0]+10**9)
    assert x.calls.events==before and not owner.reservations and not x.calls.handles
    assert owner.cleanup(None,deadline_ns=x.now[0]+10**9)


@pytest.mark.parametrize('id',[c.id for c in contracts()])
def test_all_scheduled_native_bindings_refuse_a_missing_physical_context_before_reservation(id):
    x=guarded_fixture();x.controller.process_port=x.port;x.controller.clock=lambda:x.now[0]
    value=bindings(x.controller.profile['source_pins'])[id]
    with x.guard.installed(),pytest.raises(ValueError,match='PHYSICAL_CONTEXT_MISSING'):
        value.check(x.controller,x.guard,deadline_ns=x.now[0]+10**9)
    assert not x.port.sessions and not x.calls.handles


def test_exact_schedule_preserves_missing_fault_producers_race_roles_and_original_deadlines():
    table={c.id:c for c in contracts()}
    assert table['F04'].roles==('race_one','race_two') and table['F04'].max_children==2
    assert all(c.stop_ns==8*10**9 and c.ipc_ns==6*10**9 for c in table.values())
    assert all(table[k].source_case is None for k in ('F05','F06','F09','F11','F12'))
    with pytest.raises(ValueError): bindings({},contexts={'UNKNOWN':object()})


@pytest.mark.parametrize('damage',['valid','extra-case','missing-result','wrong-result'])
def test_existing_guarded_pytest_driver_admits_only_exact_reviewed_case(monkeypatch,damage):
    from scripts.observation_runtime.aip06_test_driver import run_reviewed_tests
    x=guarded_fixture();monkeypatch.setenv('PYTEST_DISABLE_PLUGIN_AUTOLOAD','1');monkeypatch.setenv('PYTHONDONTWRITEBYTECODE','1')
    x.port.verify_test_source=lambda path:None
    case='tests/test_qd_unified_shutdown.py::test_global_qd_stop_cannot_falsely_complete'
    def main(args,plugins):
        assert args[-1]==case and 'tests/test_qd_unified_shutdown.py' not in args
        writer=plugins[1]
        if damage!='missing-result':
            for phase in ('setup','call','teardown'):
                writer.pytest_runtest_logreport(SimpleNamespace(nodeid=case if damage!='wrong-result' else case+'other',
                    when=phase,outcome='passed',failed=False,skipped=False,duration=0,longrepr=''))
        writer.pytest_sessionfinish(None,0);return 0
    with x.guard.installed():
        x.guard.mkdir(ROOTS['E'])
        kwargs={'modules':['tests/test_qd_unified_shutdown.py'],'junit_leaf':'case.xml','case_ids':[case], 'pytest_main':main}
        if damage=='extra-case': kwargs['case_ids'] += ['tests/other.py::unreviewed']
        if damage=='valid': assert run_reviewed_tests(**kwargs)['native_acceptance'] is False
        else:
            with pytest.raises(ValueError): run_reviewed_tests(**kwargs)


@pytest.mark.parametrize('builtin',[False,True])
def test_async_branch_assessment_never_grants_native_compatibility(builtin):
    review={'schema':'AIP06_ASYNC_SOURCE_REVIEW_V1','native_execution':False,'compatible':False,
            'default_proactor':True,'self_socketpair':True,'fallback_binds_tcp':True}
    observed={'schema':'AIP06_READONLY_HOST_ASYNC_BRANCH_V1','has_builtin_socketpair':builtin,
              'socket_created':False,'loop_created':False,'target_runtime_executed':False,'target_byte_match':True}
    result=assess_observed_branch(review,observed)
    assert not result['compatible'] and not result['native_acceptance']
    assert result['status'].endswith('FORBIDDEN_BIND_CONNECT') if not builtin else result['status'].endswith('NOT_QUALIFIED')
    observed['loop_created']=True
    with pytest.raises(ValueError): assess_observed_branch(review,observed)


def bundle_fixture(damage=''):
    x=process_fixture();x.evidence.capture(x.worker,deadline_ns=x.clock()+10**9)
    x.calls.exits.add(20);x.calls.jobs[100].clear()
    classes={'JOB':WindowsJobEvidence,'LEDGER':WindowsCapacityEvidence,'FINANCIAL':RetainedFinancialEvidence,
             'RESTART':ColdArchiveEvidence,'OBJECTS':BootstrapObjectEvidence,'CIM':CimSockets,
             'IP_HELPER':TcpTables,'NETSTAT':GuardedNetstat,'PROCESS':StrictProcessCleanup}
    providers={'HANDLES':x.evidence};x.order=[];x.output=[]
    for name,cls in classes.items():
        provider=object.__new__(cls)  # Inject responses into concrete provider instances, no OS loaders.
        def read(*,deadline_ns,name=name):
            x.order.append(name)
            if name in ('CIM','IP_HELPER','NETSTAT'):
                rows=[]
                if damage in ('state-zero','pid-zero-listener','retained-listener'):
                    rows=[{'protocol':'TCP','family':4,'local_address':'127.0.0.1','local_port':50123,
                           'remote_address':'0.0.0.0','remote_port':0,'state':0 if damage=='state-zero' else 2,
                           'owner_present':True,'owner_pid':20 if damage=='retained-listener' else 0}]
                if damage=='reader-error' and name=='NETSTAT': raise ValueError('enumeration failed')
                return {'rows':rows,'complete':True,'error':None,'started_ns':x.clock(),'finished_ns':x.clock()}
            return {'injected_response':name}
        if name=='PROCESS':
            def collect(*,after_ns,deadline_ns):
                x.order.append('PROCESS')
                return {'scope':SCOPE_HASH,'survivors':[99] if damage=='survivor' else [],'unknown':False,
                        'started_ns':after_ns-1 if damage=='stale-process' else x.clock(),'at_ns':x.clock()}
            provider.collect=collect
        else: provider.read=read
        providers[name]=provider
    if damage=='owner-summary': providers['JOB']=SimpleNamespace(read=lambda **kw:{'complete':True})
    x.bundle=WindowsReaderSet(process_evidence=x.evidence,providers=providers,clock_ns=x.clock,output=x.output,
        manifest_sha256='a'*64,socket_port=SimpleNamespace(aggregate=SimpleNamespace(rows={20:{'native':{'pid':20}}})),
        endpoints=(('127.0.0.1',50123),))
    x.request={'scope':SCOPE_HASH,'manifest':'a'*64,'root':ROOTS['E']}
    return x


def test_raw_concrete_bundle_keeps_socket_then_strict_process_order_and_cannot_grade_native():
    from test_aip06_native_prerequisites import plan
    x=bundle_fixture();p=plan();pin=digest(p);x.bundle.pin=pin;x.request['manifest']=pin
    result=IndependentGrader.inspect_windows(x.bundle,x.request,plan=p,manifest_sha256=pin,deadline_ns=x.clock()+10**9)
    assert len(result['cuts'])==len(READERS) and not result['native_acceptance']
    assert x.order[-4:]==['CIM','IP_HELPER','NETSTAT','PROCESS']
    assert result['observer']==identity(x.reader.runtime)
    previous_order = list(x.order)
    with pytest.raises(ValueError,match='WINDOWS_READER_ONCE_ONLY_COLLECTION_REQUIRED'):
        x.bundle.collect(x.request,deadline_ns=x.clock()+10**9)
    assert x.order == previous_order and x.bundle.sequence == 1
    with pytest.raises(ValueError,match='NOT_QUALIFIED'): IndependentGrader.grade_native(None,result)


@pytest.mark.parametrize('damage',['owner-summary','state-zero','pid-zero-listener','retained-listener',
                                  'reader-error','survivor','stale-process'])
def test_raw_concrete_bundle_preserves_all_existing_cleanup_refusals(damage):
    with pytest.raises(ValueError):
        x=bundle_fixture(damage);x.bundle.collect(x.request,deadline_ns=x.clock()+10**9)


@pytest.mark.parametrize('cut', [None, [], {},
    {'scope': SCOPE_HASH, 'survivors': None, 'unknown': False, 'started_ns': 1, 'at_ns': 1},
    {'scope': SCOPE_HASH, 'survivors': [], 'unknown': 0, 'started_ns': 1, 'at_ns': 1},
    {'scope': SCOPE_HASH, 'survivors': [], 'unknown': False, 'started_ns': True, 'at_ns': 1},
    {'scope': SCOPE_HASH, 'survivors': [], 'unknown': False, 'started_ns': 1, 'at_ns': '1'},
])
def test_strict_process_provider_refuses_malformed_cut_without_emitting_process_evidence(cut):
    x = bundle_fixture()
    x.bundle.providers['PROCESS'].collect = lambda **kw: cut
    with pytest.raises(ValueError, match='STRICT_PROCESS_CUT_FIELDS_REQUIRED'):
        x.bundle.collect(x.request, deadline_ns=x.clock()+10**9)
    assert x.bundle.failed and x.bundle.sequence == 0
    assert all(row['reader'] != 'PROCESS' for row in x.output)


def test_final_process_cut_refuses_changed_independent_reader_identity():
    x = bundle_fixture()
    original = x.evidence.check_reader
    checks = [0]
    def switching_reader(*, deadline_ns):
        checks[0] += 1
        return original(deadline_ns=deadline_ns) if checks[0] == 1 else ('SWAPPED_READER',)
    x.evidence.check_reader = switching_reader
    with pytest.raises(ValueError, match='FINAL_PROCESS_CUT_FRESH_AND_SAME_INDEPENDENT_READER'):
        x.bundle.collect(x.request, deadline_ns=x.clock()+10**9)
    assert checks[0] >= 2 and x.bundle.failed and x.bundle.sequence == 0
    assert all(row['reader'] != 'PROCESS' for row in x.output)


@pytest.mark.parametrize('deadline', [0, True, -1, 'future'])
def test_reader_refuses_invalid_deadline_before_native_observation(deadline):
    x = bundle_fixture()
    observations = []
    x.evidence.check_reader = lambda **kw: observations.append(kw)
    if deadline == 'future':
        deadline = x.clock()  # Typed but already expired.
    with pytest.raises(ValueError, match='INDEPENDENT_READER_DEADLINE_BEFORE_OBSERVATION'):
        x.bundle.collect(x.request, deadline_ns=deadline)
    assert not observations and not x.order and not x.output
    assert x.bundle.failed and x.bundle.sequence == 0


def test_final_process_cut_refuses_stale_collection_window():
    x = bundle_fixture()
    original_clock = x.bundle.clock
    advanced = [None]
    def clock():
        return advanced[0] if advanced[0] is not None else original_clock()
    x.bundle.clock = clock
    def stale_process(*, after_ns, deadline_ns):
        advanced[0] = after_ns + 2 * 10**9 + 1
        return {'scope': SCOPE_HASH, 'survivors': [], 'unknown': False,
                'started_ns': after_ns, 'at_ns': advanced[0]}
    x.bundle.providers['PROCESS'].collect = stale_process
    with pytest.raises(ValueError, match='FINAL_PROCESS_CUT_FRESH_AND_SAME_INDEPENDENT_READER'):
        x.bundle.collect(x.request, deadline_ns=x.clock()+4*10**9)
    assert x.bundle.failed and x.bundle.sequence == 0
    assert all(row['reader'] != 'PROCESS' for row in x.output)


def test_original_bootstrap_object_observer_checks_kernel_continuity_and_release_history():
    from test_aip06_bootstrap_objects import acquired
    from test_aip06_descendant_closure import exit_child
    t=acquired();t.cap.accept(t.lease.evidence())
    independent=SimpleNamespace(check_reader=lambda **kw:('INJECTED_READER',))
    value=BootstrapObjectEvidence(sources=(t.cap,),process_evidence=independent,clock_ns=lambda:t.x.now[0])
    live=value.read(deadline_ns=t.x.now[0]+10**9)
    assert live['rows'][0]['open_slots'] and live['rows'][0]['financial_ack'] is False
    exit_child(t.j.z);t.cap.dispose_after_exit();t.cap.release_reservations()
    final=value.read(deadline_ns=t.x.now[0]+10**9)
    assert final['rows'][0]['released'] and not final['rows'][0]['open_slots']


def test_retained_financial_reply_is_never_mislabelled_as_new_cold_native_reopen():
    from scripts.observation_runtime.aip06_stop import RetainedFinancialReply
    x=process_fixture();reply=RetainedFinancialReply();request={'scope':SCOPE_HASH,'operation':'INJECTED'}
    financial={'accounts':{},'acknowledgements':{},'before_hashes':{},'after_hashes':{},'writer_rebind_refused':True}
    reply.bind(SimpleNamespace(identity=lambda:x.reader.runtime),request,{'request':request,'financial':financial})
    value=RetainedFinancialEvidence(reply=reply,request=request,process_evidence=x.evidence,clock_ns=x.clock)
    result=value.read(deadline_ns=x.clock()+10**9)
    assert result['readback_type']=='RETAINED_RESPONSE_NOT_NEW_COLD_REOPEN' and not result['native_acceptance']
    reply.observer_identity=x.worker.runtime
    with pytest.raises(ValueError,match='READER_CONFLICT'): value.read(deadline_ns=x.clock()+10**9)


def test_cold_archive_adapter_reopens_original_hash_chain_without_writing():
    from scripts.observation_runtime.aip06_outputs import EvidenceOutput
    from test_aip06_windows_adapters import io_fixture
    x=io_fixture();independent=SimpleNamespace(check_reader=lambda **kw:('INJECTED_READER',))
    with x.guard.installed():
        x.guard.mkdir(ROOTS['E']);directory=ntpath.join(ROOTS['E'],'adapter-archive');x.guard.mkdir(directory)
        producer={'session':'a'*32,'owner':x.s.controller,'role':'OFFLINE_SOURCE_TEST','source_pins':{'source.py':'a'*64}}
        writer=EvidenceOutput(x.guard,directory=directory,producer=producer);writer.append({'domain':'SOURCE_ONLY'})
        before=copy.deepcopy(x.io.data) if hasattr(x.io,'data') else writer.head
        archive=EvidenceOutput(x.guard,directory=directory,producer=producer)
        provider=ColdArchiveEvidence(archive=archive,expected_head=writer.head,process_evidence=independent,clock_ns=lambda:x.s.now[0])
        result=provider.read(deadline_ns=x.s.now[0]+10**9)
        assert len(result['records'])==1 and not result['native_acceptance'] and archive.sequence==0
        if hasattr(x.io,'data'): assert before==x.io.data
        x.io.close_cache()


@pytest.mark.parametrize('damage',['no-driver','wrong-driver'])
def test_fault_and_capacity_producers_cannot_be_derived_from_mock_headroom(damage):
    x=guarded_fixture();x.controller.clock=lambda:x.now[0];x.controller.process_port=x.port
    contract=next(c for c in contracts() if c.id=='F11')
    context=SimpleNamespace(guard=x.guard,controller=x.controller,contract=contract,roles=contract.roles,verify=lambda **kw:None)
    driver=None if damage=='no-driver' else SimpleNamespace(contract=next(c for c in contracts() if c.id=='F09'))
    value=bindings(x.controller.profile['source_pins'],contexts={'F11':context},fault_drivers={'F11':driver})['F11']
    with x.guard.installed(),pytest.raises(ValueError): value.check(x.controller,x.guard,deadline_ns=x.now[0]+10**9)
    assert not x.calls.handles and not x.port.sessions


def test_concrete_owner_requires_matched_precreation_instead_of_adopting_a_worker_as_supervisor():
    from test_aip06_native_prerequisites import plan
    x=guarded_fixture();p=plan()
    x.controller.require_ready=lambda:None;x.controller.process_port=x.port
    x.controller.profile['executable']=p['executable'];x.controller.profile['source_pins']=p['source_pins']
    owner=WindowsAcceptanceOwner(controller=x.controller,guard=x.guard,
        capacity=SimpleNamespace(read=lambda **kw:{'observed':True}),clock_ns=lambda:x.now[0])
    with x.guard.installed(),pytest.raises(ValueError,match='MATCHED_CONTROLLER_PRECREATION'):
        owner.preflight(p,manifest_sha256=digest(p),deadline_ns=x.now[0]+10**9)
    with pytest.raises(ValueError,match='NOT_CONNECTED'): owner.verify_controller(object(),deadline_ns=x.now[0]+10**9)
    assert not x.calls.handles


def test_original_child_bootstrap_still_refuses_controller_target_as_legacy_supervisor():
    from scripts.observation_runtime.aip06_child_bootstrap import ChildBootstrap
    from scripts.observation_runtime.aip06_acceptance_plan import ENTRY
    with pytest.raises(ValueError,match='SUPERVISOR_ONLY_PINNED_LEGACY_TARGET'):
        ChildBootstrap(channel=SimpleNamespace(role='CHILD'),identity=object(),target=ENTRY,source_pins={ENTRY:'a'*64},
            verify_source=lambda p:None,guard_factory=lambda:None,clock_ns=lambda:1,role='acceptance_supervisor')
