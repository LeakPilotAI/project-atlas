"""Resting PAPER order control, not financial accounting or execution evidence."""
import copy

from app.services.paper_financial_replay import body, digest, number, text


def validate_order(order, manifest):
    fields = {'schema', 'epoch', 'order_id', 'symbol', 'side', 'quantity', 'limit_price',
              'stop_price', 'risk_price', 'leverage', 'created_at', 'expires_at',
              'source_id', 'source_revision', 'source_digest', 'session_id', 'plan'}
    if (type(order) is not dict or set(order) != fields or order['schema'] != 'PERP_RESTING_ORDER_V1'
            or order['epoch'] != manifest['epoch'] or order['symbol'] not in manifest['perp_policy']['symbols']
            or order['side'] not in ('LONG', 'SHORT') or type(order['plan']) is not dict
            or any(type(order[k]) is not int for k in ('created_at', 'expires_at', 'source_revision'))
            or order['source_revision'] < 1 or not manifest['opened_at'] <= order['created_at'] < order['expires_at']
            or order['expires_at'] - order['created_at'] > 21600 or len(body(order).encode()) > 16384):
        raise ValueError('EXACT_BOUNDED_RESTING_ORDER_REQUIRED')
    for key in ('order_id', 'source_id', 'source_digest', 'session_id'): text(order[key])
    qty, limit, stop, risk, leverage = (number(order[k]) for k in ('quantity', 'limit_price', 'stop_price', 'risk_price', 'leverage'))
    policy = manifest['perp_policy']
    step = number(order['plan'].get('quantity_step'))
    if (min(qty, limit, stop, risk, leverage) <= 0 or leverage > number(policy['max_leverage'])
            or step <= 0 or qty % step != 0 or order['plan'].get('execution_policy') != 'STATIC_SETUP_TP1_V1'
            or qty * limit > number(policy['max_notional']) or qty * risk > number(policy['risk_limit'])
            or risk != abs(limit - stop) or (stop >= limit if order['side'] == 'LONG' else stop <= limit)):
        raise ValueError('RESTING_ORDER_RISK_OR_LIMIT_REFUSED')
    return order


def validate_fill(order, command):
    if (command.get('schema') != 'PAPER_PERP_MAKER_FILL_V1' or command.get('kind') != 'ENTRY'
            or command.get('epoch') != order['epoch'] or command.get('origin_ref') != order['order_id']
            or command.get('symbol') != order['symbol'] or command.get('side') != order['side']
            or number(command.get('leverage')) != number(order['leverage'])
            or number(command.get('risk_price')) != number(order['risk_price'])
            or not order['created_at'] <= command.get('timestamp', -1) < order['expires_at']):
        raise ValueError('RESTING_ORDER_FILL_IDENTITY_REFUSED')
    proof = command['evidence']['maker_execution']
    if (proof['order_id'] != order['order_id'] or number(proof['limit_price']) != number(order['limit_price'])
            or number(command['quantity']) % number(order['plan']['quantity_step']) != 0
            or proof['rested_at'] != order['created_at'] or number(proof['requested_quantity']) != number(order['quantity'])
            or number(command['quantity']) != number(proof['filled_quantity'])
            or number(proof['filled_quantity']) + number(proof['cancelled_quantity']) != number(order['quantity'])):
        raise ValueError('RESTING_ORDER_QUEUE_BINDING_REFUSED')


def transition(scope, manifest, state, event):
    """Pure control replay. Native custody and financial ACK authenticity are external."""
    if (type(event) is not dict or set(event) != {'kind', 'order_id', 'at', 'payload'}
            or type(event['at']) is not int or event['at'] < state['last_clock']):
        raise ValueError('RESTING_CONTROL_EVENT_OR_CLOCK_REFUSED')
    text(event['order_id'])
    after = copy.deepcopy(state)
    prior = state['orders'].get(event['order_id'])
    payload = event['payload']
    if event['kind'] == 'ARM':
        order = validate_order(payload, manifest)
        active = [o for o in state['orders'].values() if o['state'] in ('RESERVED', 'FILL_PENDING')]
        if (prior is not None or order['order_id'] != event['order_id'] or order['created_at'] != event['at']
                or len(active) >= manifest['perp_policy']['max_positions']
                or any(o['order']['symbol'] == order['symbol'] for o in active)):
            raise ValueError('RESTING_ORDER_DUPLICATE_OR_CONCURRENCY_REFUSED')
        after['orders'][event['order_id']] = {'order': copy.deepcopy(order), 'state': 'RESERVED',
                                             'command_digest': None, 'operation_id': None, 'receipt': None}
    elif event['kind'] == 'FILL_PENDING':
        if prior is None or prior['state'] != 'RESERVED':
            raise ValueError('RESTING_ORDER_PENDING_OR_UNKNOWN')
        validate_fill(prior['order'], payload)
        if payload['timestamp'] != event['at']:
            raise ValueError('RESTING_FILL_CLOCK_REFUSED')
        after['orders'][event['order_id']].update(state='FILL_PENDING', command_digest=digest(payload), operation_id=payload['operation_id'])
    elif event['kind'] == 'ACK':
        if (prior is None or prior['state'] != 'FILL_PENDING' or type(payload) is not dict
                or payload.get('operation_id') != prior['operation_id'] or payload.get('payload_digest') != prior['command_digest']):
            raise ValueError('RESTING_FINANCIAL_ACK_REFUSED')
        after['orders'][event['order_id']].update(state='ACKNOWLEDGED', receipt=copy.deepcopy(payload))
    elif event['kind'] == 'CANCEL':
        if prior is None or prior['state'] != 'RESERVED' or payload != {'reason': 'NO_FINANCIAL_EFFECT'}:
            raise ValueError('RESTING_CANCELLATION_UNKNOWN_REFUSED')
        after['orders'][event['order_id']]['state'] = 'CANCELLED'
    else:
        raise ValueError('RESTING_CONTROL_KIND_REFUSED')
    after['revision'] += 1
    after['last_clock'] = event['at']
    return after
