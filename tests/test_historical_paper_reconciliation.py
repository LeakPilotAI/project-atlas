"""Disposable-only tests for read-only historical identity classification."""
import json

import pytest

from scripts.diagnostics.reconcile_pending_paper_history import reconcile


def _write(path, rows):
    payload = ''.join(json.dumps(row) + '\n' for row in rows).encode()
    path.write_bytes(payload)
    return payload


def test_cancel_rearm_with_linked_single_paper_trade_requires_exception(tmp_path):
    pending = tmp_path / 'pending.jsonl'
    paper = tmp_path / 'paper.jsonl'
    identity = 'BTC:LONG|first|epoch'
    before_pending = _write(pending, [
        {'event': 'armed', 'setup_instance_id': identity, 'timestamp': '2026-09-11T00:00:01+00:00'},
        {'event': 'cancelled', 'setup_instance_id': identity, 'timestamp': '2026-09-11T00:00:02+00:00'},
        {'event': 'armed', 'setup_instance_id': identity, 'timestamp': '2026-09-11T00:00:03+00:00'},
        {'event': 'filled', 'setup_instance_id': identity, 'timestamp': '2026-09-11T00:00:04+00:00'},
    ])
    before_paper = _write(paper, [
        {'event': 'open', 'source': 'perp_manual_auto', 'trade_id': 'one',
         'features': {'setup_instance_id': identity}, 'entry_timestamp': '2026-09-11T00:00:04+00:00',
         'trade_type': 'PAPER', 'counts_for_live': False},
        {'event': 'close', 'trade_id': 'one', 'exit_timestamp': '2026-09-11T00:00:05+00:00',
         'trade_type': 'PAPER', 'counts_for_live': False, 'net_pnl_r': 1.0},
    ])
    report = reconcile(pending, paper)
    assert report['affected_identities'] == report['violating_rearm_events'] == 1
    assert report['cases'][0]['classification'] == 'HISTORICAL EXCEPTION REQUIRED'
    assert report['cases'][0]['paper_open_count'] == report['cases'][0]['paper_close_count'] == 1
    assert pending.read_bytes() == before_pending and paper.read_bytes() == before_paper


def test_missing_linked_open_never_becomes_compatible(tmp_path):
    pending = tmp_path / 'pending.jsonl'
    paper = tmp_path / 'paper.jsonl'
    _write(pending, [{'event': event, 'setup_instance_id': 'x', 'timestamp': f'2026-09-11T00:00:0{n}+00:00'}
                     for n, event in enumerate(('armed', 'cancelled', 'armed', 'filled'))])
    _write(paper, [{'event': 'session_start'}])
    case = reconcile(pending, paper)['cases'][0]
    assert case['classification'] == 'INSUFFICIENT EVIDENCE'
    assert 'pending fill has no linked PAPER open' in case['missing_or_ambiguous']


def test_duplicate_json_field_refuses_before_classification(tmp_path):
    pending = tmp_path / 'pending.jsonl'
    paper = tmp_path / 'paper.jsonl'
    pending.write_bytes(b'{"event":"armed","event":"cancelled","setup_instance_id":"x"}\n')
    _write(paper, [{'event': 'session_start'}])
    with pytest.raises(ValueError, match='duplicate JSON field'):
        reconcile(pending, paper)


def test_replayed_identity_with_live_authority_claim_is_contradictory(tmp_path):
    pending = tmp_path / 'pending.jsonl'
    paper = tmp_path / 'paper.jsonl'
    identity = 'x'
    _write(pending, [{'event': event, 'setup_instance_id': identity,
                      'timestamp': f'2026-09-11T00:00:0{n}+00:00'}
                     for n, event in enumerate(('armed', 'cancelled', 'armed', 'filled'))])
    _write(paper, [{'event': 'open', 'source': 'perp_manual_auto', 'trade_id': 'one',
                    'features': {'setup_instance_id': identity}, 'trade_type': 'PAPER',
                    'counts_for_live': True}])
    case = reconcile(pending, paper)['cases'][0]
    assert case['classification'] == 'CONTRADICTORY EVIDENCE'


def test_duplicate_linked_paper_opens_are_contradictory(tmp_path):
    pending = tmp_path / 'pending.jsonl'
    paper = tmp_path / 'paper.jsonl'
    identity = 'x'
    _write(pending, [{'event': event, 'setup_instance_id': identity,
                      'timestamp': f'2026-09-11T00:00:0{n}+00:00'}
                     for n, event in enumerate(('armed', 'cancelled', 'armed', 'filled'))])
    _write(paper, [{'event': 'open', 'source': 'perp_manual_auto', 'trade_id': trade_id,
                    'features': {'setup_instance_id': identity}, 'trade_type': 'PAPER',
                    'counts_for_live': False} for trade_id in ('one', 'two')])
    case = reconcile(pending, paper)['cases'][0]
    assert case['paper_open_count'] == 2
    assert case['classification'] == 'CONTRADICTORY EVIDENCE'


def test_pending_event_clock_reversal_is_contradictory(tmp_path):
    pending = tmp_path / 'pending.jsonl'
    paper = tmp_path / 'paper.jsonl'
    _write(pending, [
        {'event': 'armed', 'setup_instance_id': 'x', 'timestamp': '2026-09-11T00:00:02+00:00'},
        {'event': 'cancelled', 'setup_instance_id': 'x', 'timestamp': '2026-09-11T00:00:01+00:00'},
        {'event': 'armed', 'setup_instance_id': 'x', 'timestamp': '2026-09-11T00:00:03+00:00'},
    ])
    _write(paper, [{'event': 'session_start'}])
    case = reconcile(pending, paper)['cases'][0]
    assert case['classification'] == 'CONTRADICTORY EVIDENCE'
    assert 'pending event chronology unavailable or out of order' in case['missing_or_ambiguous']
