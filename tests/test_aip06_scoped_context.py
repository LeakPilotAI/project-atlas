"""Source contracts over injected Windows, original bootstrap and framed RPC.

No real native process/reader, financial worker, socket or installed runtime.
"""
import copy
import ntpath
from dataclasses import replace
from subprocess import list2cmdline
from types import SimpleNamespace

import pytest
from app.services.paper_financial_replay import digest
from scripts.observation_runtime.aip06_acceptance_grade import IndependentGrader
from scripts.observation_runtime.aip06_controller_contract import ENTRY, ROLE, bootstrap_argv
from scripts.observation_runtime.aip06_harness import ROOTS, SCOPE_HASH
from scripts.observation_runtime.aip06_ipc import Channel
from scripts.observation_runtime.aip06_scoped_context import (
    SOURCE, READER_ENTRY, ReaderIntent, verify_inherited_scope, forward_scope,
)
import test_aip06_controller_contract as owner_test
import test_aip06_windows_adapters as fixture

WORKER = ntpath.join(ntpath.dirname(ntpath.dirname(ROOTS['E'])), 'INJECTED-worker.py')


def in_controller(monkeypatch, callback):
    original = owner_test.plan
    def plan():
        p = original()
        p['source_pins'].update({SOURCE:'a'*64, READER_ENTRY:'a'*64, WORKER:'a'*64})
        return p
    monkeypatch.setattr(owner_test, 'plan', plan)
    x = owner_test.owner_fixture(monkeypatch)
    targets = {ROLE:ENTRY, 'financial_worker':WORKER, 'readonly_reader':READER_ENTRY,
               'race_one':WORKER, 'race_two':WORKER, 'query':WORKER}
    x.controller.profile['targets'] = targets
    with x.guard.installed(): lease = owner_test.launch(x)
    wire = {'scope':SCOPE_HASH, 'session':'a'*32, 'nonce':'b'*32, 'parent':lease.binding.parent,
            'child':lease.binding.runtime, 'job':{'name':'INJECTED'},
            'launch':{'command':lease.binding.request.launch_command}}
    def channels():
        a,b = fixture.MemoryEndpoint(),fixture.MemoryEndpoint();a.peer=b;b.peer=a
        parent=Channel(a,binding=wire,clock_ns=lambda:x.now[0],account_scope=fixture.ACCOUNTS,role='PARENT')
        child=Channel(b,binding=wire,clock_ns=lambda:x.now[0],account_scope=fixture.ACCOUNTS,role='CHILD')
        return SimpleNamespace(s=SimpleNamespace(ledger=x.ledger,now=x.now),owner=digest(wire['child']),
                               a=a,b=b,parent=parent,child_channel=child)
    monkeypatch.setattr(fixture,'channels',channels)
    f=fixture.bootstrap_fixture(role='acceptance_supervisor',target_override=ENTRY,
        pins_override=x.intent.plan()['source_pins'],controller_command=x.intent.argv,controller_targets=targets)
    f.broker.verifier.verify_peer=lambda binding:lease.binding.verify()
    f.boot.prepare();f.x.parent.send('INPUT',lease.preparation_packet(x.intent.plan(),x.intent.sha256),deadline_ns=x.now[0]+10**9)
    result=[]
    def run(target):
        from scripts.observation_runtime.aip06_session_io import ChildSessionIO
        from scripts.observation_runtime.aip06_acceptance_controller import inherited_prepare
        stream=ChildSessionIO(f.boot.guard,clock_ns=lambda:x.now[0])
        descriptor={'argv':list(x.intent.argv),'source_pins':x.intent.plan()['source_pins'],'targets':targets}
        controller=SimpleNamespace(profile={'source_pins':descriptor['source_pins'],'targets':targets},clock=lambda:x.now[0],
                                    verify_source=x.controller.verify_source)
        port=SimpleNamespace(controller=controller,sessions=[])
        services=SimpleNamespace(port=port,runtime=SimpleNamespace(descriptor=descriptor,identity=f.identity),
                                 read_input=stream.read_input,emit_output=stream.emit_output)
        controller.process_port=services;f.boot.guard.processes=services
        context=inherited_prepare();factory=context.scoped_factory()
        # Memory IO behind the original guard/Broker: logical accounting only,
        # NOT qualification of NativeIO failed-open escrow or physical ACLs.
        from test_aip06_fixture_guard_integration import IO
        from scripts.observation_runtime.aip06_harness import FixturePaths
        g=f.boot.guard;g.io=IO();g.io.close_cache=lambda:None
        g.paths=FixturePaths(g.io)
        g.io.rows[ROOTS['E']]=copy.deepcopy(x.guard.paths.bound['E'])
        g.paths.bound['E']=copy.deepcopy(x.guard.paths.bound['E'])
        proofs=SimpleNamespace(effects={},handles={},release=lambda owner,key,obs:{'owner':owner,'key':key})
        g.resources.proofs=proofs
        def release_observer(binding,key,proof):
            assert proof=={'owner':g.owner,'key':key} and g.io.closed(g.owner,key)
            return g.io
        f.verifier.release_observer=release_observer
        values=dict(locals());values.update(x=x,f=f,lease=lease)
        result.append(callback(SimpleNamespace(**values)))
        g.io.close_cache()
        return {'native_acceptance':False,'source_context':True}
    try:
        f.boot.run(run)
        if result and callable(result[0]):result[0]()
    finally:
        owner_test.finish(x,lease)
    return result[0]


def intent(t, scenario='F01', case='1'*32):
    roles=next(c.roles for c in __import__('scripts.observation_runtime.aip06_native_scenario_bindings',fromlist=['contracts']).contracts() if c.id==scenario)
    commands={r:(t.x.intent.plan()['executable'],'-B',WORKER,*(() if r not in ('race_one','race_two') else ('--injected-role',r))) for r in roles}
    return t.factory.intent(scenario,case,commands)


@pytest.mark.parametrize('damage',['unknown','manifest','case-id','budget','root','schedule','evidence','accounts',
                                  'roles','target','duplicate-command','duplicate-case','stale-current','job','targets','timeout'])
def test_case_factory_refuses_exact_contract_damage_before_any_context_allocation(monkeypatch,damage):
    def check(t):
        value=intent(t,scenario='F04' if damage=='duplicate-command' else 'F01')
        if damage=='unknown':value=replace(value,scenario='UNKNOWN')
        elif damage=='manifest':value=replace(value,manifest='f'*64)
        elif damage=='case-id':value=replace(value,case='../escape')
        elif damage=='budget':value=replace(value,budget=())
        elif damage=='root':value=replace(value,root=r'D:\AtlasRuntime')
        elif damage=='schedule':value=replace(value,schedule='f'*64)
        elif damage=='evidence':value=replace(value,evidence='f'*64)
        elif damage=='accounts':value=replace(value,accounts=(('QUALITY_DIPS','USDC'),))
        elif damage=='roles':value=replace(value,commands=())
        elif damage=='target':value=replace(value,targets=(('financial_worker',READER_ENTRY),))
        elif damage=='duplicate-command':value=replace(value,commands=tuple((r,value.commands[0][1]) for r,_ in value.commands))
        elif damage=='duplicate-case':t.factory.create(value,deadline_ns=t.x.now[0]+10**9)
        elif damage=='stale-current':t.f.observer.observe=lambda h:dict(t.factory.binding['child'],created=0)
        elif damage=='job':t.f.observer.members=lambda:set()
        elif damage=='targets':t.controller.profile['targets']=dict(t.controller.profile['targets'],financial_worker=READER_ENTRY)
        deadline=t.x.now[0] if damage=='timeout' else t.x.now[0]+10**9
        before=set(t.x.ledger.state['resources'])
        with pytest.raises((ValueError,KeyError)):t.factory.create(value,deadline_ns=deadline)
        assert t.factory.failed and set(t.x.ledger.state['resources'])==before
    in_controller(monkeypatch,check)


@pytest.mark.parametrize('foreign', [None, object()])
def test_reader_rejects_unowned_case_without_attempting_abort(monkeypatch, foreign):
    def check(t):
        from scripts.observation_runtime.aip06_scoped_context import CaseContext
        aborts = []
        original = CaseContext.abort
        def observed_abort(self, *args, **kwargs):
            aborts.append(self)
            return original(self, *args, **kwargs)
        monkeypatch.setattr(CaseContext, 'abort', observed_abort)
        before = copy.deepcopy(t.x.ledger.state['resources'])
        with pytest.raises(ValueError, match='ORIGINAL_RESERVED_CASE_FOR_READER'):
            t.factory.reader(foreign, None, None, deadline_ns=t.x.now[0]+10**9)
        assert t.factory.failed and aborts == []
        assert t.x.ledger.state['resources'] == before
        assert t.factory.cleanup_failure is None
    in_controller(monkeypatch, check)


def test_failed_initial_ledger_snapshot_clears_only_original_scope(monkeypatch):
    def check(t):
        case = t.factory.create(intent(t), deadline_ns=t.x.now[0]+10**9)
        original = t.g.ledger
        def interrupted(action, *args, **kwargs):
            if action == 'read' and t.factory.pending is case:
                raise ValueError('INJECTED_SNAPSHOT_FAILURE')
            return original(action, *args, **kwargs)
        monkeypatch.setattr(t.g, 'ledger', interrupted)
        with pytest.raises(ValueError, match='INJECTED_SNAPSHOT_FAILURE'):
            case.reserve(deadline_ns=t.x.now[0]+10**9)
        assert case.closed and case.failed and t.factory.failed
        assert t.factory.pending is None and t.port.scoped_case is None
        assert case.baseline is None and case.reservation is None
        assert not t.factory.cleanup_failure
        monkeypatch.setattr(t.g, 'ledger', original)
    in_controller(monkeypatch, check)


def test_release_order_conflict_keeps_case_open_until_original_marker_restored(monkeypatch):
    def check(t):
        case = t.factory.create(intent(t), deadline_ns=t.x.now[0]+10**9)
        ticket = case.reserve(deadline_ns=t.x.now[0]+10**9)
        original_release = t.g.release
        releases = []
        def counted_release(key):
            releases.append(key)
            return original_release(key)
        monkeypatch.setattr(t.g, 'release', counted_release)
        before = copy.deepcopy(t.x.ledger.state['resources'])
        t.port.scoped_case = object()
        with pytest.raises(ValueError, match='ORIGINAL_SCOPED_CASE_RELEASE_ORDER'):
            case.abort(ticket, deadline_ns=t.x.now[0]+10**9)
        assert releases == [] and t.x.ledger.state['resources'] == before
        assert not case.closed and t.factory.pending is case
        assert t.port.scoped_case is not case
        t.port.scoped_case = case
        assert case.abort(ticket, deadline_ns=t.x.now[0]+10**9)
        assert case.closed and t.factory.pending is None and t.port.scoped_case is None
    in_controller(monkeypatch, check)


@pytest.mark.parametrize('bad_map', [[], (), False, 'F01'])
@pytest.mark.parametrize('field', ['contexts', 'fault_drivers'])
def test_dispatcher_refuses_non_dictionary_binding_maps(bad_map, field):
    from scripts.observation_runtime.aip06_native_scenario_bindings import bindings
    with pytest.raises(ValueError, match='EXACT_NATIVE_BINDING_MAP_TYPES'):
        bindings({}, **{field: bad_map})


def test_dispatcher_refuses_fault_driver_for_reviewed_source_case():
    from scripts.observation_runtime.aip06_native_scenario_bindings import bindings, contracts
    reviewed = next(c.id for c in contracts() if c.source_case is not None)
    with pytest.raises(ValueError, match='NO_FAULT_DRIVER_ON_REVIEWED_SOURCE_CASE'):
        bindings({}, fault_drivers={reviewed: object()})


def test_ownership_probes_cannot_reserve_without_reviewed_native_producer(monkeypatch):
    def check(t):
        from scripts.observation_runtime.aip06_native_scenario_bindings import contracts
        contract = next(c for c in contracts() if c.id == 'OWNERSHIP-PROBES')
        assert contract.source_case is None
        case = t.factory.create(intent(t, scenario='OWNERSHIP-PROBES'),
                                deadline_ns=t.x.now[0]+10**9)
        before = copy.deepcopy(t.x.ledger.state['resources'])
        binding = t.factory.as_bindings()['OWNERSHIP-PROBES']
        with pytest.raises(ValueError, match='ACTUAL_NATIVE_FAULT_LOAD_PRODUCER_MISSING:OWNERSHIP-PROBES'):
            binding.reserve(t.g, deadline_ns=t.x.now[0]+10**9)
        assert case.reservation is None
        assert t.factory.pending is None
        assert t.x.ledger.state['resources'] == before
    in_controller(monkeypatch, check)


def test_physical_host_handoff_is_copy_only_and_cannot_grant_execution(monkeypatch):
    def check(t):
        case = t.factory.create(intent(t), deadline_ns=t.x.now[0]+10**9)
        with pytest.raises(ValueError, match='ORIGINAL_RESERVED_CASE_FOR_PHYSICAL_HOST_HANDOFF'):
            case.physical_host_handoff({}, deadline_ns=t.x.now[0]+10**9)
        ticket = case.reserve(deadline_ns=t.x.now[0]+10**9)
        with pytest.raises(ValueError, match='ORIGINAL_RESERVED_CASE_FOR_PHYSICAL_HOST_HANDOFF'):
            case.physical_host_handoff({**ticket, 'held': False}, deadline_ns=t.x.now[0]+10**9)
        handoff = case.physical_host_handoff(ticket, deadline_ns=t.x.now[0]+10**9)
        assert handoff['native_acceptance'] is False
        assert handoff['schema'] == 'AIP06_PHYSICAL_CASE_HOST_HANDOFF_V1'
        assert handoff['case']['intent']['scenario'] == 'F01'
        handoff['reservation']['held'] = False
        handoff['case']['owners'].clear()
        assert case.reservation['held'] is True
        assert case.wire()['owners'] == [t.g.owner]
        with pytest.raises(ValueError, match='SEPARATELY_GUARDED_PHYSICAL_CASE_HOST_BINDING_REQUIRED'):
            case.require_execution()
        assert case.abort(ticket, deadline_ns=t.x.now[0]+10**9)
    in_controller(monkeypatch, check)


def test_physical_host_handoff_requires_inherited_scope_integrity_and_original_ledger(monkeypatch):
    def check(t):
        from scripts.observation_runtime.aip06_scoped_context import verify_physical_host_handoff
        case = t.factory.create(intent(t), deadline_ns=t.x.now[0]+10**9)
        ticket = case.reserve(deadline_ns=t.x.now[0]+10**9)
        packet = case.physical_host_handoff(ticket, deadline_ns=t.x.now[0]+10**9)
        descriptor = {'binding': {'parent': t.lease.binding.runtime},
                      'source_pins': t.factory.plan['source_pins'],
                      'targets': t.controller.profile['targets'],
                      'argv': list(dict(case.intent.commands)[case.roles[0]])}
        verified = verify_physical_host_handoff(packet, descriptor, t.g)
        assert verified == packet and verified is not packet
        for field, value in [('native_acceptance', True), ('integrity', '0'*64),
                             ('schema', 'OTHER')]:
            damaged = copy.deepcopy(packet)
            damaged[field] = value
            with pytest.raises(ValueError, match='CLOSED_INTEGRITY_BOUND_PHYSICAL_HOST_HANDOFF'):
                verify_physical_host_handoff(damaged, descriptor, t.g)
        damaged = copy.deepcopy(packet)
        damaged['reservation']['held'] = False
        damaged['integrity'] = digest({k:v for k,v in damaged.items() if k != 'integrity'})
        with pytest.raises(ValueError, match='EXACT_PHYSICAL_HOST_RESERVATION_SCOPE'):
            verify_physical_host_handoff(damaged, descriptor, t.g)
        for changed in ('scenario', 'case', 'manifest', 'evidence', 'roles'):
            damaged = copy.deepcopy(packet)
            damaged['reservation'][changed] = 'untrusted' if changed != 'roles' else ()
            damaged['integrity'] = digest({k:v for k,v in damaged.items() if k != 'integrity'})
            with pytest.raises(ValueError, match='EXACT_PHYSICAL_HOST_RESERVATION_SCOPE'):
                verify_physical_host_handoff(damaged, descriptor, t.g)
        assert case.abort(ticket, deadline_ns=t.x.now[0]+10**9)
        with pytest.raises(ValueError, match='ORIGINAL_PHYSICAL_HOST_RESERVATION_STILL_HELD'):
            verify_physical_host_handoff(packet, descriptor, t.g)
    in_controller(monkeypatch, check)


def test_dispatcher_requires_explicit_physical_host_gate_even_for_context_proxy(monkeypatch):
    def check(t):
        from scripts.observation_runtime.aip06_native_scenario_bindings import NativeScenarioBinding
        case = t.factory.create(intent(t), deadline_ns=t.x.now[0]+10**9)
        ticket = case.reserve(deadline_ns=t.x.now[0]+10**9)
        binding = t.factory.as_bindings()['F01']
        class Proxy:
            def __getattr__(self, key):
                if key == 'require_execution':
                    raise AttributeError(key)
                return getattr(case, key)
        proxy = Proxy()
        replaced = NativeScenarioBinding(binding.contract, source_pins=binding.source_pins, context=proxy)
        with pytest.raises(ValueError, match='EXPLICIT_PHYSICAL_CASE_HOST_EXECUTION_GATE_REQUIRED'):
            replaced.execute(t.controller, t.g, ticket, deadline_ns=t.x.now[0]+10**9)
        assert case.abort(ticket, deadline_ns=t.x.now[0]+10**9)
    in_controller(monkeypatch, check)


@pytest.mark.parametrize('damage', ['closed', 'foreign', 'failed', 'case-failed'])
def test_dispatcher_snapshot_refuses_unhealthy_or_foreign_case(monkeypatch, damage):
    def check(t):
        case = t.factory.create(intent(t), deadline_ns=t.x.now[0]+10**9)
        if damage == 'closed':
            case.closed = True
        elif damage == 'foreign':
            t.factory.cases['F01'] = object()
        elif damage == 'case-failed':
            case.failed = True
        else:
            t.factory.failed = True
        with pytest.raises(ValueError, match='HEALTHY_ORIGINAL_SCOPED_BINDING_SNAPSHOT'):
            t.factory.as_bindings()
        assert t.factory.failed
    in_controller(monkeypatch, check)


def test_joined_bootstrap_case_bridge_reservation_raw_reader_and_release(monkeypatch):
    def check(t):
        from scripts.observation_runtime.aip06_acceptance_control import GuardedScenarioBridge,scenarios
        case=t.factory.create(intent(t),deadline_ns=t.x.now[0]+10**9)
        binding=t.factory.as_bindings()['F01'];binding.check(t.controller,t.g,deadline_ns=t.x.now[0]+10**9)
        scenario=next(s for s in scenarios() if s.id=='F01')
        bridge=GuardedScenarioBridge(t.controller,t.g,t.factory.as_bindings())
        ticket=bridge.reserve(scenario,deadline_ns=t.x.now[0]+10**9)
        assert ticket['key'] in t.x.ledger.state['resources'] and not t.x.ledger.state['resources'][ticket['key']]['closed']
        assert t.factory.pending is case and t.port.scoped_case is case
        with pytest.raises(ValueError,match='PHYSICAL_CASE_HOST_BINDING_REQUIRED'):
            binding.execute(t.controller,t.g,ticket,deadline_ns=t.x.now[0]+10**9)
        descriptor={'binding':{'parent':t.factory.binding['child']},'source_pins':t.factory.plan['source_pins'],
                    'targets':t.controller.profile['targets'],'argv':list(ticket['commands']['financial_worker'])}
        assert verify_inherited_scope(case.wire(),descriptor)['intent']['case']==case.intent.case
        case.admit(ticket['commands']['financial_worker'])
        with pytest.raises(ValueError):case.admit((t.factory.plan['executable'],'-B',WORKER,'extra'))
        # Independent raw providers are exercised separately below. No financial
        # producer or run_reviewed_tests is executed by this source lifecycle.
        assert case.abort(ticket,deadline_ns=t.x.now[0]+10**9)
        assert case.closed and t.port.scoped_case is None and t.factory.pending is None
        assert t.x.ledger.state['resources'][ticket['key']]['closed']
        with pytest.raises(ValueError):case.release(ticket,{},deadline_ns=t.x.now[0]+10**9)
    in_controller(monkeypatch,check)


@pytest.mark.parametrize('damage',['partial-create','partial-output','abort','unreleased-handle','failed-release','late-release'])
def test_partial_construction_and_abort_preserve_original_release_accounting(monkeypatch,damage):
    def check(t):
        case=t.factory.create(intent(t),deadline_ns=t.x.now[0]+10**9)
        if damage=='partial-create':
            original=t.g.mkdir
            def refused(*a,**k):original(*a,**k);raise ValueError('interrupted after original create')
            monkeypatch.setattr(t.g,'mkdir',refused)
        if damage=='partial-output':monkeypatch.setattr(t.g,'write',lambda *a:(_ for _ in ()).throw(ValueError('write interrupted')))
        if damage.startswith('partial'):
            with pytest.raises(ValueError):case.reserve(deadline_ns=t.x.now[0]+10**9)
            assert case.closed and t.factory.failed and t.factory.pending is None
            return
        ticket=case.reserve(deadline_ns=t.x.now[0]+10**9)
        if damage=='unreleased-handle':t.g.ledger('reserve',t.g.owner,'INJECTED-LEAK','handle')
        original_closed=t.g.io.closed
        if damage=='failed-release':monkeypatch.setattr(t.g.io,'closed',lambda *a:False)
        deadline=t.x.now[0] if damage=='late-release' else t.x.now[0]+10**9
        if damage=='abort':assert case.abort(ticket,deadline_ns=deadline)
        else:
            with pytest.raises(ValueError):case.abort(ticket,deadline_ns=deadline)
            assert not case.closed and t.factory.pending is case
            # Test fixture cleanup is explicit and does not turn FAIL into PASS.
            if damage=='unreleased-handle':t.x.ledger.close(t.g.owner,'INJECTED-LEAK',observer=SimpleNamespace(closed=lambda *a:True))
            elif damage=='failed-release':monkeypatch.setattr(t.g.io,'closed',original_closed)
            case._close(t.x.now[0]+10**9)
    in_controller(monkeypatch,check)


@pytest.mark.parametrize('damage',['missing','duplicate-id','owner-session','missing-access','wrong-manifest'])
def test_reader_parent_factory_refuses_missing_conflicting_or_unapproved_context(monkeypatch,damage):
    def check(t):
        case=t.factory.create(intent(t),deadline_ns=t.x.now[0]+10**9);case.reserve(deadline_ns=t.x.now[0]+10**9)
        value=ReaderIntent('2'*32,case.intent.case,case.intent.manifest)
        if damage=='duplicate-id':t.factory.readers.add(value.reader)
        elif damage=='missing-access':value=replace(value,access=())
        elif damage=='wrong-manifest':value=replace(value,manifest='f'*64)
        with pytest.raises((ValueError,AttributeError)):
            t.factory.reader(case,value,None if damage!='owner-session' else t.lease,deadline_ns=t.x.now[0]+10**9)
        assert t.factory.failed and case.closed and t.factory.pending is None
    in_controller(monkeypatch,check)


@pytest.mark.parametrize('provider', [None, (), [], (object(), object()), (object(),),
                                     (object(), object(), object()), {'adapters': object()}])
def test_reader_provider_host_refuses_unqualified_pairs_before_guard_access(provider):
    from scripts.observation_runtime.aip06_reader_context_entry import prepare_reader_from_provider
    with pytest.raises(ValueError, match='EXACT_INDEPENDENT_READER_PROVIDER_HOST_PAIR_REQUIRED'):
        prepare_reader_from_provider(provider)


@pytest.mark.parametrize('deadline', [None, False, 0, -1, 1.5, '100'])
def test_reader_collection_requires_explicit_bounded_deadline_before_guard_access(deadline):
    from scripts.observation_runtime.aip06_reader_context_entry import collect_reader_from_provider
    with pytest.raises(ValueError, match='EXPLICIT_BOUNDED_READER_COLLECTION_DEADLINE'):
        collect_reader_from_provider(None, deadline_ns=deadline)


def test_reader_collection_refuses_missing_provider_before_guard_access():
    from scripts.observation_runtime.aip06_reader_context_entry import collect_reader_from_provider
    with pytest.raises(ValueError, match='EXACT_INDEPENDENT_READER_PROVIDER_HOST_PAIR_REQUIRED'):
        collect_reader_from_provider(None, deadline_ns=10**9)


def test_native_reader_entry_cannot_auto_load_a_provider_or_create_authority():
    from scripts.observation_runtime.aip06_reader_context_entry import main
    with pytest.raises(ValueError,match='NOT_YET_QUALIFIED'):main()
    with pytest.raises(ValueError):IndependentGrader.inspect_scoped(object(),{},deadline_ns=1)
    with pytest.raises(ValueError,match='NOT_QUALIFIED'):IndependentGrader.grade_native(None,{})


@pytest.mark.parametrize('damage',['', 'missing','owner','pins','budget','role','command','ancestry','account','collision'])
def test_private_scope_forwarding_is_only_a_restriction_and_preserves_global_history(monkeypatch,damage):
    def check(t):
        case=t.factory.create(intent(t),deadline_ns=t.x.now[0]+10**9)
        scope=case.wire();desc={'binding':{'parent':t.factory.binding['child']},
            'source_pins':t.factory.plan['source_pins'],'targets':t.controller.profile['targets'],
            'argv':list(dict(case.intent.commands)['financial_worker'])}
        before=copy.deepcopy(t.controller.profile)
        if damage=='missing':scope=None
        elif damage=='owner':scope['owner']='f'*64
        elif damage=='pins':scope['source_pins']='f'*64
        elif damage=='budget':scope['intent']['budget']=[]
        elif damage=='role':scope['intent']['targets']=(('query',WORKER),)
        elif damage=='command':desc['argv'].append('unexpected')
        elif damage=='ancestry':scope['owners']=[]
        elif damage=='account':scope['intent']['accounts']=(('HYPERLIQUID','USD'),)
        elif damage=='collision':scope['owners']=[scope['owner'],scope['owner']]
        if damage:
            with pytest.raises(ValueError):verify_inherited_scope(scope,desc)
        else:
            assert verify_inherited_scope(scope,desc)==scope
            transfer={**scope,'owner':t.factory.context.root_owner,'owners':[t.factory.context.root_owner]}
            transfer['intent']={**scope['intent'],'evidence':digest({'manifest':case.intent.manifest,
                'case':case.intent.case,'owner':t.factory.context.root_owner})}
            forwarded=forward_scope(transfer,t.g)
            assert forwarded['owners']==[t.factory.context.root_owner,t.g.owner]
            assert forwarded['intent']==transfer['intent']
            with pytest.raises(ValueError):forward_scope(forwarded,t.g)
        assert before==t.controller.profile and not t.port.sessions
    in_controller(monkeypatch,check)


def test_held_context_directory_uses_original_nativeio_reservation_and_close_proof():
    from test_aip06_windows_adapters import io_fixture
    x=io_fixture()
    with x.guard.installed():
        x.guard.mkdir(ROOTS['E'])
        key=x.guard.mkdir(ntpath.join(ROOTS['E'],'INJECTED-held-context'),hold=True)
        assert x.s.ledger.state['resources'][key]=={'owner':x.guard.owner,'kind':'directory','closed':False}
        assert x.io.closed(x.guard.owner,key)
        x.guard.release(key);x.io.close_cache()
        assert x.s.ledger.state['resources'][key]['closed'] and not x.calls.handles


def reader_fixture(t, case, damage=''):
    """Injected original-handle/IPC session, serial independent guard contexts.

    The parent GuardedProcess's OS exchange/exit adapters are injected here;
    this is NOT suspended Windows reader launch or native release acceptance.
    """
    from test_aip06_windows_acceptance_adapters import bundle_fixture
    from scripts.observation_runtime.aip06_windows_process import NativeProcessObserver
    from scripts.observation_runtime.launch_ownership import LaunchRequest, RetainedLaunchBinding
    from scripts.observation_runtime.aip06_windows_acceptance_adapters import PinnedWindowsRead, WindowsProcessEvidence
    from scripts.observation_runtime.aip06_native_session import Session
    from scripts.observation_runtime.aip06_fixture_guard import GuardedProcess
    b=bundle_fixture(damage if damage in ('state-zero','pid-zero-listener','reader-error','survivor') else '')
    clock=lambda:t.x.now[0]
    b.calls.rows[20]={k:v for k,v in t.factory.binding['child'].items() if k in ('pid','created','image','parent_pid','command_line')}
    b.calls.rows[30].update(parent_pid=20,created=b.calls.rows[20]['created']+1000,image=b.calls.rows[20]['image'],
                           command_line=list2cmdline(bootstrap_argv(t.factory.plan['executable'],'b'*32)))
    b.calls.exits.clear()
    image=(b.calls.rows[30]['image'],tuple(t.factory.binding['child']['file_id']),t.factory.binding['child']['sha256'])
    api=NativeProcessObserver(calls=b.calls,cim=b.cim,images={ntpath.normcase(image[0]):{'file_id':list(image[1]),'sha256':image[2]}},clock_ns=clock)
    api.job=200;api.parent=20
    req=LaunchRequest('acceptance_worker','b'*32,'direct',image,image,b.calls.rows[30]['command_line'],b.calls.rows[30]['command_line'])
    binding=RetainedLaunchBinding(api,req,20,30);binding.bind_runtime(30,{'pid':30,'nonce':req.nonce,'role':req.role})
    owner=t.x.ledger.register_owner(binding.runtime)
    t.x.ledger.reserve(t.g.owner,'INJECTED-reader-process','launch')
    t.x.ledger.bind_reserved_process('INJECTED-reader-process',t.g.owner,binding,30)
    process=WindowsProcessEvidence(observer=api,reader_binding=binding,clock_ns=clock)
    b.bundle.processes=process;b.bundle.providers['HANDLES']=process;b.bundle.clock=clock;b.bundle.pin=t.factory.context.intent.sha256
    # Existing concrete providers are exercised; their OS calls remain injected.
    b.clock=lambda:(t.x.now.__setitem__(0,t.x.now[0]+1000) or t.x.now[0])
    acl=object.__new__(PinnedWindowsRead);acl.pins={image[0]:{'file_id':list(image[1]),'sha256':image[2]}}
    def read_acl(path,**kw):
        assert path==image[0] and kw['deadline_ns']>clock()
        if damage=='acl-denied':raise ValueError('injected protected ACL denial')
        return b'INJECTED_ACL_READ_NOT_NATIVE_PROOF'
    acl.read_bytes=read_acl
    wire={'scope':SCOPE_HASH,'session':'a'*32,'nonce':'b'*32,'parent':binding.parent,'child':binding.runtime,
          'job':200,'launch':{'command':req.launch_command}}
    frames=[]
    def channels():
        a,z=fixture.MemoryEndpoint(),fixture.MemoryEndpoint();a.peer=z;z.peer=a
        parent=Channel(a,binding=wire,clock_ns=clock,account_scope=fixture.ACCOUNTS,role='PARENT')
        child=Channel(z,binding=wire,clock_ns=clock,account_scope=fixture.ACCOUNTS,role='CHILD')
        return SimpleNamespace(s=SimpleNamespace(ledger=t.x.ledger,now=t.x.now),owner=owner,
                               a=a,b=z,parent=parent,child_channel=child)
    # Build now, run only after the controller guard has exited its context.
    old=fixture.channels;fixture.channels=channels
    try:
        f=fixture.bootstrap_fixture(target_override=READER_ENTRY,pins_override=t.factory.plan['source_pins'],
                                    output_handler=lambda value:frames.append({'payload':value}))
    finally:fixture.channels=old
    session=Session('readonly_reader',{'name':'readonly_reader','request':req},{},('INJECTED-reader-process',),
        (t.factory.plan['executable'],'-B',READER_ENTRY),{},api,binding=binding,creation_attempted=True,
        creation_native=b.calls.native(30),receipt={'guarded':True,'scope':SCOPE_HASH,'nonce':req.nonce,'owner':owner},target_released=True,suspended=False,
        channel=SimpleNamespace(saved_outputs=frames))
    child=GuardedProcess(t.g,session,session.plan,session.keys,session.argv)
    t.port.sessions.append(session);t.g.ownership.bindings['readonly_reader']=binding
    t.port.resources_closed=lambda s,keys:s.closed
    def cleanup():
        b.calls.exits.add(30);b.calls.jobs[200].clear()
        session.closed=child.closed=True
        t.x.ledger.close(owner,'INJECTED-reader-process',observer=SimpleNamespace(closed=lambda *a:True))
    def exchange(packet,timeout=12):
        # The reader's already completed, authenticated framed reply is retained.
        assert packet['case']['case']==case.intent.case and 0<timeout<=6 and frames
        cleanup();return ('','')
    child.communicate=exchange
    def run_reader(packet):
        f.boot.prepare();f.x.parent.send('INPUT',packet,deadline_ns=clock()+10**9)
        def run(target):
            from scripts.observation_runtime.aip06_session_io import ChildSessionIO
            from scripts.observation_runtime.aip06_reader_context_entry import prepare_reader
            stream=ChildSessionIO(f.boot.guard,clock_ns=clock)
            f.boot.guard.processes=SimpleNamespace(runtime=SimpleNamespace(identity=f.identity,
                descriptor={'argv':list(session.argv),'source_pins':t.factory.plan['source_pins'],
                            'targets':t.controller.profile['targets'],'binding':wire,'case_scope':case.wire()}),
                read_input=stream.read_input,emit_output=stream.emit_output)
            acl.allocations=SimpleNamespace(resources=f.boot.guard.resources,owner=f.boot.guard.owner)
            if damage=='owner-collision':b.calls.current_handle=20
            if damage=='stale-identity':b.calls.rows[30]['created']+=10
            if damage=='missing-job':b.calls.jobs[200].add(999)
            if damage=='missing-reader':b.bundle.providers.pop('NETSTAT')
            context=prepare_reader(b.bundle,acl)
            request=packet['request']
            result=IndependentGrader.inspect_scoped(context,request,deadline_ns=clock()+10**9)
            assert not result['native_acceptance']
            return {'native_acceptance':False}
        return f.boot.run(run)
    return SimpleNamespace(**locals())


@pytest.mark.parametrize('damage',['duplicate-birth','receipt','creation','empty-keys','command','unregistered','job'])
def test_reader_lease_cannot_adopt_or_redeclare_a_native_identity(monkeypatch,damage):
    def check(t):
        from scripts.observation_runtime.launch_ownership import identity
        case=t.factory.create(intent(t),deadline_ns=t.x.now[0]+10**9)
        ticket=case.reserve(deadline_ns=t.x.now[0]+10**9);r=reader_fixture(t,case)
        if damage=='duplicate-birth':t.factory.reader_births.add(identity(r.binding.runtime))
        elif damage=='receipt':r.session.receipt=None
        elif damage=='creation':r.session.creation_native={**r.session.creation_native,'created':0}
        elif damage=='empty-keys':r.child.keys=()
        elif damage=='command':r.child.argv=(*r.child.argv,'unapproved')
        elif damage=='unregistered':r.child.keys=('no-such-reservation',);r.session.keys=r.child.keys
        elif damage=='job':r.b.calls.jobs[200].add(999)
        try:
            with pytest.raises(ValueError):
                t.factory.reader(case,ReaderIntent('2'*32,case.intent.case,case.intent.manifest),r.child,
                                 deadline_ns=t.x.now[0]+10**9)
            assert t.factory.failed and not case.closed and t.factory.cleanup_failure
        finally:
            r.cleanup()
            case.abort(ticket,deadline_ns=t.x.now[0]+10**9)
    in_controller(monkeypatch,check)


@pytest.mark.parametrize('damage',['', 'owner-collision','stale-identity','missing-job','missing-reader','acl-denied',
                                  'state-zero','pid-zero-listener','reader-error','survivor','stale-reply','wrong-reply','timeout',
                                  'missing-ack','duplicate-ack','replay','result-tamper','wrong-private-scope','wrong-access',
                                  'raw-not-dict','raw-cuts-not-list','raw-cuts-short','raw-cut-time-string'])
def test_separate_reader_context_private_frames_and_complete_parent_release(monkeypatch,damage):
    def start(t):
        case=t.factory.create(intent(t),deadline_ns=t.x.now[0]+10**9)
        ticket=case.reserve(deadline_ns=t.x.now[0]+10**9)
        r=reader_fixture(t,case,damage)
        value=ReaderIntent('2'*32,case.intent.case,case.intent.manifest)
        parent=t.factory.reader(case,value,r.child,deadline_ns=t.x.now[0]+10**9)
        request={'scope':SCOPE_HASH,'manifest':case.intent.manifest,'scenario':case.contract.id,'reservation':ticket['key'],'root':ROOTS['E']}
        packet=parent.prepare(request,deadline_ns=t.x.now[0]+10**9)
        if damage=='wrong-private-scope':packet['case']['accounts']=[['QUALITY_DIPS','USDC']]
        if damage=='wrong-access':packet['reader']['access']=[]
        def after():
            try:
                if damage in ('owner-collision','stale-identity','missing-job','missing-reader','acl-denied',
                              'state-zero','pid-zero-listener','reader-error','survivor','wrong-private-scope','wrong-access'):
                    with pytest.raises((ValueError,KeyError)):r.run_reader(packet)
                else:
                    r.run_reader(packet)
                    if damage=='stale-reply':r.frames[0]['payload']['raw']['cuts'][0]['started_ns']=0
                    if damage=='wrong-reply':r.frames[0]['payload']['request']='f'*64
                    if damage=='raw-not-dict':r.frames[0]['payload']['raw']=None
                    if damage=='raw-cuts-not-list':r.frames[0]['payload']['raw']['cuts']='bad'
                    if damage=='raw-cuts-short':r.frames[0]['payload']['raw']['cuts'].pop()
                    if damage=='raw-cut-time-string':r.frames[0]['payload']['raw']['cuts'][0]['started_ns']='bad'
                    if damage=='missing-ack':r.frames.clear();r.child.communicate=lambda *a,**kw:r.cleanup()
                    if damage=='duplicate-ack':r.frames.append(copy.deepcopy(r.frames[0]))
                    with t.g.installed():
                        deadline=t.x.now[0] if damage=='timeout' else t.x.now[0]+10**9
                        if damage not in ('','replay','result-tamper'):
                            with pytest.raises(ValueError):IndependentGrader.inspect_scoped(parent,request,deadline_ns=deadline)
                        else:
                            result=IndependentGrader.inspect_scoped(parent,request,deadline_ns=deadline)
                            assert r.b.order[-4:]==['CIM','IP_HELPER','NETSTAT','PROCESS']
                            if damage=='replay':
                                with pytest.raises(ValueError):IndependentGrader.inspect_scoped(parent,request,deadline_ns=deadline)
                            elif damage=='result-tamper':
                                result['sequence']+=1
                                with pytest.raises(ValueError):case.release(ticket,result,deadline_ns=t.x.now[0]+10**9)
                            else:assert case.release(ticket,result,deadline_ns=t.x.now[0]+10**9)
            finally:
                r.cleanup()
                if not case.closed:
                    # Explicit model cleanup only; original failure stays FAIL.
                    with t.g.installed():case.abort(ticket,deadline_ns=t.x.now[0]+10**9)
        return after
    in_controller(monkeypatch,start)
