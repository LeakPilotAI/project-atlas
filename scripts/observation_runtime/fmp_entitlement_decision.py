"""Fail-closed classification of provider entitlement evidence for Atlas research."""


def classify_fmp_access(reason):
    if not isinstance(reason,str) or len(reason)>80:
        raise ValueError('FMP_ACCESS_REASON_REFUSED')
    if reason=='FMP_HTTP_402':
        category='PAID_ENTITLEMENT_REQUIRED_OR_ACCOUNT_RESTRICTED'
        retry_same_endpoint=False
    elif reason in ('FMP_HTTP_429','FMP_TIMEOUT','FMP_NETWORK_OR_TLS_FAILURE'):
        category='TRANSIENT_ACCESS_FAILURE'
        retry_same_endpoint=False
    elif reason=='FMP_ORIGIN_AND_LICENSE_REVIEW_REQUIRED':
        category='PROVENANCE_AND_LICENSE_REVIEW_REQUIRED'
        retry_same_endpoint=False
    else:
        category='UNRESOLVED_PROVIDER_ACCESS'
        retry_same_endpoint=False
    return {'schema':'ATLAS_FMP_ENTITLEMENT_DECISION_V1','category':category,
            'repeat_same_endpoint_without_new_evidence':retry_same_endpoint,
            'free_tier_analyst_access_verified':False,
            'operational_source_accepted':False,
            'paper_fill_authorized':False,'live_order_authorized':False}
