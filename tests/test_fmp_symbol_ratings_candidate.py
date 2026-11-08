import pytest
from scripts.observation_runtime.fmp_symbol_ratings_candidate import candidate_url, assess_records


def test_fixed_bounded_url():
    url=candidate_url('MSFT','secret')
    assert url.startswith('https://financialmodelingprep.com/stable/tipranks-search?')
    assert 'symbol=MSFT' in url and 'limit=10' in url and 'page=0' in url


def test_attribution_does_not_grant_authority():
    result=assess_records([{'symbol':'MSFT','expertUID':'private','priceTarget':500}],symbol='MSFT')
    assert result['attributed_count']==1
    assert result['numeric_price_target_count']==1
    assert result['independent_origins_verified']==0
    assert result['operational_source_accepted'] is False
    assert 'private' not in str(result)


def test_cross_symbol_refused_for_use():
    result=assess_records([{'symbol':'AVGO','priceTarget':900}],symbol='MSFT')
    assert result['symbol_filter_respected'] is False
    assert result['nonmatching_symbol_count']==1


@pytest.mark.parametrize('bad',[None,{},[None],[1],['bad']])
def test_bad_payload_refused(bad):
    with pytest.raises(ValueError):
        assess_records(bad,symbol='MSFT')


def test_unsupported_symbol_refused():
    with pytest.raises(ValueError):
        candidate_url('SPY','secret')
