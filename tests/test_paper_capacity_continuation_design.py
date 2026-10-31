"""Executable design examples ONLY; no runtime continuation or financial writer.

This fixture oracle checks proposed structural invariants, not source authenticity,
financial replay, native atomicity, real currentness or authorization acceptance.
"""
import copy
import hashlib
import json
from pathlib import Path

import pytest

FIXTURE = Path(__file__).parent / 'fixtures/paper_capacity_continuation_design_v1.json'


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def example():
    return json.loads(FIXTURE.read_text(encoding='utf8'))


def check_design(predecessor, successor, expected_state, expected_predecessor):
    # expected_* are explicitly synthetic test oracles, never a local trust root.
    if (successor['execution_allowed'] is not False or successor['new_inception_count'] != 0
            or successor['phase'] != 'ACKNOWLEDGED'
            or predecessor['unknown'] is not False or not predecessor['final']
            or successor['index'] != predecessor['index'] + 1
            or successor['previous_digest'] != digest(predecessor)
            or successor['previous_digest'] != expected_predecessor
            or successor['opening_state'] != expected_state
            or predecessor['account_state'] != expected_state
            or set(successor['resources']) != set(predecessor['resources'])
            or set(successor['resources'].values()) & set(predecessor['resources'].values())
            or len(set(successor['resources'].values())) != len(successor['resources'])
            or len(successor['operation_ids']) != len(set(successor['operation_ids']))
            or set(successor['operation_ids']) & set(predecessor['operation_ids'])
            or not successor['custody_receipt']
            or any(row['positions'] or row['pending'] for row in expected_state.values())):
        raise ValueError('CONTINUATION_DESIGN_REFUSED_OR_UNKNOWN')
    return {'design_consistent': True, 'operational_admission': False}


@pytest.mark.parametrize('row', example()['scenarios'], ids=lambda row: row['name'])
def test_source_derived_global_capacity_lower_bounds(row):
    needed = row['sessions'] * row['global_records_per_session_lower_bound'] + row['extra_global_records']
    assert needed == row['expected_global_lower_bound']
    if needed > 128:
        assert 128 - needed < 0  # Impossible even before other stores and reserves.
    # A lower bound <=128 alone never proves the full workload fits.


def test_valid_design_preserves_same_accounts_without_second_inception():
    value = example()
    original = copy.deepcopy(value)
    result = check_design(value['predecessor'], value['successor'], value['synthetic_expected_state'],
                          digest(value['predecessor']))
    assert result == {'design_consistent': True, 'operational_admission': False}
    assert value == original
    assert {r['currency'] for r in value['successor']['opening_state'].values()} == {'USD', 'USDC'}


@pytest.mark.parametrize('damage', ['missing-predecessor', 'rollback', 'account', 'cash', 'duplicate',
                                    'resource-reuse', 'unknown', 'second-inception', 'missing-receipt'])
def test_continuation_design_rejects_incomplete_or_conflicting_evidence(damage):
    value = example()
    p, s = value['predecessor'], value['successor']
    trusted = digest(p)
    if damage == 'missing-predecessor': s['previous_digest'] = ''
    elif damage == 'rollback': p['high_water']['GLOBAL'] -= 1; s['previous_digest'] = digest(p)
    elif damage == 'account': s['opening_state']['QUALITY_DIPS']['epoch'] = 'FOREIGN'
    elif damage == 'cash': s['opening_state']['QUALITY_DIPS']['cash'] = '2000'
    elif damage == 'duplicate': s['operation_ids'] = p['operation_ids'][:]
    elif damage == 'resource-reuse': s['resources']['GLOBAL'] = p['resources']['GLOBAL']
    elif damage == 'unknown': p['unknown'] = True
    elif damage == 'second-inception': s['new_inception_count'] = 1
    else: s['custody_receipt'] = None
    with pytest.raises(ValueError):
        check_design(p, s, value['synthetic_expected_state'], trusted)


@pytest.mark.parametrize('phase', ['INTENT', 'RECORD', 'COMMIT', 'UNKNOWN'])
def test_interrupted_multi_store_design_never_grants_admission(phase):
    value = example()
    value['successor']['phase'] = phase
    with pytest.raises(ValueError):
        check_design(value['predecessor'], value['successor'], value['synthetic_expected_state'],
                     digest(value['predecessor']))
