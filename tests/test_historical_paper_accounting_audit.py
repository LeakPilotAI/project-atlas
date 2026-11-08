"""Synthetic accounting checks; no retained PAPER journals are modified."""
import json

from scripts.diagnostics.audit_historical_paper_accounting import audit


def _write(path, rows):
    path.write_text(''.join(json.dumps(row) + '\n' for row in rows), encoding='utf-8')


def _case(tmp_path, trade_rows):
    pending, paper = tmp_path / 'pending.jsonl', tmp_path / 'paper.jsonl'
    _write(pending, [{'event': event, 'setup_instance_id': 'id',
                      'timestamp': f'2026-01-01T00:00:0{n}+00:00'}
                     for n, event in enumerate(('armed', 'cancelled', 'armed', 'filled'))])
    _write(paper, trade_rows)
    before = pending.read_bytes(), paper.read_bytes()
    result = audit(pending, paper)['cases'][0]
    assert before == (pending.read_bytes(), paper.read_bytes())
    return result


def _open():
    return {'event': 'open', 'trade_id': 't', 'source': 'perp_manual_auto',
            'features': {'setup_instance_id': 'id'}, 'trade_type': 'PAPER',
            'counts_for_live': False, 'entry_timestamp': '2026-01-01T00:00:03+00:00',
            'actual_entry_price': 100, 'risk_price': 10, 'side': 'LONG',
            'fees_bps': 2, 'slippage_bps': 1}


def _close():
    return {'event': 'close', 'trade_id': 't', 'trade_type': 'PAPER',
            'counts_for_live': False, 'exit_timestamp': '2026-01-01T00:00:05+00:00',
            'actual_exit_price': 110, 'net_pnl_r': 0.994, 'result': 'WIN'}


def test_recomputes_net_r_and_separates_historical_mark_from_current(tmp_path):
    mark = {'event': 'mark', 'trade_id': 't', 'timestamp': '2026-01-01T00:00:04+00:00',
            'unrealized_r': 0.5}
    result = _case(tmp_path, [_open(), mark, _close()])
    assert result['accounting_status'] == 'LOCALLY_CONSISTENT_UNAUTHENTICATED'
    trade = result['trades'][0]
    assert trade['recomputed_closed_net_r'] == trade['recorded_closed_net_r'] == 0.994
    assert trade['last_recorded_mark_unrealized_r'] == 0.5
    assert trade['current_unrealized_r'] is None


def test_duplicate_close_and_bad_accounting_remain_incomplete(tmp_path):
    bad = {**_close(), 'net_pnl_r': 3}
    result = _case(tmp_path, [_open(), bad, _close()])
    assert result['accounting_status'] == 'INCOMPLETE'
    assert 'duplicate close' in ' '.join(result['findings'])


def test_orphan_close_and_missing_open_are_incomplete(tmp_path):
    result = _case(tmp_path, [{**_close(), 'features': {'setup_instance_id': 'id'}}])
    assert result['accounting_status'] == 'INCOMPLETE'
    assert 'orphan mark or close' in ' '.join(result['findings'])


def test_missing_cost_inputs_do_not_invent_recomputed_result(tmp_path):
    opened = _open()
    del opened['fees_bps']
    result = _case(tmp_path, [opened, _close()])
    assert result['trades'][0]['recomputed_closed_net_r'] is None
    assert result['accounting_status'] == 'INCOMPLETE'
