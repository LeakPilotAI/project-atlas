"""Proposed V4 native event/receipt envelope validation; not an accepted authority.

Pure in-memory contract. It neither writes native files nor grants operational
publication, custody, quote rights, PAPER startup or live-order permissions.
"""
from decimal import Decimal
from app.services.paper_financial_replay import body, digest, strict
from app.services.quality_dips_autonomous_v4_fill_proposal import replay_proposed_v4_fills
from app.services.quality_dips_autonomous_v4_fill_audit_proposal import audit_proposed_v4_fills
from app.services.quality_dips_autonomous_v4_integer_oracle_proposal import audit_v4_fill_arithmetic_independently, UNIT


def verify_proposed_v4_native_envelopes(enrollment, envelopes, assertion):
    if (type(enrollment) is not dict or set(enrollment) != {'account_id', 'epoch', 'enrollment_digest'}
            or any(type(enrollment[k]) is not str or not enrollment[k] for k in enrollment)
            or type(envelopes) is not list or len(envelopes) > 128):
        raise ValueError('V4_ENVELOPE_PROPOSAL_BOUNDARY')
    events = []
    receipts = []
    for i, envelope in enumerate(envelopes, 1):
        if (type(envelope) is not dict or set(envelope) != {
                'schema', 'account_id', 'epoch', 'enrollment_digest', 'revision',
                'record', 'record_digest', 'receipt'}
                or envelope['schema'] != 'QD_AUTO_NATIVE_EVENT_ENVELOPE_PROPOSAL_V1'
                or any(envelope[k] != enrollment[k] for k in enrollment)
                or type(envelope['revision']) is not int or envelope['revision'] != i
                or type(envelope['record']) is not dict
                or envelope['record_digest'] != digest(envelope['record'])
                or type(envelope['receipt']) is not dict
                or set(envelope['receipt']) != {'schema', 'revision', 'record_digest', 'head', 'state_digest'}
                or envelope['receipt']['schema'] != 'QD_AUTO_NATIVE_RECEIPT_PROPOSAL_V1'
                or type(envelope['receipt']['revision']) is not int
                or envelope['receipt']['revision'] != i
                or envelope['receipt']['record_digest'] != envelope['record_digest']):
            raise ValueError('V4_ENVELOPE_PROPOSAL_INVALID')
        events.append(strict(body(envelope['record'])))
        current = replay_proposed_v4_fills(events)
        independent = audit_v4_fill_arithmetic_independently(events)
        state = current['state']
        if (independent['revision'] != i
                or any(int(Decimal(state[k]) * UNIT) != independent[other]
                       for k, other in [('cash', 'cash_units'), ('gross', 'gross_units'),
                                        ('costs', 'cost_units'), ('net', 'net_units')])
                or set(state['positions']) != set(independent['positions_units'])
                or any(int(Decimal(position['quantity']) * 10**8) !=
                       independent['positions_units'][symbol]['quantity_1e8']
                       or int(Decimal(position['entry']) * 10**4) !=
                       independent['positions_units'][symbol]['entry_1e4']
                       for symbol, position in state['positions'].items())):
            raise ValueError('V4_ENVELOPE_PROPOSAL_INDEPENDENT_FINANCIAL_MISMATCH')
        if (envelope['receipt']['head'] != current['head']
                or envelope['receipt']['state_digest'] != digest(current['state'])):
            raise ValueError('V4_ENVELOPE_PROPOSAL_RECEIPT_MISMATCH')
        receipts.append(digest(envelope['receipt']))
    audit = audit_proposed_v4_fills(events, assertion)
    return {'schema': 'QD_AUTO_NATIVE_EVENT_AUDIT_PROPOSAL_V1',
            'revision': audit['revision'], 'head': audit['head'],
            'receipts_digest': digest(receipts),
            'operational_authority_accepted': False,
            'paper_execution_authorized': False, 'live_order_authorized': False}