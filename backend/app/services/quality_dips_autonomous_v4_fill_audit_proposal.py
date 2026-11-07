"""Independent proposed V4 financial publication audit; no operational authority.

This compares separately supplied financial assertions with deterministic replay.
It does not authenticate event origin, native custody, quote or fill evidence.
"""
from decimal import Decimal
from app.services.paper_financial_replay import body, digest, strict
from app.services.quality_dips_autonomous_v4_fill_proposal import replay_proposed_v4_fills
from app.services.quality_dips_autonomous_v4_integer_oracle_proposal import audit_v4_fill_arithmetic_independently, UNIT


def audit_proposed_v4_fills(events, assertion, *, opening_cash='1000'):
    if type(assertion) is not dict or set(assertion) != {
            'schema', 'revision', 'head', 'event_digest', 'state_digest', 'state'}:
        raise ValueError('V4_PROPOSAL_AUDIT_ASSERTION_SCHEMA')
    if assertion['schema'] != 'QD_AUTO_V4_FINANCIAL_AUDIT_ASSERTION_PROPOSAL_V1':
        raise ValueError('V4_PROPOSAL_AUDIT_ASSERTION_SCHEMA')
    result = replay_proposed_v4_fills(events, opening_cash=opening_cash)
    independent = audit_v4_fill_arithmetic_independently(events, opening_cash=opening_cash)
    computed = result['state']
    if (any(int(Decimal(computed[key]) * UNIT) != independent[other]
            for key, other in [('cash', 'cash_units'), ('gross', 'gross_units'),
                               ('costs', 'cost_units'), ('net', 'net_units')])
            or computed['revision'] != independent['revision']
            or set(computed['positions']) != set(independent['positions_units'])
            or any(int(Decimal(position['quantity']) * 10**8) !=
                   independent['positions_units'][symbol]['quantity_1e8']
                   or int(Decimal(position['entry']) * 10**4) !=
                   independent['positions_units'][symbol]['entry_1e4']
                   for symbol, position in computed['positions'].items())):
        raise ValueError('V4_PROPOSAL_AUDIT_INDEPENDENT_ARITHMETIC_MISMATCH')
    state = strict(body(assertion['state']))
    if (type(assertion['revision']) is not int
            or assertion['revision'] != result['state']['revision']
            or assertion['head'] != result['head']
            or assertion['event_digest'] != result['event_digest']
            or assertion['state_digest'] != digest(result['state'])
            or body(state) != body(result['state'])):
        raise ValueError('V4_PROPOSAL_AUDIT_FINANCIAL_MISMATCH')
    return {'schema': 'QD_AUTO_V4_FINANCIAL_AUDIT_RESULT_PROPOSAL_V1',
            'revision': result['state']['revision'], 'head': result['head'],
            'state_digest': digest(result['state']),
            'operational_authority_accepted': False,
            'paper_execution_authorized': False, 'live_order_authorized': False}