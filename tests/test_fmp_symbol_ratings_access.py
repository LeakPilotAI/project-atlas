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
    assert result['reason']=='FMP_RESPONSE_TOO_LARGE'


from urllib.error import HTTPError, URLError
import pytest

@pytest.mark.parametrize('status,reason',[(401,'FMP_HTTP_401'),(403,'FMP_HTTP_403'),(404,'FMP_HTTP_404'),(429,'FMP_HTTP_429'),(418,'FMP_HTTP_418'),(402,'FMP_HTTP_402'),(410,'FMP_HTTP_410')])
def test_http_error_category_no_secret_leak(status,reason):
    def failed():
        raise HTTPError('https://redacted.invalid/?apikey=secret',status,'secret',None,None)
    result=probe(environ={'FMP_API_KEY':'redacted'},fetch=failed)
    assert result['reason']==reason
    assert 'secret' not in str(result)

def test_timeout_category():
    def failed():
        raise TimeoutError('private')
    assert probe(environ={'FMP_API_KEY':'redacted'},fetch=failed)['reason']=='FMP_TIMEOUT'

def test_network_category():
    def failed():
        raise URLError('private')
    assert probe(environ={'FMP_API_KEY':'redacted'},fetch=failed)['reason']=='FMP_NETWORK_OR_TLS_FAILURE'

def test_redirect_category():
    def failed():
        raise ValueError('FMP_REDIRECT_REFUSED')
    assert probe(environ={'FMP_API_KEY':'redacted'},fetch=failed)['reason']=='FMP_REDIRECT_REFUSED'

