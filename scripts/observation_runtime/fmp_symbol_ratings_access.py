"""Bounded read-only FMP symbol ratings access probe; no trading authority."""
import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener, HTTPRedirectHandler
from scripts.observation_runtime.fmp_candidate_access import KEY_NAMES
from scripts.observation_runtime.fmp_symbol_ratings_candidate import candidate_url, assess_records

class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise ValueError('FMP_REDIRECT_REFUSED')


def probe(*, environ=None, fetch=None, symbol='MSFT'):
    env=os.environ if environ is None else environ
    keys=[env[n].strip() for n in KEY_NAMES if isinstance(env.get(n),str) and env[n].strip()]
    result={'schema':'ATLAS_FMP_SYMBOL_RATINGS_ACCESS_V1','symbol':symbol,
            'credential_configured':bool(keys),'authenticated_access_tested':False,
            'free_tier_entitlement_verified':False,'individual_origins_verified':False,
            'operational_source_accepted':False,'paper_fill_authorized':False,
            'live_order_authorized':False,'reason':'FMP_CREDENTIAL_MISSING_OR_AMBIGUOUS'}
    if len(keys)!=1:
        return result
    try:
        url=candidate_url(symbol,keys[0])
        def network():
            with build_opener(_NoRedirect()).open(Request(url,headers={'Accept':'application/json','User-Agent':'ProjectAtlas-Research/1.0'},method='GET'),timeout=8) as response:
                if response.status!=200:
                    raise ValueError('FMP_HTTP_REFUSED')
                body=response.read(65537)
                if len(body)>65536:
                    raise ValueError('FMP_RESPONSE_TOO_LARGE')
                return body
        body=(network if fetch is None else fetch)()
        if len(body)>65536:
            raise ValueError('FMP_RESPONSE_TOO_LARGE')
        payload=json.loads(body,parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
        result['authenticated_access_tested']=True
        if isinstance(payload,dict):
            result['reason']='FMP_ACCESS_OR_PLAN_REFUSED'
        else:
            result['metadata_review']=assess_records(payload,symbol=symbol)
            result['reason']=('FMP_ORIGIN_AND_LICENSE_REVIEW_REQUIRED' if result['metadata_review']['symbol_filter_respected'] else 'FMP_SYMBOL_FILTER_OR_EMPTY_RESULT_REFUSED')
    except HTTPError as exc:
        status=exc.code
        result['reason']=('FMP_HTTP_'+str(status) if isinstance(status,int) and 100<=status<=599 else 'FMP_HTTP_INVALID_STATUS')
    except TimeoutError:
        result['reason']='FMP_TIMEOUT'
    except URLError:
        result['reason']='FMP_NETWORK_OR_TLS_FAILURE'
    except (OSError,ValueError,TypeError,UnicodeError) as exc:
        if isinstance(exc,ValueError) and str(exc)=='FMP_REDIRECT_REFUSED':
            result['reason']='FMP_REDIRECT_REFUSED'
        elif isinstance(exc,ValueError) and str(exc)=='FMP_RESPONSE_TOO_LARGE':
            result['reason']='FMP_RESPONSE_TOO_LARGE'
        else:
            result['reason']='FMP_REQUEST_OR_RESPONSE_REFUSED'
    return result

if __name__=='__main__':
    print(json.dumps(probe(),sort_keys=True))
