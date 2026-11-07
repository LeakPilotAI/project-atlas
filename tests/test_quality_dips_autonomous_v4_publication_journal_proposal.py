"""Source-only proposed V4 reserve/commit/crash recovery contract."""
import copy
import pytest
from app.services.quality_dips_autonomous_v4_publication_journal_proposal import (
    initial_publication_journal, transition_publication_journal)


def record(i=1):
    return {'publication_digest': f'{i:064x}', 'publication_id': f'PUB-{i}'}


def run(state, op, value=None):
    return transition_publication_journal(state, op, value)


def test_reserve_commit_advances_monotonic_digest_chain_without_mutating_inputs():
    start = initial_publication_journal()
    source = record()
    reserved = run(start, 'RESERVE', source)
    assert start['revision'] == 0 and start['pending'] is None
    assert reserved['revision'] == 0 and reserved['pending']['record'] == source
    committed = run(reserved, 'COMMIT')
    assert committed['revision'] == 1 and committed['pending'] is None
    assert committed['head'] and committed['status'] == 'IDLE'
    assert run(committed, 'RESTART') == committed
    second = run(run(committed, 'RESERVE', record(2)), 'COMMIT')
    assert second['revision'] == 2 and second['head'] != committed['head']
    assert source == record()


def test_uncertain_restart_fences_commit_and_new_reserve():
    reserved = run(initial_publication_journal(), 'RESERVE', record())
    uncertain = run(reserved, 'RESTART')
    assert uncertain['status'] == 'UNCERTAIN'
    assert uncertain['pending'] == reserved['pending']
    with pytest.raises(ValueError): run(uncertain, 'COMMIT')
    with pytest.raises(ValueError): run(uncertain, 'RESERVE', record(2))
    assert run(uncertain, 'RESTART') == uncertain


@pytest.mark.parametrize('operation', ['COMMIT', 'UNKNOWN'])
def test_invalid_operations_refused_on_inception(operation):
    with pytest.raises(ValueError): run(initial_publication_journal(), operation)


@pytest.mark.parametrize('damage', ['missing_digest', 'extra_field', 'bad_id', 'bad_digest', 'bool_revision',
    'wrong_schema', 'forged_head', 'pending_removed', 'pending_revision', 'pending_parent',
    'commit_with_record', 'double_reserve'])
def test_corrupt_or_invalid_journal_operations_refused(damage):
    start = initial_publication_journal()
    reserved = run(start, 'RESERVE', record())
    if damage in ('missing_digest', 'extra_field', 'bad_id', 'bad_digest'):
        source = record()
        if damage == 'missing_digest': source.pop('publication_digest')
        if damage == 'extra_field': source['approved'] = True
        if damage == 'bad_id': source['publication_id'] = ''
        if damage == 'bad_digest': source['publication_digest'] = 'short'
        action = lambda: run(start, 'RESERVE', source)
    elif damage == 'double_reserve': action = lambda: run(reserved, 'RESERVE', record(2))
    elif damage == 'commit_with_record': action = lambda: run(reserved, 'COMMIT', record())
    else:
        broken = copy.deepcopy(reserved)
        if damage == 'bool_revision': broken['revision'] = True
        if damage == 'wrong_schema': broken['schema'] = 'OTHER'
        if damage == 'forged_head': broken['head'] = 'f' * 64
        if damage == 'pending_removed': broken['pending'] = None
        if damage == 'pending_revision': broken['pending']['revision'] = 3
        if damage == 'pending_parent': broken['pending']['previous'] = 'f' * 64
        action = lambda: run(broken, 'COMMIT')
    with pytest.raises(ValueError): action()


def test_revision_capacity_fails_closed():
    state = initial_publication_journal()
    for i in range(1, 129):
        state = run(run(state, 'RESERVE', record(i)), 'COMMIT')
    assert state['revision'] == 128
    with pytest.raises(ValueError): run(state, 'RESERVE', record(129))
@pytest.mark.parametrize('damage', ['digest_nonhex', 'digest_uppercase', 'pending_digest_short',
    'pending_digest_nonhex', 'pending_id_empty', 'pending_id_extra', 'pending_record_extra',
    'pending_record_missing', 'pending_revision_bool', 'pending_revision_over_capacity',
    'pending_wrong_parent', 'committed_head_nonhex', 'uncertain_pending_invalid'])
def test_malformed_persisted_journal_refuses_even_restart(damage):
    state = run(initial_publication_journal(), 'RESERVE', record())
    if damage == 'digest_nonhex':
        with pytest.raises(ValueError): run(initial_publication_journal(), 'RESERVE',
            {**record(), 'publication_digest': 'g'*64})
        return
    if damage == 'digest_uppercase':
        with pytest.raises(ValueError): run(initial_publication_journal(), 'RESERVE',
            {**record(), 'publication_digest': 'A'*64})
        return
    if damage == 'pending_digest_short': state['pending']['record']['publication_digest'] = 'short'
    if damage == 'pending_digest_nonhex': state['pending']['record']['publication_digest'] = 'z'*64
    if damage == 'pending_id_empty': state['pending']['record']['publication_id'] = ''
    if damage == 'pending_id_extra': state['pending']['record']['publication_id'] = 'x'*129
    if damage == 'pending_record_extra': state['pending']['record']['authorized'] = True
    if damage == 'pending_record_missing': state['pending']['record'].pop('publication_id')
    if damage == 'pending_revision_bool': state['pending']['revision'] = True
    if damage == 'pending_revision_over_capacity': state['pending']['revision'] = 129
    if damage == 'pending_wrong_parent': state['pending']['previous'] = 'f'*64
    if damage == 'committed_head_nonhex':
        state = run(state, 'COMMIT')
        state['head'] = 'z'*64
    if damage == 'uncertain_pending_invalid':
        state['status'] = 'UNCERTAIN'
        state['pending']['record']['publication_digest'] = 'z'*64
    with pytest.raises(ValueError): run(state, 'RESTART')
    with pytest.raises(ValueError): run(state, 'COMMIT')