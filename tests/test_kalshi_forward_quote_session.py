import asyncio
import pytest
from scripts.kalshi_forward_quote_session import run


def test_bounded_session_collects_twice_and_analyzes():
    calls = []
    async def collector():
        calls.append('collect')
        return {'records_written': 1, 'provider_errors': []}
    async def sleep(seconds):
        calls.append(seconds)
    def analyzer():
        calls.append('analyze')
        return {'paired_count': 1}
    result = asyncio.run(run(collector=collector, analyzer=analyzer, sleep=sleep))
    assert calls == ['collect', 60.0, 'collect', 'analyze']
    assert result['cycles_completed'] == 2
    assert result['orders_placed'] == 0
    assert result['unattended_runtime_started'] is False


def test_provider_error_stops_session():
    async def collector():
        return {'provider_errors': ['unavailable']}
    result = asyncio.run(run(collector=collector, analyzer=lambda: {'paired_count': 0}))
    assert result['cycles_completed'] == 1


@pytest.mark.parametrize('cycles,interval', [(0, 60), (4, 60), (2, 0), (2, 301)])
def test_unbounded_session_refused(cycles, interval):
    with pytest.raises(ValueError):
        asyncio.run(run(cycles=cycles, interval_seconds=interval))
def test_eligibility_trend_does_not_infer_same_listing_turnover():
    scans = iter([
        {'unique_markets_screened': 500, 'entry_gate_qualified_new_listings_seen': 7,
         'rejection_reason_counts': {'INSUFFICIENT_24H_VOLUME': 492,
                                     'INSUFFICIENT_OPEN_INTEREST': 486}, 'provider_errors': []},
        {'unique_markets_screened': 500, 'entry_gate_qualified_new_listings_seen': 0,
         'rejection_reason_counts': {'INSUFFICIENT_24H_VOLUME': 500,
                                     'INSUFFICIENT_OPEN_INTEREST': 500}, 'provider_errors': []},
    ])
    async def collector():
        return next(scans)
    async def sleep(_):
        return None
    result = asyncio.run(run(collector=collector, sleep=sleep, analyzer=lambda: {}))
    assert [row['qualified'] for row in result['eligibility_trend']] == [7, 0]
    assert [row['qualified_fraction'] for row in result['eligibility_trend']] == [0.014, 0.0]
    assert result['listing_identity_overlap_not_measured'] is True
    assert result['qualification_change_cause_unverified'] is True
    assert result['orders_placed'] == result['paper_trades_opened'] == 0

def test_identity_overlap_distinguishes_turnover_from_same_market_eligibility():
    scans = iter([
        {'scan_qualification_by_ticker': {'A': True, 'B': False, 'C': True},
         'provider_errors': []},
        {'scan_qualification_by_ticker': {'A': False, 'B': True, 'D': True},
         'provider_errors': []},
    ])
    async def collector():
        return next(scans)
    async def sleep(_):
        return None
    result = asyncio.run(run(collector=collector, sleep=sleep, analyzer=lambda: {}))
    assert result['listing_identity_overlap'] == [{
        'from_cycle': 1, 'to_cycle': 2, 'shared_tickers': 2,
        'prior_only_tickers': 1, 'current_only_tickers': 1,
        'shared_remained_qualified': 0, 'shared_lost_qualification': 1,
        'shared_gained_qualification': 1, 'shared_remained_unqualified': 0,
    }]
    assert result['listing_identity_overlap_not_measured'] is False
    assert result['qualification_change_cause_unverified'] is True
    assert all('scan_qualification_by_ticker' not in x for x in result['observations'])
    assert result['orders_placed'] == result['paper_trades_opened'] == 0
