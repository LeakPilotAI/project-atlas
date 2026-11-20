"""Review FMP target-news metadata without revealing prices, records, or API credentials."""
from __future__ import annotations
from collections import Counter
from datetime import datetime, timezone


def review_target_news(payload, *, symbol='MSFT'):
    if not isinstance(payload,list) or len(payload)>1000:
        raise ValueError('FMP_TARGET_NEWS_SHAPE_REFUSED')
    if not isinstance(symbol,str) or not symbol.isalpha() or not symbol.isupper():
        raise ValueError('FMP_TARGET_NEWS_SYMBOL_REFUSED')
    keys=Counter()
    source_labels=set()
    dated=0
    matching=0
    nonmatching=0
    missing_symbol=0
    for row in payload:
        if not isinstance(row,dict):
            raise ValueError('FMP_TARGET_NEWS_ROW_REFUSED')
        keys.update(k for k in row if isinstance(k,str) and len(k)<80)
        if row.get('symbol')!=symbol:
            if not isinstance(row.get('symbol'),str) or not row['symbol'].strip():
                missing_symbol+=1
            else:
                nonmatching+=1
            continue
        matching+=1
        if any(isinstance(row.get(k),str) and row[k].strip() for k in ('analystName','analyst','analystCompany','analystFirm','newsPublisher')):
            source_labels.add('HAS_ATTRIBUTION_FIELD')
        if any(isinstance(row.get(k),str) and row[k].strip() for k in ('publishedDate','date','updatedAt')):
            dated+=1
    return {'schema':'ATLAS_FMP_TARGET_NEWS_METADATA_REVIEW_V1','symbol':symbol,
            'record_count':len(payload),'matching_symbol_count':matching,
            'nonmatching_symbol_count':nonmatching,'missing_symbol_count':missing_symbol,
            'requested_symbol_filter_respected':matching>0 and nonmatching==0 and missing_symbol==0,
            'field_names':sorted(keys),'rows_with_date_field':dated,
            'attribution_field_present':bool(source_labels),
            'independent_originating_analysts_authenticated':0,
            'free_tier_entitlement_verified':False,
            'operational_source_accepted':False,'paper_fill_authorized':False,'live_order_authorized':False,
            'reason':'FMP_ORIGIN_INDEPENDENCE_AND_LICENSE_NOT_VERIFIED'}
