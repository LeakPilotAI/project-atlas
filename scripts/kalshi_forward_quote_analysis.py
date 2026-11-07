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
    # Count distinct observed listing identities, including those without a
    # second quote. A single quote is coverage, never a forward outcome.
    listing_groups = {}
    for stamp, row, qty in rows:
        identity = (row['ticker'], _time(row['created_time']),
                    _time(row['open_time']), _time(row['occurrence_datetime']))
        group = listing_groups.setdefault(identity, {'snapshots': 0, 'qualified_snapshots': 0})
        group['snapshots'] += 1
        group['qualified_snapshots'] += row.get('entry_gate_passed') is True
    # Compare earliest and latest qualified snapshots per immutable listing/side.
    # Unlike adjacent pairs, this reveals longer horizons across separate
    # operator-invoked sessions without inventing fills or future prices.
    qualified_horizons = {}
    for stamp, row, qty in rows:
        if row.get('entry_gate_passed') is not True:
            continue
        for side in ('YES', 'NO'):
            quote = row['sides'].get(side)
            if not isinstance(quote, dict):
                continue
            identity = (row['ticker'], side, qty, _time(row['created_time']),
                        _time(row['open_time']), _time(row['occurrence_datetime']))
            qualified_horizons.setdefault(identity, []).append((stamp, quote))
    horizon_results = []
    for identity, observations in qualified_horizons.items():
        first_stamp, first = observations[0]
        last_stamp, last = observations[-1]
        if last_stamp <= first_stamp or first.get('buy_fillable') is not True or last.get('sell_fillable') is not True:
            continue
        entry, exit_price = _decimal(first.get('buy_vwap')), _decimal(last.get('sell_vwap'))
        entry_fee, exit_fee = _decimal(first.get('buy_fee')), _decimal(last.get('sell_fee'))
        if (None in (entry, exit_price, entry_fee, exit_fee) or
            not 0 <= entry <= 1 or not 0 <= exit_price <= 1 or
            entry_fee < 0 or exit_fee < 0):
            continue
        net = (exit_price - entry) * identity[2] - entry_fee - exit_fee
        horizon_results.append({
            'ticker': identity[0], 'side': identity[1],
            'elapsed_seconds': str(Decimal(str((last_stamp - first_stamp).total_seconds()))),
            'net_dollars': str(net), 'fee_adjusted_break_even_met': net >= 0,
            'classification': 'RETROSPECTIVE_QUALIFIED_QUOTE_HORIZON_NOT_TRADE',
        })
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
                                      'listing_created_at': key[3].isoformat(),
                                      'listing_open_at': key[4].isoformat(),
                                      'event_occurrence_at': key[5].isoformat(),
                                      'cohort': cohort,
                                      'entry_observed_at': prior[0].isoformat(),
                                      'exit_observed_at': stamp.isoformat(),
                                      'elapsed_seconds': str(Decimal(str((stamp - prior[0]).total_seconds()))),
                                      'required_exit_bid_to_break_even': str(entry + (entry_fee + exit_fee) / qty),
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
    # Non-overlapping quote transitions: each snapshot may belong to at most
    # one selected transition for a ticker/side/listing. This reduces repeated
    # reuse of the same evidence; it still does NOT create independent trades.
    disjoint_pairs = []
    used_snapshots = set()
    for pair in pairs:
        identity = (pair['ticker'], pair['side'], pair['quantity'],
                    pair['listing_created_at'], pair['listing_open_at'],
                    pair['event_occurrence_at'])
        first = (*identity, pair['entry_observed_at'])
        last = (*identity, pair['exit_observed_at'])
        if first not in used_snapshots and last not in used_snapshots:
            disjoint_pairs.append(pair)
            used_snapshots.update((first, last))
    cohorts = {}
    for name in ('ENTRY_PREFILTER_PASSED_BOTH', 'EXPLORATORY_NOT_ENTRY_QUALIFIED'):
        group = [p for p in pairs if p['cohort'] == name]
        values = [Decimal(p['net_dollars']) for p in group]
        cohorts[name] = {
            'pairs': len(group),
            'non_overlapping_snapshot_pairs': sum(p['cohort'] == name for p in disjoint_pairs),
            'positive': sum(v > 0 for v in values),
            'negative': sum(v < 0 for v in values),
            'zero': sum(v == 0 for v in values),
            'sum_hypothetical_net_dollars': str(sum(values, Decimal('0'))),
            'distinct_tickers': len({p['ticker'] for p in group}),
            'pairs_under_60_seconds': sum(Decimal(p['elapsed_seconds']) < 60 for p in group),
            'pairs_at_least_60_seconds': sum(Decimal(p['elapsed_seconds']) >= 60 for p in group),
            'pairs_at_least_300_seconds': sum(Decimal(p['elapsed_seconds']) >= 300 for p in group),
            'pairs_at_least_300_seconds_net_positive': sum(
                Decimal(p['elapsed_seconds']) >= 300 and Decimal(p['net_dollars']) > 0
                for p in group),
            'pairs_exit_bid_met_fee_adjusted_break_even': sum(
                Decimal(p['exit_vwap']) >= Decimal(p['required_exit_bid_to_break_even'])
                for p in group),
            'pairs_break_even_bid_above_contract_max': sum(
                Decimal(p['required_exit_bid_to_break_even']) > 1 for p in group),
            'longest_observation_gap_seconds': str(max(
                (Decimal(p['elapsed_seconds']) for p in group), default=Decimal('0'))),
            'not_realized_pnl': True,
        }
    return {'status': 'PAIRED' if pairs else 'INSUFFICIENT_MATCHED_FORWARD_QUOTES',
            'pairs': pairs, 'paired_count': len(pairs),
            'cohort_summary': cohorts,
            'qualified_first_to_last_horizons': {
                'comparisons': horizon_results,
                'count': len(horizon_results),
                'at_least_300_seconds': sum(Decimal(p['elapsed_seconds']) >= 300 for p in horizon_results),
                'fee_adjusted_break_even_met': sum(p['fee_adjusted_break_even_met'] for p in horizon_results),
                'not_executed_trades': True,
            },
            'listing_coverage': {
                'distinct_observed_listings': len(listing_groups),
                'distinct_listings_with_qualified_snapshot': sum(
                    group['qualified_snapshots'] > 0 for group in listing_groups.values()),
                'distinct_listings_with_multiple_snapshots': sum(
                    group['snapshots'] >= 2 for group in listing_groups.values()),
                'distinct_qualified_listings_with_multiple_snapshots': sum(
                    group['qualified_snapshots'] >= 2 for group in listing_groups.values()),
                'qualified_snapshot_count': sum(
                    group['qualified_snapshots'] for group in listing_groups.values()),
                'not_independent_trades': True,
            },
            'quote_pair_summary': {
                'positive_pairs': positive, 'negative_pairs': negative,
                'zero_pairs': zero, 'sum_net_dollars': str(sum(nets, Decimal('0'))),
                'overlapping_pairs_possible': True,
                'non_overlapping_snapshot_pairs': len(disjoint_pairs),
                'non_overlapping_is_not_independent_trades': True,
                'not_realized_pnl': True,
                'exploratory_pairs': sum(p['cohort'] == 'EXPLORATORY_NOT_ENTRY_QUALIFIED' for p in pairs),
                'entry_prefilter_passed_pairs': sum(p['cohort'] == 'ENTRY_PREFILTER_PASSED_BOTH' for p in pairs),
            },
            'orders_placed': 0, 'paper_trades_opened': 0,
            'forecast_or_execution_proven': False}


if __name__ == '__main__':
    print(json.dumps(analyze(), sort_keys=True))