"""Independent integer-ledger arithmetic oracle for proposed V4 fill histories.

Does not call the V4 replay implementation. Financial calculations use integer
units of 1e-12 USD, supporting up to 8 share and 4 price decimal places.
This is a source-only cross-check, not a trusted event or native V4 authority.
"""
from decimal import Decimal, InvalidOperation

UNIT = 10 ** 12


def _fixed(value, places):
    if type(value) is not str:
        raise ValueError('V4_ORACLE_DECIMAL_STRING_REQUIRED')
    try:
        decimal = Decimal(value)
        if not decimal.is_finite() or decimal.as_tuple().exponent < -places:
            raise ValueError('V4_ORACLE_PRECISION')
        scaled = decimal * (10 ** places)
        if scaled != scaled.to_integral_value():
            raise ValueError('V4_ORACLE_PRECISION')
        return int(scaled)
    except (InvalidOperation, OverflowError) as exc:
        raise ValueError('V4_ORACLE_DECIMAL_INVALID') from exc


def audit_v4_fill_arithmetic_independently(events, *, opening_cash='1000'):
    if type(events) is not list or len(events) > 128 or opening_cash != '1000':
        raise ValueError('V4_ORACLE_BOUNDARY')
    cash, gross, fees = 1000 * UNIT, 0, 0
    positions, seen = {}, set()
    for revision, event in enumerate(events, 1):
        if (type(event) is not dict or set(event) != {'schema', 'revision', 'operation_id',
                'kind', 'symbol', 'quantity', 'price', 'fee', 'parent'}
                or event['schema'] != 'QD_AUTO_V4_FILL_PROPOSAL_V1'
                or type(event['revision']) is not int or event['revision'] != revision
                or event['kind'] not in ('ENTRY', 'EXIT')
                or type(event['operation_id']) is not str
                or not 1 <= len(event['operation_id']) <= 128
                or event['operation_id'] in seen
                or type(event['symbol']) is not str
                or not 1 <= len(event['symbol']) <= 15
                or not event['symbol'].replace('.', '').replace('-', '').isalnum()
                or event['symbol'] != event['symbol'].upper()):
            raise ValueError('V4_ORACLE_EVENT_INVALID')
        seen.add(event['operation_id'])
        quantity = _fixed(event['quantity'], 8)
        price = _fixed(event['price'], 4)
        fee = _fixed(event['fee'], 4) * 10 ** 8
        if quantity <= 0 or price <= 0 or fee < 0:
            raise ValueError('V4_ORACLE_RANGE')
        symbol = event['symbol']
        notional = quantity * price
        if event['kind'] == 'ENTRY':
            if symbol in positions or notional + fee > cash:
                raise ValueError('V4_ORACLE_ENTRY_REFUSED')
            cash -= notional + fee
            positions[symbol] = [quantity, price]
        else:
            if symbol not in positions or quantity > positions[symbol][0]:
                raise ValueError('V4_ORACLE_EXIT_REFUSED')
            cash += notional - fee
            gross += quantity * (price - positions[symbol][1])
            positions[symbol][0] -= quantity
            if positions[symbol][0] == 0:
                del positions[symbol]
        fees += fee
    return {'schema': 'QD_AUTO_V4_INDEPENDENT_INTEGER_ORACLE_PROPOSAL_V1',
            'revision': len(events), 'cash_units': cash, 'gross_units': gross,
            'cost_units': fees, 'net_units': gross - fees,
            'positions_units': {symbol: {'quantity_1e8': value[0], 'entry_1e4': value[1]}
                                for symbol, value in sorted(positions.items())},
            'operational_authority_accepted': False,
            'paper_execution_authorized': False, 'live_order_authorized': False}