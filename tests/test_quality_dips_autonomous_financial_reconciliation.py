"""Retained FS1 event evidence only; no native custody or operational grant."""
import copy
import pytest
from app.services.paper_financial_replay import digest, event_stream_record, replay_verified_events
from app.services.quality_dips_autonomous_financial_reconciliation import reconcile_authenticated_financial_cut
from test_fs1_financial_replay import GOLDEN


def case():
    value = copy.deepcopy(GOLDEN[0])
    rows = [event_stream_record(*r) for r in value['sql_rows']]
    state, _, _ = replay_verified_events(value['manifest'], rows)
    return value['manifest'], rows, state, {
        'expected_epoch': value['manifest']['epoch'],
        'expected_revision': len(rows),
        'expected_head': value['head'],
        'expected_state_digest': digest(state),
    }


def test_reconciles_retained_quality_dips_entry_exit_financial_cut():
    m, rows, state, expected = case()
    result = reconcile_authenticated_financial_cut(m, rows, state, **expected)
    assert result['revision'] == 3
    assert result['head'] == expected['expected_head']
    assert result['startup_authorized'] is result['production_authorized'] is False


@pytest.mark.parametrize('damage', ['foreign_epoch', 'foreign_strategy', 'missing_event',
    'duplicate_event', 'wrong_head', 'wrong_state', 'wrong_revision', 'bool_revision',
    'tampered_cash', 'tampered_event', 'tampered_receipt', 'missing_snapshot'])
def test_reconciliation_refuses_inconsistent_evidence(damage):
    m, rows, state, expected = case()
    if damage == 'foreign_epoch': expected['expected_epoch'] = 'OTHER'
    if damage == 'foreign_strategy': m['strategy'] = 'HYPERLIQUID_MANUAL'
    if damage == 'missing_event': rows.pop(1)
    if damage == 'duplicate_event': rows.append(copy.deepcopy(rows[0]))
    if damage == 'wrong_head': expected['expected_head'] = 'f' * 64
    if damage == 'wrong_state': expected['expected_state_digest'] = 'f' * 64
    if damage == 'wrong_revision': expected['expected_revision'] = 2
    if damage == 'bool_revision': expected['expected_revision'] = True
    if damage == 'tampered_cash': state['cash'] = '999'
    if damage == 'tampered_event': rows[0]['digest'] = 'f' * 64
    if damage == 'tampered_receipt': rows[0]['receipt'] = '{}'
    if damage == 'missing_snapshot': state.pop('positions')
    with pytest.raises((ValueError, KeyError)):
        reconcile_authenticated_financial_cut(m, rows, state, **expected)
