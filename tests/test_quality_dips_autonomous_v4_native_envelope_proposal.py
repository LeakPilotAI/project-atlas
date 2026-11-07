"""Native envelope/receipt research contract only, not V4 operational acceptance."""
import copy
import pytest
from app.services.paper_financial_replay import digest
from app.services.quality_dips_autonomous_v4_fill_proposal import replay_proposed_v4_fills
from app.services.quality_dips_autonomous_v4_native_envelope_proposal import verify_proposed_v4_native_envelopes
from test_quality_dips_autonomous_v4_fill_audit_proposal import evidence


def sample():
    events, assertion = evidence()
    enrollment = {'account_id': 'PAPER-1', 'epoch': 'EPOCH-1', 'enrollment_digest': 'a' * 64}
    envelopes = []
    for i, event in enumerate(events, 1):
        replay = replay_proposed_v4_fills(events[:i])
        record_digest = digest(event)
        envelopes.append({'schema': 'QD_AUTO_NATIVE_EVENT_ENVELOPE_PROPOSAL_V1',
            **enrollment, 'revision': i, 'record': copy.deepcopy(event),
            'record_digest': record_digest,
            'receipt': {'schema': 'QD_AUTO_NATIVE_RECEIPT_PROPOSAL_V1',
                'revision': i, 'record_digest': record_digest,
                'head': replay['head'], 'state_digest': digest(replay['state'])}})
    return enrollment, envelopes, assertion


def test_proposed_native_event_envelopes_and_receipts_reconcile():
    result = verify_proposed_v4_native_envelopes(*sample())
    assert result['revision'] == 3
    assert result['operational_authority_accepted'] is False
    assert result['paper_execution_authorized'] is False
    assert result['live_order_authorized'] is False


@pytest.mark.parametrize('damage', ['foreign_account', 'foreign_epoch', 'foreign_enrollment',
    'bool_revision', 'missing_event', 'duplicate_event', 'record_digest', 'receipt_head',
    'receipt_state', 'receipt_revision', 'receipt_digest', 'extra_receipt',
    'extra_envelope', 'record_mutation', 'assertion_head'])
def test_proposed_native_event_envelope_refuses_corruption(damage):
    enrollment, envelopes, assertion = sample()
    if damage == 'foreign_account': envelopes[1]['account_id'] = 'FOREIGN'
    if damage == 'foreign_epoch': envelopes[1]['epoch'] = 'FOREIGN'
    if damage == 'foreign_enrollment': envelopes[1]['enrollment_digest'] = 'f' * 64
    if damage == 'bool_revision': envelopes[1]['revision'] = True
    if damage == 'missing_event': envelopes.pop(1)
    if damage == 'duplicate_event': envelopes.append(copy.deepcopy(envelopes[2]))
    if damage == 'record_digest': envelopes[1]['record_digest'] = 'f' * 64
    if damage == 'receipt_head': envelopes[1]['receipt']['head'] = 'f' * 64
    if damage == 'receipt_state': envelopes[1]['receipt']['state_digest'] = 'f' * 64
    if damage == 'receipt_revision': envelopes[1]['receipt']['revision'] = 1
    if damage == 'receipt_digest': envelopes[1]['receipt']['record_digest'] = 'f' * 64
    if damage == 'extra_receipt': envelopes[1]['receipt']['approved'] = True
    if damage == 'extra_envelope': envelopes[1]['approved'] = True
    if damage == 'record_mutation': envelopes[1]['record']['price'] = '111'
    if damage == 'assertion_head': assertion['head'] = 'f' * 64
    with pytest.raises(ValueError):
        verify_proposed_v4_native_envelopes(enrollment, envelopes, assertion)


def test_proposed_native_envelope_verification_preserves_inputs():
    evidence = sample()
    original = copy.deepcopy(evidence)
    verify_proposed_v4_native_envelopes(*evidence)
    assert evidence == original
@pytest.mark.parametrize('field', ['cash', 'gross', 'costs', 'net', 'quantity', 'entry'])
def test_proposed_native_receipts_refuse_independent_arithmetic_disagreement(monkeypatch, field):
    from app.services import quality_dips_autonomous_v4_native_envelope_proposal as target
    original = target.audit_v4_fill_arithmetic_independently
    def corrupted(events):
        value = original(events)
        if field in ('quantity', 'entry'):
            if value['positions_units']:
                symbol = next(iter(value['positions_units']))
                value['positions_units'][symbol]['quantity_1e8' if field == 'quantity' else 'entry_1e4'] += 1
            else:
                value['cash_units'] += 1
        else:
            value[{'cash': 'cash_units', 'gross': 'gross_units',
                   'costs': 'cost_units', 'net': 'net_units'}[field]] += 1
        return value
    monkeypatch.setattr(target, 'audit_v4_fill_arithmetic_independently', corrupted)
    with pytest.raises(ValueError, match='INDEPENDENT_FINANCIAL_MISMATCH'):
        verify_proposed_v4_native_envelopes(*sample())


def test_proposed_native_envelope_prefixes_include_independent_arithmetic():
    enrollment, envelopes, assertion = sample()
    assert verify_proposed_v4_native_envelopes(enrollment, envelopes, assertion)['revision'] == 3