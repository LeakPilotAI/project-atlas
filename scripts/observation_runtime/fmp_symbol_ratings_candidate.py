"""Fail-closed assessment of FMP symbol-specific analyst rating records."""
from urllib.parse import urlencode

ENDPOINT = 'https://financialmodelingprep.com/stable/tipranks-search'


def candidate_url(symbol, key):
    if symbol not in ('MSFT','AVGO') or not isinstance(key,str) or not key.strip():
        raise ValueError('FMP_SYMBOL_OR_CREDENTIAL_REFUSED')
    return ENDPOINT+'?'+urlencode({'symbol':symbol,'limit':10,'page':0,'apikey':key})


def assess_records(payload, *, symbol):
    if symbol not in ('MSFT','AVGO') or not isinstance(payload,list) or len(payload)>500:
        raise ValueError('FMP_RATINGS_PAYLOAD_REFUSED')
    matches=0
    mismatches=0
    with_attribution=0
    with_target=0
    for row in payload:
        if not isinstance(row,dict):
            raise ValueError('FMP_RATINGS_ROW_REFUSED')
        if row.get('symbol')!=symbol:
            mismatches+=1
            continue
        matches+=1
        if any(isinstance(row.get(k),str) and row[k].strip() for k in ('analystName','analyst','expertUID')):
            with_attribution+=1
        if isinstance(row.get('priceTarget'),(int,float)) and not isinstance(row['priceTarget'],bool) and 0<row['priceTarget']<100000:
            with_target+=1
    return {'schema':'ATLAS_FMP_SYMBOL_RATINGS_CANDIDATE_V1','symbol':symbol,
            'record_count':len(payload),'matching_symbol_count':matches,
            'nonmatching_symbol_count':mismatches,'attributed_count':with_attribution,
            'numeric_price_target_count':with_target,
            'symbol_filter_respected':mismatches==0 and matches>0,
            'independent_origins_verified':0,'provider_rights_verified':False,
            'operational_source_accepted':False,'paper_fill_authorized':False,
            'live_order_authorized':False}
