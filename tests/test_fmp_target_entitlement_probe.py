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
