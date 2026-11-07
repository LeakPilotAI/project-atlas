"""Actual native lanes and durable Stop attribution, synthetic authority only."""
import copy

import pytest
import test_unified_actual_native_lanes as native
from app.services.unified_paper_runtime import (
    UnifiedControlStopBridge,
    UnifiedPaperRuntime,
)

system=native.system

@pytest.mark.asyncio
async def test_user_stop_native_history_and_duplicate(system):
    s=system
    await native.cycle(s)
    bridge=UnifiedControlStopBridge(s.r)
    result=bridge.request_stop('SHUTDOWN_FLATTEN')
    assert result['outcome']['status']=='FLATTENED',result
    history=s.custody.read_trade_history(s.r.grant)
    assert history['status']=='ACKNOWLEDGED',history
    assert len(history['rows'])==1 and history['rows'][0]['reason']=='USER_SHUTDOWN'
    assert history['rows'][0]['stop_command_id']==s.r.stop_context['command_id']
    assert bridge.request_stop('SHUTDOWN_FLATTEN')==result
    assert history==s.custody.read_trade_history(s.r.grant)

@pytest.mark.asyncio
async def test_strategy_exit_not_relabelled_after_stop(system):
    s=system;await native.cycle(s)
    s.tick(s.clock()+1,stock_bid='120',stock_ask='120.1',monitor={'classification':'THESIS_BROKEN'})
    await native.cycle(s)
    before=s.custody.read_trade_history(s.r.grant)
    assert before['status']=='ACKNOWLEDGED',before
    assert before['rows'][0]['reason']=='STRATEGY_EXIT'
    UnifiedControlStopBridge(s.r).request_stop('SHUTDOWN_FLATTEN')
    assert s.custody.read_trade_history(s.r.grant)['rows']==before['rows']

@pytest.mark.asyncio
@pytest.mark.parametrize('reason',['RISK_SHUTDOWN','UNKNOWN'])
async def test_non_user_stop_is_not_user_exit(system,reason):
    s=system;await native.cycle(s)
    assert s.r.stop(reason=reason)['state']=='STOPPED'
    h=s.custody.read_trade_history(s.r.grant)
    assert h['status']=='ACKNOWLEDGED',h
    assert h['rows'][0]['reason']==reason

@pytest.mark.asyncio
async def test_unknown_ack_never_becomes_completed_user_exit(system):
    s=system;await native.cycle(s);s.a.fail_ack=True
    outcome=UnifiedControlStopBridge(s.r).request_stop('SHUTDOWN_FLATTEN')
    assert outcome['outcome']['status']=='SHUTDOWN_INCOMPLETE'
    h=s.custody.read_trade_history(s.r.grant)
    assert h['status']=='INCOMPLETE' and not h['rows']
    assert not s.custody.verify_restart({'session_id':'not-recovery-authority'})

@pytest.mark.asyncio
async def test_no_position_stop_does_not_invent_exit(system):
    s=system
    assert UnifiedControlStopBridge(s.r).request_stop('SHUTDOWN_FLATTEN')['outcome']['status']=='FLATTENED'
    assert s.custody.read_trade_history(s.r.grant)['rows']==[]

@pytest.mark.asyncio
async def test_forged_exit_attribution_refuses_before_reservation(system):
    s=system;await native.cycle(s)
    s.tick(s.clock()+1,stock_bid='120',stock_ask='120.1',monitor={'classification':'THESIS_BROKEN'})
    await s.r.poll();proposal=await s.r.lanes['QUALITY_DIPS'].next_proposal(s.r.observations['QUALITY_DIPS'])
    request={'lane':'QUALITY_DIPS','grant':s.r.grant,'proposal':proposal,'exit_classification':{'reason':'USER_SHUTDOWN'}}
    before=s.journal.snapshot()
    with s.custody.lease(request) as lease,pytest.raises(ValueError,match='CLASSIFICATION'):
        lease.verify(request)
    assert before==s.journal.snapshot()

@pytest.mark.asyncio
async def test_stale_stop_and_abrupt_restart_preserve_position(system):
    s=system;await native.cycle(s)
    before=copy.deepcopy(s.q.writer._cut())
    s.s.x.n.now[0]+=60
    outcome=UnifiedControlStopBridge(s.r).request_stop('SHUTDOWN_FLATTEN')
    assert outcome['outcome']['status']=='SHUTDOWN_INCOMPLETE'
    assert s.q.writer._cut()==before
    history=s.custody.read_trade_history(s.r.grant)
    assert history['rows']==[] and history['unresolved'][0]['state']=='POSITION_OPEN_NOT_AN_EXIT'
    restarted=UnifiedPaperRuntime(lanes=s.r.lanes,installation=s.r.installation,portfolio=s.custody,clock=s.clock)
    with pytest.raises(ValueError):restarted.start({'session_id':'fresh-is-not-recovery'})

@pytest.mark.asyncio
@pytest.mark.parametrize('side',['LONG','SHORT'])
async def test_perp_partial_fill_and_partial_qd_then_user_stop(system,side):
    s=system
    if side=='SHORT':
        s.p.packet['candles']['BTC']=[{'close':120-.3*i} for i in range(48)]
        s.p.packet['markets'][0]['funding_rate']='0.001'
    await native.cycle(s)
    order=next(iter(s.p.orders.snapshot()['state']['orders'].values()))['order']
    assert order['side']==side
    s.tick(s.clock()+1)
    s.p.packet['maker_fills'][order['order_id']]=s.p.fill_proof(order,quantity='0.6')
    await native.cycle(s)
    s.tick(s.clock()+1,stock_bid='110',stock_ask='110.1',monitor={'evidence_quality':'HIGH','fundamentals_score':60})
    await native.cycle(s)
    outcome=UnifiedControlStopBridge(s.r).request_stop('SHUTDOWN_FLATTEN')
    assert outcome['outcome']['status']=='FLATTENED',outcome
    history=s.custody.read_trade_history(s.r.grant)
    assert history['status']=='ACKNOWLEDGED',history
    assert any(r['reason']=='STRATEGY_EXIT' for r in history['rows'])
    assert {r['lane'] for r in history['rows'] if r['reason']=='USER_SHUTDOWN'}=={'QUALITY_DIPS','HYPERLIQUID'}
    from app.services.paper_financial_replay import number
    assert all(number(r['remaining'])==0 for r in history['rows'] if r['reason']=='USER_SHUTDOWN')
    assert history['accounts']['QUALITY_DIPS']['currency']=='USD'
    assert history['accounts']['HYPERLIQUID']['currency']=='USDC'
    for lane in ('QUALITY_DIPS','HYPERLIQUID'):
        assert number(history['analysis'][lane]['ALL']['net'])==number(history['accounts'][lane]['net'])

@pytest.mark.asyncio
@pytest.mark.parametrize('phase',['before_publication','after_record_before_pin','after_pin'])
async def test_real_stop_child_crash_never_invents_exit(system,phase):
    import json

    from app.services.paper_exit_history import stop_command
    from app.services.paper_financial_replay import digest
    from test_perp_order_crash_race_native import start
    s=system;await native.cycle(s)
    command=stop_command(s.r.grant,'USER_SHUTDOWN',s.clock())
    config={'confinement':str(s.confinement),'portfolio':True,'root':str(s.root/'global'),
        'pin':str(s.pins.path),'now':s.clock(),'manifest':s.binding,
        'event':{'kind':'CLOSE','order_id':'close:'+digest(s.r.grant),'at':s.clock(),
            'payload':{'grant_digest':digest(s.r.grant),'stop_context':command}},
        'reservation':{'fixture':'EXPLICIT_SELF_EXIT_BOUNDARY'}}
    path=s.root/'desktop-crash.json';path.write_text(json.dumps(config),encoding='utf-8')
    before=s.q.writer._cut()
    child=start(path,phase);out,err=child.communicate(timeout=12)
    assert child.returncode==71,(out,err)
    assert before==s.q.writer._cut()
    history=s.custody.read_trade_history(s.r.grant)
    assert not history['rows']
    if phase=='after_record_before_pin':assert history['status']=='INCOMPLETE'
    else:
        assert history['status']=='ACKNOWLEDGED'
        with pytest.raises(ValueError,match='Abandoned|recovery'):
            s.custody.verify_restart({'session_id':'crash-is-not-recovery'})

@pytest.mark.asyncio
async def test_funded_strategy_and_shutdown_performance_reconciles(system):
    from app.services.paper_financial_replay import number
    await native.test_actual_two_strategy_orders_fills_funding_partial_exits_and_shutdown(system)
    history=system.custody.read_trade_history(system.r.grant)
    assert history['status']=='ACKNOWLEDGED',history
    for lane in ('QUALITY_DIPS','HYPERLIQUID'):
        assert number(history['analysis'][lane]['ALL']['net'])==number(history['accounts'][lane]['net'])
    p=system.p.writer._cut()['state']
    assert number(history['analysis']['HYPERLIQUID']['ALL']['funding'])==number(p['funding'])
    assert number(history['analysis']['HYPERLIQUID']['ALL']['costs'])==number(p['costs'])

@pytest.mark.asyncio
@pytest.mark.parametrize('permission',['accepted','absent','unknown','undrained'])
async def test_incomplete_stop_owned_exit_never_claims_financial_final(system,permission):
    import asyncio
    import subprocess
    import sys

    from app.services.paper_financial_replay import digest
    from test_quality_dips_autonomous_runtime_http import owner_module
    s=system
    await s.r.poll()
    proposal=await s.r.lanes['QUALITY_DIPS'].next_proposal(s.r.observations['QUALITY_DIPS'])
    s.r.dispatch('QUALITY_DIPS',proposal)
    if permission=='undrained':
        pending=await s.r.lanes['HYPERLIQUID'].next_proposal(s.r.observations['HYPERLIQUID'])
        s.r.admit_resting(pending)
    child=await asyncio.to_thread(subprocess.Popen,[sys._base_executable,'-B','-c','import sys;print("ready",flush=True);sys.stdin.readline()'],
        stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True,creationflags=subprocess.CREATE_NO_WINDOW)
    try:
        assert child.stdout.readline().strip()=='ready'
        identity=owner_module.observe_pid(child.pid)
        roster={'schema':'ATLAS_UNIFIED_OWNED_ROSTER_V1','session_id':s.r.grant['session_id'],
            'writer_binding':s.binding['roster_digest'],'account_binding':digest({k:digest(w.manifest) for k,w in s.writers.items()}),
            'processes':[identity]}
        calls=[]
        class Close:
            def close_verified(self,value):
                assert value==roster and s.journal.snapshot()['state']['finalized'] is None
                assert owner_module.observe_pid(child.pid)==identity
                child.stdin.close();child.wait(timeout=12);calls.append(value)
                return True
            def verify_exit(self,value):return value==roster and child.poll()==0
        closer=Close();s.ownership.owned_roster=lambda *args:roster
        if permission!='absent':
            s.a.verify_incomplete_owned_shutdown=lambda context,cap,components: (cap is closer
                and context['admission']['state']['entry_closed'] and context['admission']['state']['finalized'] is None
                and any(p['remaining']!='0' for p in context['acknowledged_cuts']['QUALITY_DIPS']['state']['positions'].values()))
        s.s.x.n.now[0]+=60
        if permission=='unknown':s.r.uncertain=True
        outcome=UnifiedControlStopBridge(s.r,owned_close=closer).request_stop('SHUTDOWN_FLATTEN')['outcome']
        assert outcome['status']=='SHUTDOWN_INCOMPLETE' and outcome['position_state']!='FLAT'
        assert s.journal.snapshot()['state']['finalized'] is None
        assert bool(calls)==(permission=='accepted')
        if permission=='accepted':assert outcome['process_shutdown']=='VERIFIED_EXIT_WITH_UNRESOLVED_POSITIONS'
        else:assert child.poll() is None
    finally:
        if child.poll() is None:child.stdin.close();child.wait(timeout=12)
