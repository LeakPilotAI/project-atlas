"""Separate V4 proposed publication audit; no accepted event or custody authority."""
import copy
import pytest
from app.services.paper_financial_replay import digest
from app.services.quality_dips_autonomous_v4_fill_proposal import replay_proposed_v4_fills
from app.services.quality_dips_autonomous_v4_fill_audit_proposal import audit_proposed_v4_fills
from test_quality_dips_autonomous_v4_fill_proposal import fills


def evidence():
    events = fills()
    replay = replay_proposed_v4_fills(events)
    assertion = {'schema': 'QD_AUTO_V4_FINANCIAL_AUDIT_ASSERTION_PROPOSAL_V1',
                 'revision': replay['state']['revision'], 'head': replay['head'],
                 'event_digest': replay['event_digest'],
                 'state_digest': digest(replay['state']),
                 'state': copy.deepcopy(replay['state'])}
    return events, assertion


def test_independent_proposed_financial_assertion_reconciles():
    events, assertion = evidence()
    result = audit_proposed_v4_fills(events, assertion)
    assert result['revision'] == 3
    assert result['state_digest'] == digest(assertion['state'])
    assert result['operational_authority_accepted'] is False
    assert result['paper_execution_authorized'] is False
    assert result['live_order_authorized'] is False


@pytest.mark.parametrize('damage', ['cash', 'position', 'gross', 'costs', 'net',
    'revision', 'bool_revision', 'head', 'event_digest', 'state_digest',
    'extra_state', 'missing_state', 'schema', 'extra_field', 'event'])
def test_independent_proposed_financial_assertion_refuses_mismatch(damage):
    events, assertion = evidence()
    if damage in ('cash', 'gross', 'costs', 'net'):
        assertion['state'][damage] = '999'
    if damage == 'position': assertion['state']['positions']['AAPL'] = {'quantity': '1'}
    if damage == 'revision': assertion['revision'] = 2
    if damage == 'bool_revision': assertion['revision'] = True
    if damage == 'head': assertion['head'] = 'f' * 64
    if damage == 'event_digest': assertion['event_digest'] = 'f' * 64
    if damage == 'state_digest': assertion['state_digest'] = 'f' * 64
    if damage == 'extra_state': assertion['state']['invented'] = True
    if damage == 'missing_state': assertion.pop('state')
    if damage == 'schema': assertion['schema'] = 'WRONG'
    if damage == 'extra_field': assertion['approved'] = True
    if damage == 'event': events[2]['price'] = '121'
    with pytest.raises(ValueError):
        audit_proposed_v4_fills(events, assertion)


def test_proposed_financial_audit_does_not_mutate_input():
    events, assertion = evidence()
    original = copy.deepcopy((events, assertion))
    audit_proposed_v4_fills(events, assertion)
    assert (events, assertion) == original