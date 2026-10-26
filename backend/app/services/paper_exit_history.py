"""Versioned exit attribution over immutable financial/global evidence; no writer."""
from decimal import DecimalException, Inexact, localcontext

from app.services.paper_financial_replay import (
    apply_event,
    body,
    digest,
    initial_state,
    number,
    strict,
    text,
)

REASONS=('STRATEGY_EXIT','STOP_LOSS','TAKE_PROFIT','USER_SHUTDOWN','RISK_SHUTDOWN','UNKNOWN')

def stop_command(grant, reason, at):
    if reason not in ('USER_SHUTDOWN','RISK_SHUTDOWN','UNKNOWN') or type(at) is not int or at<0:
        raise ValueError('EXPLICIT_STOP_REASON_AND_CLOCK_REQUIRED')
    text(grant['session_id'])
    return {'schema':'ATLAS_DESKTOP_STOP_V1','session_id':grant['session_id'],
        'command_id':'stop:'+digest([digest(grant),reason]),'reason':reason,'requested_at':at}

def validate_stop(value,grant):
    if (type(value) is not dict or set(value)!={'schema','session_id','command_id','reason','requested_at'}
            or value!=stop_command(grant,value.get('reason'),value.get('requested_at'))):
        raise ValueError('EXACT_INITIATING_STOP_COMMAND_REQUIRED')
    return strict(body(value))

def classify_exit(lane,proposal,grant,stop,writer):
    reason='STRATEGY_EXIT'; command=proposal['command']
    if stop is not None:
        stop=validate_stop(stop,grant);reason=stop['reason']
    elif command.get('evidence',{}).get('exit_reason')=='SHUTDOWN_FLATTEN' or str(proposal.get('strategy_ref','')).startswith('SHUTDOWN_FLATTEN:'):
        reason='UNKNOWN'
    elif lane=='HYPERLIQUID' and hasattr(writer,'orders'):
        from app.trading_core.models import Side
        from app.trading_core.perp_setup_state import classify_setup_state
        cut=writer._cut();position=cut['state']['positions'][command['position_id']]
        order=writer.orders.snapshot()['state']['orders'].get(position['origin_ref'])
        if order is None or order['state']!='ACKNOWLEDGED':raise ValueError('EXIT_ORIGINAL_ORDER_REQUIRED')
        plan=order['order']['plan'];book=command['evidence']
        state=classify_setup_state(side=Side(position['side']),mark=float(book['bid'] if position['side']=='LONG' else book['ask']),entered=True,
            **{k:float(plan[k]) for k in ('l1','l2','l3','stop','tp1','tp2')}).state.value
        reason={'INVALIDATED':'STOP_LOSS','TP1_HIT':'TAKE_PROFIT','TP2_HIT':'TAKE_PROFIT'}.get(state,'STRATEGY_EXIT')
    return {'schema':'ATLAS_EXIT_REASON_V1','reason':reason,'session_id':grant['session_id'],
        'operation_id':proposal['operation_id'],'stop_command':stop}

def reconcile_history(control,cuts,writers):
    """Re-derive all per-fill deltas; incomplete evidence never becomes a closed trade."""
    rows=[];accounts={};unresolved=[]
    for lane,cut in cuts.items():
        m=cut['manifest'];state=initial_state(m);operations=[];entry_costs={};unallocated={};entries={}
        for ident,row in control['state']['operations'].items():
            request=row['request'];p=request['proposal']
            if request['lane']==lane and p['kind'] not in ('RESTING_ORDER','CANCEL_RESTING_ORDER'):
                if row['state']!='ACKNOWLEDGED' or row['receipt'] is None:raise ValueError('HISTORY_GLOBAL_ACK_UNKNOWN')
                if cut['acknowledged_operations'].get(ident)!=digest(p['command']):raise ValueError('HISTORY_NATIVE_COMMAND_MISSING')
                operations.append((row['receipt']['source_revision'],ident,row))
        if len(operations)!=len(cut['acknowledged_operations']):raise ValueError('HISTORY_SOURCE_COMPLETENESS_UNPROVEN')
        for revision,ident,row in sorted(operations):
            request=row['request'];p=request['proposal'];command=p['command'];before=state
            state,receipt=apply_event(m,state,command)
            # The native cut already verifies every immutable command/ACK/projection.
            # Recompute exact receipts once, rather than reopen/replay the whole
            # native store for each row (quadratic disk reads near capacity).
            receipt['projection_required']=True
            if (revision!=state['revision'] or body(receipt)!=body(row['receipt'])):
                raise ValueError('HISTORY_RECEIPT_OR_REVISION_CONFLICT')
            if p['kind']=='ENTRY':
                entries[receipt['position_id']]={'entry_operation_id':ident,'entry_at':command['timestamp'],
                    'entry_source_revision':revision}
            if p['kind']=='ENTRY' and lane=='HYPERLIQUID':
                key=receipt['position_id']
                entry_costs[key]=number(state['costs'])-number(before['costs'])
                unallocated[key]=entry_costs[key]
            if p['kind']=='EXIT':
                attribution=request.get('exit_classification')
                if attribution is None:
                    attribution={'schema':'ATLAS_EXIT_REASON_V1','reason':'UNKNOWN','session_id':request['grant']['session_id'],
                        'operation_id':ident,'stop_command':None}
                if (set(attribution)!={'schema','reason','session_id','operation_id','stop_command'}
                        or attribution['schema']!='ATLAS_EXIT_REASON_V1' or attribution['reason'] not in REASONS
                        or attribution['operation_id']!=ident or attribution['session_id']!=request['grant']['session_id']):
                    raise ValueError('HISTORY_EXIT_CLASSIFICATION_CONFLICT')
                if attribution['reason'] in ('USER_SHUTDOWN','RISK_SHUTDOWN'):
                    stop=validate_stop(attribution['stop_command'],request['grant'])
                    if stop['reason']!=attribution['reason'] or request.get('mode')!='SHUTDOWN_REDUCING_EXIT_V1':
                        raise ValueError('HISTORY_STOP_CLASSIFICATION_UNBOUND')
                key=receipt['position_id'];position=state['positions'][key]
                gross=number(state['gross'])-number(before['gross'])
                costs=number(state['costs'])-number(before['costs']);funding=number('0')
                if lane=='HYPERLIQUID':
                    prior=before['positions'][key];quantity=number(command['quantity'])
                    with localcontext() as context:
                        context.prec=28;context.traps[Inexact]=True
                        allocated=unallocated[key] if quantity==number(prior['remaining']) else entry_costs[key]*quantity/number(prior['quantity'])
                        unallocated[key]-=allocated;costs+=allocated
                        funding=number(prior['remaining_funding'])-number(position['remaining_funding'])
                rows.append({'lane':lane,'currency':m['currency'],'epoch':m['epoch'],'operation_id':ident,
                    'position_id':key,**entries[key],'session_id':attribution['session_id'],'reason':attribution['reason'],
                    'stop_command_id':None if attribution['stop_command'] is None else attribution['stop_command']['command_id'],
                    'at':command['timestamp'],'quantity':command['quantity'],'remaining':position['remaining'],
                    'gross':str(gross),'costs':str(costs),'net':str(gross-costs+funding),
                    'funding':str(funding),'ledger_net_delta':str(number(state['net'])-number(before['net'])),
                    'funding_delta':str(number(state.get('funding','0'))-number(before.get('funding','0'))),
                    'entry':position['entry'],'symbol':position['symbol'],'side':position['side'],
                    'entry_quantity':position['quantity'],'execution_evidence_digest':digest(command['evidence']),
                    'receipt_digest':digest(row['receipt']),'source_revision':revision,'execution':'SIMULATED'})
        if body(state)!=body(cut['state']):raise ValueError('HISTORY_REPLAY_SOURCE_MISMATCH')
        if control['state']['entry_closed'] and control['state']['finalized'] is None:
            for key,position in state['positions'].items():
                if number(position['remaining'])>0:
                    unresolved.append({'lane':lane,'position_id':key,'quantity':position['remaining'],
                        'currency':m['currency'],'state':'POSITION_OPEN_NOT_AN_EXIT',
                        'attempt_reason':control['state'].get('stop_context',{}).get('reason','UNKNOWN')})
        accounts[lane]={'currency':m['currency'],'cash':state['cash'],'net':state['net'],
            'source_revision':state['revision'],'source_head':cut['head']}
    groups={'ALL':REASONS,'STRATEGY':('STRATEGY_EXIT','TAKE_PROFIT'),'USER':('USER_SHUTDOWN',),
        'RISK':('STOP_LOSS','RISK_SHUTDOWN'),'UNRESOLVED':('UNKNOWN',)}
    analysis={}
    try:
        with localcontext() as context:
            context.prec=28;context.traps[Inexact]=True
            for lane,account in accounts.items():
                analysis[lane]={}
                for name,reasons in groups.items():
                    selected=[r for r in rows if r['lane']==lane and r['reason'] in reasons]
                    analysis[lane][name]={'currency':account['currency'],'exit_fills':len(selected),
                        **{key:str(sum((number(r[key]) for r in selected),number('0'))) for key in ('gross','costs','net')},
                        'funding':str(sum((number(r['funding']) for r in selected),number('0'))),
                        'cost_allocation':'COMMITTED_ENTRY_COSTS_AND_REMAINING_FUNDING_PRO_RATA_V1'}
    except DecimalException as error:
        raise ValueError('HISTORY_ANALYTICS_PRECISION_UNSUPPORTED') from error
    return {'schema':'ATLAS_EXIT_HISTORY_V1','status':'ACKNOWLEDGED','rows':rows,'accounts':accounts,'analysis':analysis,'unresolved':unresolved,
        'global_head':control['head'],'global_revision':control['state']['revision'],
        'total_cash':None,'total_net':None,'startup_authorized':False}
