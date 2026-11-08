from scripts.observation_runtime.fmp_target_news_review import review_target_news
import pytest


def test_metadata_review_does_not_promote_attributed_record():
    result=review_target_news([{'symbol':'MSFT','analystName':'private-name','date':'2026-11-07','priceTarget':500}])
    assert result['matching_symbol_count']==1
    assert result['attribution_field_present'] is True
    assert result['independent_originating_analysts_authenticated']==0
    assert result['paper_fill_authorized'] is False
    assert 'private-name' not in str(result)


def test_mixed_symbols_do_not_count_as_matching():
    result=review_target_news([{'symbol':'AVGO','date':'2026-11-07'}])
    assert result['matching_symbol_count']==0
    assert result['rows_with_date_field']==0


@pytest.mark.parametrize('bad', [None, {}, [None], [1], ['record']])
def test_bad_payload_refused(bad):
    with pytest.raises(ValueError):
        review_target_news(bad)
