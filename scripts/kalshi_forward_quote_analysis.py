"""Offline, retrospective forward-quote pairs. No trades, orders, or profit forecast."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path

from scripts.kalshi_forward_quote_observer import DEFAULT_PATH


def _decimal(value):
    try:
        number = Decimal(str(value))
        return number if number.is_finite() else None
    except (InvalidOperation, TypeError, ValueError):
        return None


def _time(value):
    try:
        result = datetime.fromisoformat(value.replace('Z', '+00:00'))
        return result if result.tzinfo is not None and result.utcoffset() is not None else None
    except (ValueError, TypeError, AttributeError):
        return None


def analyze(path: Path = DEFAULT_PATH) -> dict:
    if not path.exists():
        return {'status': 'NO_FORWARD_OBSERVATIONS', 'pairs': [], 'paired_count': 0,
                'orders_placed': 0, 'paper_trades_opened': 0}
    rows = []
    with path.open(encoding='utf-8') as source:
        for line in source:
            try:
                row = json.loads(line)
            except (ValueError, TypeError):
                continue
            if not isinstance(row, dict) or row.get('schema') != 'kalshi-forward-quote-v1':
                continue
            stamp = _time(row.get('observed_at'))
            listing = _time(row.get('open_time'))
            created = _time(row.get('created_time'))
            occurrence = _time(row.get('occurrence_datetime'))
            qty = _decimal(row.get('quantity'))
            if (stamp is None or listing is None or created is None or occurrence is None or
                stamp < max(listing, created) or stamp >= occurrence or
                qty is None or qty <= 0 or
                not isinstance(row.get('sides'), dict) or not isinstance(row.get('ticker'), str)):
                continue
            rows.append((stamp, row, qty))
    rows.sort(key=lambda item: item[0])
    previous = {}
    pairs = []
    for stamp, row, qty in rows:
        ticker = row['ticker']
        for side in ('YES', 'NO'):
            raw_quote = row['sides'].get(side)
            if not isinstance(raw_quote, dict):
                continue
            quote = dict(raw_quote)
            quote['_entry_gate_passed'] = row.get('entry_gate_passed') is True
            # Require identical exchange-issued listing and event identity.
            # A reused ticker or revised event date must never be paired.
            key = (ticker, side, qty, _time(row['created_time']),
                   _time(row['open_time']), _time(row['occurrence_datetime']))
            prior = previous.get(key)
            if prior is not None and stamp > prior[0]:
                buy = prior[1]
                if buy.get('buy_fillable') is True and quote.get('sell_fillable') is True:
                    entry = _decimal(buy.get('buy_vwap'))
                    exit_price = _decimal(quote.get('sell_vwap'))
                    entry_fee = _decimal(buy.get('buy_fee'))
                    exit_fee = _decimal(quote.get('sell_fee'))
                    if (None not in (entry, exit_price, entry_fee, exit_fee)
                        and 0 <= entry <= 1 and 0 <= exit_price <= 1
                        and entry_fee >= 0 and exit_fee >= 0):
                        gross = (exit_price - entry) * qty
                        # Separate research-only low-activity markets from
                        # markets meeting the unchanged entry prefilter.
                        entry_gate_passed = buy.get('_entry_gate_passed') is True
                        exit_gate_passed = quote.get('_entry_gate_passed') is True
                        cohort = ('ENTRY_PREFILTER_PASSED_BOTH' if entry_gate_passed and exit_gate_passed
                                  else 'EXPLORATORY_NOT_ENTRY_QUALIFIED')
                        pairs.append({'ticker': ticker, 'side': side, 'quantity': str(qty),
                                      'cohort': cohort,
                                      'entry_observed_at': prior[0].isoformat(),
                                      'exit_observed_at': stamp.isoformat(),
                                      'entry_vwap': str(entry), 'exit_vwap': str(exit_price),
                                      'gross_dollars': str(gross),
                                      'total_fees_dollars': str(entry_fee + exit_fee),
                                      'net_dollars': str(gross - entry_fee - exit_fee),
                                      'classification': 'RETROSPECTIVE_QUOTE_PAIR_NOT_TRADE'})
            previous[key] = (stamp, quote)
    # Summarize ALL valid chronological quote transitions, including losses.
    # These can overlap and are NOT independent executed trades or a backtest.
    nets = [Decimal(pair['net_dollars']) for pair in pairs]
    positive = sum(value > 0 for value in nets)
    negative = sum(value < 0 for value in nets)
    zero = len(nets) - positive - negative
    return {'status': 'PAIRED' if pairs else 'INSUFFICIENT_MATCHED_FORWARD_QUOTES',
            'pairs': pairs, 'paired_count': len(pairs),
            'quote_pair_summary': {
                'positive_pairs': positive, 'negative_pairs': negative,
                'zero_pairs': zero, 'sum_net_dollars': str(sum(nets, Decimal('0'))),
                'overlapping_pairs_possible': True,
                'not_realized_pnl': True,
                'exploratory_pairs': sum(p['cohort'] == 'EXPLORATORY_NOT_ENTRY_QUALIFIED' for p in pairs),
                'entry_prefilter_passed_pairs': sum(p['cohort'] == 'ENTRY_PREFILTER_PASSED_BOTH' for p in pairs),
            },
            'orders_placed': 0, 'paper_trades_opened': 0,
            'forecast_or_execution_proven': False}


if __name__ == '__main__':
    print(json.dumps(analyze(), sort_keys=True))