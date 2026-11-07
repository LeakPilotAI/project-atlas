"""Research-only proposed V4 simulated fill arithmetic, not accepted financial authority.

No native file, provider, custody, publisher, runtime or PAPER account IO. The
proposal must be separately reviewed before it can become a V4 event protocol.
"""
from decimal import Context, Decimal, Inexact, ROUND_HALF_EVEN, localcontext
from app.services.paper_financial_replay import body, digest, number


def replay_proposed_v4_fills(events, *, opening_cash='1000'):
    """Replay proposed long-only entry/partial-exit/full-exit records in memory.

    Strict event shape and integer cent prices/quantities avoid silent rounding.
    Returned state is a proposal and cannot be passed as operational evidence.
    """
    if (type(events) is not list or len(events) > 128
            or opening_cash != '1000'):
        raise ValueError('V4_PROPOSAL_BOUNDARY')
    state = {'cash': '1000', 'positions': {}, 'gross': '0', 'costs': '0',
             'net': '0', 'revision': 0}
    seen = set()
    with localcontext(Context(prec=28, rounding=ROUND_HALF_EVEN)) as context:
        context.traps[Inexact] = True
        for i, event in enumerate(events, 1):
            if (type(event) is not dict or set(event) != {
                    'schema', 'revision', 'operation_id', 'kind', 'symbol',
                    'quantity', 'price', 'fee'}
                    or event['schema'] != 'QD_AUTO_V4_FILL_PROPOSAL_V1'
                    or type(event['revision']) is not int or event['revision'] != i
                    or event['kind'] not in ('ENTRY', 'EXIT')
                    or type(event['operation_id']) is not str
                    or not 1 <= len(event['operation_id']) <= 128
                    or event['operation_id'] in seen
                    or type(event['symbol']) is not str
                    or not 1 <= len(event['symbol']) <= 15
                    or not event['symbol'].replace('.', '').replace('-', '').isalnum()
                    or event['symbol'] != event['symbol'].upper()):
                raise ValueError('V4_PROPOSAL_EVENT_SHAPE')
            seen.add(event['operation_id'])
            try:
                qty, price, fee = (number(event[k]) for k in ('quantity', 'price', 'fee'))
                if (qty <= 0 or price <= 0 or fee < 0
                        or any(x.as_tuple().exponent < -2 for x in (qty, price, fee))):
                    raise ValueError('V4_PROPOSAL_FILL_RANGE')
                cash = number(state['cash'])
                gross, costs = number(state['gross']), number(state['costs'])
                symbol = event['symbol']
                if event['kind'] == 'ENTRY':
                    if symbol in state['positions']:
                        raise ValueError('V4_PROPOSAL_DUPLICATE_POSITION')
                    debit = qty * price + fee
                    if debit > cash:
                        raise ValueError('V4_PROPOSAL_INSUFFICIENT_CASH')
                    cash -= debit
                    state['positions'][symbol] = {'quantity': str(qty), 'entry': str(price)}
                else:
                    position = state['positions'].get(symbol)
                    if position is None or qty > number(position['quantity']):
                        raise ValueError('V4_PROPOSAL_UNOWNED_EXIT')
                    cash += qty * price - fee
                    gross += (price - number(position['entry'])) * qty
                    remaining = number(position['quantity']) - qty
                    if remaining == 0:
                        del state['positions'][symbol]
                    else:
                        position['quantity'] = str(remaining)
                costs += fee
                state.update(cash=str(cash), gross=str(gross), costs=str(costs),
                             net=str(gross - costs), revision=i)
            except (Inexact, ArithmeticError) as exc:
                raise ValueError('V4_PROPOSAL_PRECISION') from exc
    return {'schema': 'QD_AUTO_V4_FINANCIAL_REPLAY_PROPOSAL_V1',
            'state': state, 'event_digest': digest(events),
            'operational_authority_accepted': False,
            'paper_execution_authorized': False, 'live_order_authorized': False}