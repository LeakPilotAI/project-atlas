"""Bounded FMP analyst-target entitlement probe; never promotes market authority."""
import json
import os
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, build_opener, HTTPRedirectHandler
from scripts.observation_runtime.fmp_candidate_access import KEY_NAMES

class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise ValueError('FMP_REDIRECT_REFUSED')


def probe(*, environ=None, fetch=None):
    env = os.environ if environ is None else environ
    keys = [env[name].strip() for name in KEY_NAMES if isinstance(env.get(name), str) and env[name].strip()]
    result = {'schema':'ATLAS_FMP_TARGET_ENTITLEMENT_PROBE_V1',
              'credential_configured':bool(keys), 'authenticated_access_tested':False,
              'free_tier_entitlement_verified':False, 'individual_analyst_records_verified':False,
              'operational_source_accepted':False, 'paper_fill_authorized':False,
              'live_order_authorized':False, 'reason':'FMP_CREDENTIAL_MISSING'}
    if len(keys)!=1:
        result['reason']='FMP_CREDENTIAL_MISSING_OR_AMBIGUOUS'
        return result
    # Endpoint is fixed; never accept an arbitrary URL from a caller.
    url='https://financialmodelingprep.com/stable/price-target-latest-news?'+urlencode({'symbol':'MSFT','apikey':keys[0]})
    def network():
        with build_opener(_NoRedirect()).open(Request(url,headers={'Accept':'application/json','User-Agent':'ProjectAtlas-Research/1.0'},method='GET'),timeout=8) as response:
            if response.status!=200: raise ValueError('FMP_HTTP_REFUSED')
            body=response.read(65537)
            if len(body)>65536: raise ValueError('FMP_RESPONSE_TOO_LARGE')
            return body
    try:
        body=(network if fetch is None else fetch)()
        payload=json.loads(body,parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
        result['authenticated_access_tested']=True
        result['reason']='FMP_RESPONSE_REQUIRES_ORIGIN_AND_LICENSE_REVIEW'
        if isinstance(payload,dict) and ('Error Message' in payload or 'error' in payload or 'message' in payload):
            result['reason']='FMP_ACCESS_OR_PLAN_REFUSED'
        elif not isinstance(payload,list):
            result['reason']='FMP_UNEXPECTED_RESPONSE'
        else:
            result['returned_record_count']=min(len(payload),1000)
    except (HTTPError,URLError,TimeoutError,OSError,ValueError,TypeError,UnicodeError):
        result['reason']='FMP_REQUEST_OR_RESPONSE_REFUSED'
    return result

if __name__=='__main__':
    print(json.dumps(probe(),sort_keys=True))
