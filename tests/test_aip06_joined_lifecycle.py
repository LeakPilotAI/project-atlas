"""Joined isolated source qualification; all Windows responses injected."""

from types import SimpleNamespace

import pytest

from scripts.observation_runtime.aip06_fixture_guard import current
from aip06_joined_fixture import Joined


def test_three_joined_financial_lifecycles_preserve_original_accounting_stop_and_restart(tmp_path, monkeypatch):
    import ast,inspect
    from scripts.observation_runtime.aip06_owned_stop import OwnedStopAssembly
    from scripts.observation_runtime.aip06_stop import GuardedStopCollector
    from scripts.observation_runtime.aip06_cleanup_providers import ThreeReaderCleanup, StrictProcessCleanup, GuardedNetstat
    from scripts.observation_runtime.aip06_native_query import ARGS
    from test_aip06_physical_path import query_fixture, _dmtf
    import test_aip06_source_closure as original
    function=original.test_actual_guard_factory_collector_and_original_financial_verifier_complete_three_offline_samples
    observed={};joined=[]
    def factory():
        x=query_fixture();observed['x']=x;return x
    class Assembly(OwnedStopAssembly):
        def ready(self,child,**kw):
            super().ready(child,**kw)
            j=Joined(observed['x'],child).start();j.prove();j.stop();joined.append(j)
            assert self.port.all_members()=={child.pid}
    def collector(**kw):
        x=observed['x'];output=SimpleNamespace(append=x.records.append)
        def empty(**limits):
            return {'complete':True,'error':None,'rows':[],'started_ns':x.now[0],'finished_ns':x.now[0]}
        sockets=ThreeReaderCleanup(readers={'CIM':SimpleNamespace(read=empty),'IP_HELPER':SimpleNamespace(read=empty),
            'NETSTAT':GuardedNetstat(x.guard,ARGS)},port=x.port,output=output,clock_ns=lambda:x.now[0])
        def table(**limits):
            return {'complete':True,'error':None,'started_ns':x.now[0],'finished_ns':x.now[0],
                'rows':[{'ProcessId':r['pid'],'ParentProcessId':r['parent_pid'],'CreationDate':_dmtf(r['created']),
                         'CommandLine':r['command_line'],'ExecutablePath':r['image']}
                        for r in x.calls.rows.values() if r['pid'] not in x.calls.exits]}
        processes=StrictProcessCleanup(port=x.port,tables=SimpleNamespace(read=table),output=output,clock_ns=lambda:x.now[0])
        old_sockets,old_processes=kw['sockets'],kw['processes']
        def socket_cut(**limits):old_sockets.collect(**limits);return sockets.collect(**limits)
        def process_cut(**limits):old_processes.collect(**limits);return processes.collect(**limits)
        kw.update(sockets=SimpleNamespace(collect=socket_cut),processes=SimpleNamespace(collect=process_cut))
        return GuardedStopCollector(**kw)
    namespace=dict(original.__dict__,aggregate_fixture=factory,OwnedStopAssembly=Assembly,GuardedStopCollector=collector)
    exec(compile(ast.parse(inspect.getsource(function)),inspect.getsourcefile(function),'exec'),namespace)
    namespace[function.__name__](tmp_path)
    assert len(joined)==3 and all(j.context.closed and j.witness['ownership_accepted'] is False for j in joined)
    assert not observed['x'].calls.handles and observed['x'].aggregate.generation==2


def test_one_joined_isolated_bootstrap_probes_ack_drain_stop_and_aggregate_release():
    joined=Joined();x=joined.x
    with x.guard.installed():
        parent_guard=current()
        joined.start()
        one,two,refusal=joined.prove()
        assert current() is parent_guard and joined.context_wire.context != joined.context_wire.peer
        assert one['descendants'] and refusal['ownership_accepted'] is False
        joined.stop()
        assert current() is parent_guard and joined.context.closed
        x.calls.finish(joined.f.peer_process.child);joined.f.peer_process.close()
        x.aggregate.close(deadline_ns=x.now[0]+10**9)
        assert not x.calls.handles and all(row['closed'] for row in x.ledger.state['resources'].values())
    assert current() is None


@pytest.mark.parametrize('fault',['missing_ack','incomplete_drain'])
def test_joined_missing_financial_evidence_stays_failed_after_owned_cleanup(fault):
    joined=Joined();x=joined.x
    with x.guard.installed():
        joined.start();joined.prove()
        with pytest.raises(ValueError,match='ACK_OR_DRAIN_CORRELATION'):
            joined.stop(**{fault:True})
        assert joined.context.closed and any(v['state']=='FAILED' for v in x.ledger.state['stops'].values())
        x.calls.finish(joined.f.peer_process.child);joined.f.peer_process.close()
        x.aggregate.close(deadline_ns=x.now[0]+10**9)
        assert not x.calls.handles
        with pytest.raises(ValueError):x.aggregate.rearm(2)


def test_joined_bootstrap_account_mismatch_aborts_only_owned_context():
    joined=Joined(fault='account');x=joined.x
    with x.guard.installed():
        with pytest.raises(ValueError,match='BOOTSTRAP_FAILED'):joined.start()
        assert joined.context.closed and joined.context_result['passed'] is False
        assert not joined.server.is_alive() and not joined.running.is_set()
        assert all(not x.ledger.state['resources'][k]['closed'] for k in joined.box['lease'].keys)
