"""The existing QD engine previews without publication; commit rechecks evidence."""
import copy
from concurrent.futures import ThreadPoolExecutor

import pytest
from app.services.paper_financial_replay import digest
from app.services.quality_dips_autonomous_paper import NoFill
from test_quality_dips_autonomous_paper import candidate, quote, setup


def request(n):
    b = candidate(n)
    return {'bundles': [b], 'quotes': [quote(n, b)], 'observation': None}


def test_preview_is_read_only_and_exact_guard_commits_existing_decision(tmp_path):
    n = setup(tmp_path)
    frame = request(n)
    original = copy.deepcopy(frame)
    before = n.ledger.path.read_bytes()
    preview = n.engine.preview('first', **frame)
    assert n.ledger.path.read_bytes() == before and frame == original
    assert not preview['authority_granted'] and preview['command_digest'] == digest(preview['command'])
    result = n.engine.step('first', **frame, expected_command_digest=preview['command_digest'])
    assert result['filled'] and result['receipt'] == preview['receipt']
    with n.ledger.connect(readonly=True) as db:
        assert n.ledger._load(db)[0] == preview['after']


def test_changed_accepted_quote_refuses_before_financial_event(tmp_path):
    n = setup(tmp_path)
    frame = request(n)
    preview = n.engine.preview('first', **frame)
    frame['quotes'][0]['bid'] = '99.8'
    result = n.engine.step('first', **frame, expected_command_digest=preview['command_digest'])
    assert not result['filled'] and result['reason'] == 'PREVIEW_COMMAND_CHANGED'
    assert n.ledger.snapshot()['revision'] == 0 and n.ledger.snapshot()['cash'] == '1000'


@pytest.mark.parametrize('failure', ['revoked', 'expired', 'stale', 'closed'])
def test_preview_refusal_has_no_financial_or_diagnostic_effects(failure, tmp_path):
    n = setup(tmp_path)
    frame = request(n)
    if failure == 'revoked': n.revoked[0] = True
    elif failure == 'expired': n.now[0] += 3601
    elif failure == 'stale': n.now[0] += 6
    else: n.engine.dispatch_closed = True
    before = n.ledger.path.read_bytes()
    with pytest.raises(ValueError): n.engine.preview('first', **frame)
    assert n.ledger.path.read_bytes() == before


def test_preview_does_not_replay_acknowledged_operation(tmp_path):
    n = setup(tmp_path)
    frame = request(n)
    preview = n.engine.preview('first', **frame)
    assert n.engine.step('first', **frame, expected_command_digest=preview['command_digest'])['filled']
    before = n.ledger.path.read_bytes()
    with pytest.raises(NoFill, match='ALREADY_ACKNOWLEDGED'): n.engine.preview('first', **frame)
    assert n.ledger.path.read_bytes() == before


def test_unknown_projection_blocks_preview_without_replaying_callback(tmp_path):
    n = setup(tmp_path)
    frame = request(n)
    def failed(phase):
        if phase == 'after_commit': raise OSError('SYNTHETIC_COMMIT_BEFORE_ACK')
    assert n.engine.step('first', **frame, fault=failed)['reason'] == 'UNKNOWN_OR_CORRUPT'
    before = n.ledger.path.read_bytes()
    with pytest.raises(NoFill, match='UNKNOWN_ACK'): n.engine.preview('first', **frame)
    assert n.ledger.path.read_bytes() == before


def test_concurrent_previews_have_no_effect_and_duplicate_commit_is_one_event(tmp_path):
    n = setup(tmp_path)
    frame = request(n)
    with ThreadPoolExecutor(2) as pool:
        previews = list(pool.map(lambda _: n.engine.preview('first', **frame), range(2)))
    assert previews[0] == previews[1] and n.ledger.snapshot()['revision'] == 0
    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(lambda _: n.engine.step('first', **frame, expected_command_digest=previews[0]['command_digest']), range(2)))
    assert results[0]['receipt'] == results[1]['receipt'] and n.ledger.snapshot()['revision'] == 1
