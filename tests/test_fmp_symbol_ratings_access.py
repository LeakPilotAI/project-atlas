import json
from scripts.observation_runtime.fmp_symbol_ratings_access import probe


def test_missing_credential():
    result=probe(environ={})
    assert result['reason']=='FMP_CREDENTIAL_MISSING_OR_AMBIGUOUS'
    assert result['paper_fill_authorized'] is False


def test_symbol_specific_response_remains_unapproved():
    payload=[{'symbol':'MSFT','analystName':'Private','priceTarget':450}]
    result=probe(environ={'FMP_API_KEY':'redacted'},fetch=lambda:json.dumps(payload).encode())
    assert result['authenticated_access_tested'] is True
    assert result['metadata_review']['matching_symbol_count']==1
    assert result['individual_origins_verified'] is False
    assert result['operational_source_accepted'] is False
    assert 'Private' not in str(result)


def test_mismatched_symbol_refused():
    result=probe(environ={'FMP_API_KEY':'redacted'},fetch=lambda:b'[{"symbol":"AVGO"}]')
    assert result['reason']=='FMP_SYMBOL_FILTER_OR_EMPTY_RESULT_REFUSED'


def test_provider_error_refused():
    result=probe(environ={'FMP_API_KEY':'redacted'},fetch=lambda:b'{"Error Message":"upgrade"}')
    assert result['reason']=='FMP_ACCESS_OR_PLAN_REFUSED'


def test_oversized_response_refused():
    result=probe(environ={'FMP_API_KEY':'redacted'},fetch=lambda:b' '*65537)
    assert result['reason']=='FMP_REQUEST_OR_RESPONSE_REFUSED'
