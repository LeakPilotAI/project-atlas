"""Proposed V4 fill transition arithmetic; never an operational replay grant."""
import copy
import pytest
from app.services.quality_dips_autonomous_v4_fill_proposal import replay_proposed_v4_fills


def fills():
    return [
        {'schema': 'QD_AUTO_V4_FILL_PROPOSAL_V1', 'revision': 1,
         'operation_id': 'enter', 'kind': 'ENTRY', 'symbol': 'MSFT',
         'quantity': '2', 'price': '100', 'fee': '1'},
        {'schema': 'QD_AUTO_V4_FILL_PROPOSAL_V1', 'revision': 2,
         'operation_id': 'partial', 'kind': 'EXIT', 'symbol': 'MSFT',
         'quantity': '1', 'price': '110', 'fee': '1'},
        {'schema': 'QD_AUTO_V4_FILL_PROPOSAL_V1', 'revision': 3,
         'operation_id': 'close', 'kind': 'EXIT', 'symbol': 'MSFT',
         'quantity': '1', 'price': '120', 'fee': '1'},
    ]


def test_proposed_entry_partial_exit_and_full_exit_reconcile():
    result = replay_proposed_v4_fills(fills())
    assert result['state'] == {'cash': '1027', 'positions': {}, 'gross': '30',
                               'costs': '3', 'net': '27', 'revision': 3}
    assert result['operational_authority_accepted'] is False
    assert result['paper_execution_authorized'] is False
    assert result['live_order_authorized'] is False


@pytest.mark.parametrize('damage', ['missing', 'duplicate', 'revision', 'negative_fee',
    'over_exit', 'foreign_symbol', 'insufficient_cash', 'precision', 'bool_revision',
    'invalid_kind', 'duplicate_entry'])
def test_proposed_v4_fill_replay_refuses_invalid_financial_history(damage):
    rows = fills()
    if damage == 'missing': rows.pop(1)
    if damage == 'duplicate': rows[1]['operation_id'] = 'enter'
    if damage == 'revision': rows[1]['revision'] = 3
    if damage == 'negative_fee': rows[0]['fee'] = '-1'
    if damage == 'over_exit': rows[1]['quantity'] = '3'
    if damage == 'foreign_symbol': rows[1]['symbol'] = 'AAPL'
    if damage == 'insufficient_cash': rows[0]['price'] = '10000'
    if damage == 'precision': rows[0]['price'] = '100.001'
    if damage == 'bool_revision': rows[0]['revision'] = True
    if damage == 'invalid_kind': rows[0]['kind'] = 'SHORT'
    if damage == 'duplicate_entry': rows[1]['kind'] = 'ENTRY'
    with pytest.raises(ValueError):
        replay_proposed_v4_fills(rows)


def test_proposed_replay_is_deterministic_and_does_not_mutate_inputs():
    rows = fills()
    before = copy.deepcopy(rows)
    assert replay_proposed_v4_fills(rows) == replay_proposed_v4_fills(rows)
    assert rows == before