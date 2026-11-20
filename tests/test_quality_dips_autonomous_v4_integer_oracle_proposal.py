"""Cross-check independent integer financial oracle against decimal replay."""
from decimal import Decimal
import copy
import pytest
from app.services.paper_financial_replay import digest
from app.services.quality_dips_autonomous_v4_integer_oracle_proposal import (
    audit_v4_fill_arithmetic_independently as oracle, UNIT)
from app.services.quality_dips_autonomous_v4_fill_proposal import replay_proposed_v4_fills
from test_quality_dips_autonomous_v4_fill_proposal import fills


def compare(rows):
    before = copy.deepcopy(rows)
    actual = replay_proposed_v4_fills(rows)['state']
    independently = oracle(rows)
    for name, field in [('cash', 'cash_units'), ('gross', 'gross_units'),
                        ('costs', 'cost_units'), ('net', 'net_units')]:
        assert int(Decimal(actual[name]) * UNIT) == independently[field]
    assert actual['revision'] == independently['revision']
    assert set(actual['positions']) == set(independently['positions_units'])
    for symbol, position in actual['positions'].items():
        independent_position = independently['positions_units'][symbol]
        assert int(Decimal(position['quantity']) * 10**8) == independent_position['quantity_1e8']
        assert int(Decimal(position['entry']) * 10**4) == independent_position['entry_1e4']
    assert independently['paper_execution_authorized'] is False
    assert rows == before


def lineage(rows):
    for i, event in enumerate(rows):
        event['parent'] = (digest(['QD_AUTO_V4_FILL_PROPOSAL_V1', '1000']) if i == 0
                           else replay_proposed_v4_fills(rows[:i])['head'])
    return rows


def test_integer_oracle_matches_three_step_partial_exit():
    compare(fills())


@pytest.mark.parametrize('qty,price,fee', [('0.12345678', '101.1234', '0.0001'),
    ('0.00000001', '0.0001', '0'), ('1.25', '250.5', '0.5'),
    ('3', '99', '0'), ('0.33333333', '0.1234', '0.0001')])
def test_integer_oracle_matches_fractional_roundtrip(qty, price, fee):
    rows = fills()
    rows[0].update(quantity=qty, price=price, fee=fee)
    rows[1].update(quantity=qty, price=price, fee=fee)
    rows = lineage(rows[:2])
    compare(rows)


def test_integer_oracle_matches_multi_symbol_open_positions():
    rows = fills()[:1]
    rows.append({**rows[0], 'revision': 2, 'operation_id': 'second',
                 'symbol': 'AAPL', 'quantity': '0.00000001', 'price': '0.0001'})
    compare(lineage(rows))


@pytest.mark.parametrize('damage', ['over_exit', 'insufficient_cash', 'negative_fee',
    'precision', 'duplicate_id', 'duplicate_entry', 'bad_revision'])
def test_integer_oracle_rejects_invalid_arithmetic(damage):
    rows = fills()
    if damage == 'over_exit': rows[1]['quantity'] = '3'
    if damage == 'insufficient_cash': rows[0]['price'] = '10000'
    if damage == 'negative_fee': rows[0]['fee'] = '-1'
    if damage == 'precision': rows[0]['quantity'] = '0.123456789'
    if damage == 'duplicate_id': rows[1]['operation_id'] = 'enter'
    if damage == 'duplicate_entry': rows[1]['kind'] = 'ENTRY'
    if damage == 'bad_revision': rows[1]['revision'] = True
    with pytest.raises(ValueError): oracle(rows)