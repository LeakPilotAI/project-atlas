from datetime import datetime, timedelta, timezone
import json

from scripts.kalshi_forward_quote_analysis import analyze


def row(time, *, ticker='KX-ONE', buy='0.40', sell='0.38', buy_fee='0.02', sell_fee='0.02', quantity='10', sell_ok=True):
    return {'schema': 'kalshi-forward-quote-v1', 'ticker': ticker,
            'observed_at': time.isoformat(),
            'created_time': time.replace(hour=10, minute=0, second=0, microsecond=0).isoformat(),
            'open_time': time.replace(hour=11, minute=0, second=0, microsecond=0).isoformat(),
            'occurrence_datetime': time.replace(hour=16, minute=0, second=0, microsecond=0).isoformat(),
            'quantity': quantity,
            'sides': {'YES': {'buy_fillable': True, 'sell_fillable': sell_ok,
                              'buy_vwap': buy, 'sell_vwap': sell,
                              'buy_fee': buy_fee, 'sell_fee': sell_fee}}}


def write(path, rows):
    path.write_text(''.join(json.dumps(r) + '\n' for r in rows), encoding='utf-8')


def test_pairs_use_earlier_buy_later_sell_and_both_fees(tmp_path):
    now = datetime(2026, 11, 7, 12, tzinfo=timezone.utc)
    path = tmp_path / 'quotes.jsonl'
    write(path, [row(now + timedelta(minutes=5), sell='0.48', buy='0.50', sell_fee='0.03'),
                 row(now, buy='0.40')])
    result = analyze(path)
    assert result['paired_count'] == 1
    assert result['pairs'][0]['gross_dollars'] == '0.80'
    assert result['pairs'][0]['total_fees_dollars'] == '0.05'
    assert result['pairs'][0]['net_dollars'] == '0.75'
    assert result['forecast_or_execution_proven'] is False
    assert result['quote_pair_summary']['positive_pairs'] == 1
    assert result['quote_pair_summary']['sum_net_dollars'] == '0.75'
    assert result['quote_pair_summary']['not_realized_pnl'] is True
    assert result['quote_pair_summary']['exploratory_pairs'] == 1
    assert result['quote_pair_summary']['entry_prefilter_passed_pairs'] == 0
    assert result['pairs'][0]['elapsed_seconds'] == '300.0'
    assert result['pairs'][0]['required_exit_bid_to_break_even'] == '0.405'
    assert result['cohort_summary']['EXPLORATORY_NOT_ENTRY_QUALIFIED']['pairs'] == 1
    assert result['cohort_summary']['EXPLORATORY_NOT_ENTRY_QUALIFIED']['pairs_at_least_60_seconds'] == 1
    assert result['cohort_summary']['EXPLORATORY_NOT_ENTRY_QUALIFIED']['pairs_under_60_seconds'] == 0
    assert result['cohort_summary']['EXPLORATORY_NOT_ENTRY_QUALIFIED']['longest_observation_gap_seconds'] == '300.0'
    assert result['cohort_summary']['EXPLORATORY_NOT_ENTRY_QUALIFIED']['pairs_at_least_300_seconds'] == 1
    assert result['cohort_summary']['EXPLORATORY_NOT_ENTRY_QUALIFIED']['pairs_at_least_300_seconds_net_positive'] == 1
    assert result['cohort_summary']['EXPLORATORY_NOT_ENTRY_QUALIFIED']['pairs_exit_bid_met_fee_adjusted_break_even'] == 1
    assert result['cohort_summary']['EXPLORATORY_NOT_ENTRY_QUALIFIED']['pairs_break_even_bid_above_contract_max'] == 0
    assert result['cohort_summary']['ENTRY_PREFILTER_PASSED_BOTH']['pairs'] == 0


def test_no_same_timestamp_or_unfillable_exit(tmp_path):
    now = datetime(2026, 11, 7, 12, tzinfo=timezone.utc)
    path = tmp_path / 'quotes.jsonl'
    write(path, [row(now), row(now), row(now + timedelta(minutes=1), sell_ok=False)])
    assert analyze(path)['paired_count'] == 0


def test_rejects_post_event_quote_pairs(tmp_path):
    now = datetime(2026, 11, 7, 12, tzinfo=timezone.utc)
    path = tmp_path / 'quotes.jsonl'
    first = row(now)
    second = row(now + timedelta(minutes=5), sell='0.90')
    second['occurrence_datetime'] = (now + timedelta(minutes=3)).isoformat()
    write(path, [first, second])
    assert analyze(path)['paired_count'] == 0


def test_reused_ticker_different_listing_or_event_is_not_paired(tmp_path):
    now = datetime(2026, 11, 7, 12, tzinfo=timezone.utc)
    path = tmp_path / 'quotes.jsonl'
    initial = row(now)
    changed_listing = row(now + timedelta(minutes=1), sell='0.90')
    changed_listing['created_time'] = (now - timedelta(minutes=30)).isoformat()
    changed_event = row(now + timedelta(minutes=2), sell='0.90')
    changed_event['occurrence_datetime'] = (now + timedelta(hours=5)).isoformat()
    write(path, [initial, changed_listing, changed_event])
    assert analyze(path)['paired_count'] == 0


def test_non_overlapping_snapshot_pair_count_does_not_reuse_middle_quote(tmp_path):
    now = datetime(2026, 11, 7, 12, tzinfo=timezone.utc)
    path = tmp_path / 'quotes.jsonl'
    write(path, [row(now), row(now + timedelta(minutes=1)),
                 row(now + timedelta(minutes=2)), row(now + timedelta(minutes=3))])
    result = analyze(path)
    assert result['paired_count'] == 3
    assert result['quote_pair_summary']['non_overlapping_snapshot_pairs'] == 2
    assert result['cohort_summary']['EXPLORATORY_NOT_ENTRY_QUALIFIED']['non_overlapping_snapshot_pairs'] == 2
    assert result['quote_pair_summary']['non_overlapping_is_not_independent_trades'] is True


def test_listing_coverage_includes_single_snapshot_without_pair(tmp_path):
    now = datetime(2026, 11, 7, 12, tzinfo=timezone.utc)
    path = tmp_path / 'quotes.jsonl'
    qualified = row(now, ticker='KX-QUAL')
    qualified['entry_gate_passed'] = True
    write(path, [qualified, row(now, ticker='KX-EXP')])
    result = analyze(path)
    assert result['paired_count'] == 0
    assert result['listing_coverage']['distinct_observed_listings'] == 2
    assert result['listing_coverage']['distinct_listings_with_qualified_snapshot'] == 1
    assert result['listing_coverage']['distinct_qualified_listings_with_multiple_snapshots'] == 0
    assert result['listing_coverage']['qualified_snapshot_count'] == 1


def test_missing_file_is_no_evidence(tmp_path):
    assert analyze(tmp_path / 'missing.jsonl')['status'] == 'NO_FORWARD_OBSERVATIONS'


def test_invalid_and_cross_market_rows_refused(tmp_path):
    now = datetime(2026, 11, 7, 12, tzinfo=timezone.utc)
    path = tmp_path / 'quotes.jsonl'
    write(path, [row(now), row(now + timedelta(minutes=1), ticker='KX-TWO'),
                 row(now + timedelta(minutes=2), buy='NaN', sell='Infinity')])
    assert analyze(path)['paired_count'] == 0