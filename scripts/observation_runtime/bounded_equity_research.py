"""Operator-invoked bounded automatic equity research; no PAPER or broker orders."""
import argparse
import json
import os

from scripts.observation_runtime.alpaca_equity_catalog import score_authenticated_provider_batch


def run_cycles(*, contact, cycles=3, batch_size=2, runner=score_authenticated_provider_batch):
    if type(cycles) is not int or not 1 <= cycles <= 10:
        raise ValueError('RESEARCH_CYCLE_BUDGET_REFUSED')
    if type(batch_size) is not int or not 1 <= batch_size <= 2:
        raise ValueError('RESEARCH_BATCH_BUDGET_REFUSED')
    completed = 0
    for _ in range(cycles):
        result = runner(contact=contact, limit=batch_size, finalize=True)
        if type(result) is not dict or result.get('status') != 'RESEARCH_FINALIZED' or result.get('cursor_advanced') is not True:
            return {'status': 'BLOCKED', 'completed': completed, 'paper_execution_authorized': False,
                    'live_order_authorized': False}
        if (result.get('schema') != 'ATLAS_BROAD_RESEARCH_CYCLE_V1'
                or type(result.get('completed')) is not int
                or not 1 <= result['completed'] <= batch_size
                or type(result.get('receipt_sha256')) is not str
                or len(result['receipt_sha256']) != 64
                or any(c not in '0123456789abcdef' for c in result['receipt_sha256'])
                or result.get('paper_execution_authorized') is not False
                or result.get('live_order_authorized') is not False):
            return {'status': 'BLOCKED', 'completed': completed, 'paper_execution_authorized': False,
                    'live_order_authorized': False}
        completed += result['completed']
    return {'status': 'RESEARCH_FINALIZED', 'completed': completed,
            'paper_execution_authorized': False, 'live_order_authorized': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--cycles', type=int, default=3)
    parser.add_argument('--batch-size', type=int, default=2)
    args = parser.parse_args()
    try:
        result = run_cycles(contact=os.environ.get('ATLAS_SEC_CONTACT'), cycles=args.cycles,
                            batch_size=args.batch_size)
    except (ValueError, OSError, KeyError, TypeError):
        result = {'status': 'REFUSED', 'completed': 0, 'paper_execution_authorized': False,
                  'live_order_authorized': False}
    print(json.dumps(result, sort_keys=True))
    return 0 if result['status'] == 'RESEARCH_FINALIZED' else 1


if __name__ == '__main__':
    raise SystemExit(main())