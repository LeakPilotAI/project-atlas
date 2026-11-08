import json
from scripts.observation_runtime.fmp_target_entitlement_probe import probe

def test_no_key_never_calls_network():
    assert probe(environ={},fetch=lambda: (_ for _ in ()).throw(AssertionError()))['reason']=='FMP_CREDENTIAL_MISSING_OR_AMBIGUOUS'

def test_fake_access_never_grants_rights():
    result=probe(environ={'FMP_API_KEY':'secret'},fetch=lambda: json.dumps([{'symbol':'MSFT','priceTarget':500}]).encode())
    assert result['returned_record_count']==1
    assert result['free_tier_entitlement_verified'] is False
    assert result['operational_source_accepted'] is False
    assert 'secret' not in str(result)

def test_plan_refusal():
    result=probe(environ={'FMP_API_KEY':'secret'},fetch=lambda: b'{"Error Message":"upgrade"}')
    assert result['reason']=='FMP_ACCESS_OR_PLAN_REFUSED'

def test_invalid_json_refused():
    assert probe(environ={'FMP_API_KEY':'secret'},fetch=lambda: b'no')['reason']=='FMP_REQUEST_OR_RESPONSE_REFUSED'


def test_realistic_metadata_is_integrated_without_promoting_authority():
    sample=[{'symbol':'MSFT','analystName':'Analyst A','analystCompany':'Firm A',
             'publishedDate':'2026-11-07','priceTarget':500.0}]
    result=probe(environ={'FMP_API_KEY':'redacted'},fetch=lambda: json.dumps(sample).encode())
    assert result['metadata_review']['matching_symbol_count']==1
    assert result['metadata_review']['attribution_field_present'] is True
    assert result['metadata_review']['independent_originating_analysts_authenticated']==0
    assert result['free_tier_entitlement_verified'] is False
    assert result['operational_source_accepted'] is False
    assert 'Analyst A' not in str(result)

def test_invalid_rows_fail_closed():
    result=probe(environ={'FMP_API_KEY':'redacted'},fetch=lambda: b'[null]')
    assert result['reason']=='FMP_REQUEST_OR_RESPONSE_REFUSED'
    assert result['operational_source_accepted'] is False


def test_cross_symbol_feed_is_explicitly_rejected():
    sample=[{'symbol':'AVGO','analystName':'A','publishedDate':'2026-11-07'},
            {'symbol':'AAPL','analystName':'B','publishedDate':'2026-11-07'}]
    result=probe(environ={'FMP_API_KEY':'redacted'},fetch=lambda: json.dumps(sample).encode())
    assert result['reason']=='FMP_SYMBOL_FILTER_NOT_RESPECTED'
    assert result['metadata_review']['nonmatching_symbol_count']==2
    assert result['metadata_review']['matching_symbol_count']==0
    assert result['operational_source_accepted'] is False

def test_mixed_symbol_feed_is_explicitly_rejected():
    sample=[{'symbol':'MSFT'},{'symbol':'AAPL'}]
    result=probe(environ={'FMP_API_KEY':'redacted'},fetch=lambda: json.dumps(sample).encode())
    assert result['reason']=='FMP_SYMBOL_FILTER_NOT_RESPECTED'
    assert result['metadata_review']['matching_symbol_count']==1
    assert result['paper_fill_authorized'] is False
