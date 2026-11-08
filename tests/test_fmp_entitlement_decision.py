import pytest
from scripts.observation_runtime.fmp_entitlement_decision import classify_fmp_access


def test_http_402_blocks_repeated_free_endpoint_attempts():
    decision=classify_fmp_access('FMP_HTTP_402')
    assert decision['category']=='PAID_ENTITLEMENT_REQUIRED_OR_ACCOUNT_RESTRICTED'
    assert decision['repeat_same_endpoint_without_new_evidence'] is False
    assert decision['operational_source_accepted'] is False
    assert decision['paper_fill_authorized'] is False


def test_positive_http_response_still_requires_origin_and_rights():
    decision=classify_fmp_access('FMP_ORIGIN_AND_LICENSE_REVIEW_REQUIRED')
    assert decision['free_tier_analyst_access_verified'] is False


@pytest.mark.parametrize('reason',[None,1,'X'*81])
def test_bad_reason_refused(reason):
    with pytest.raises(ValueError):
        classify_fmp_access(reason)
