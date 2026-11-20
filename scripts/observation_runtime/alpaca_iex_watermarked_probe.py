"""Bounded enrolled IEX watermark observation; never a PAPER order or service.

Explicit data-only scope is REQUIRED before watermark, credentials or socket.
A successful exit needs auth+subscription, fresh callbacks, and disconnect.
A watermark is only replay suppression, not provider or financial authority.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

REPO=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(REPO))
sys.path.insert(0,str(REPO/'backend'))

from app.investment.alpaca_iex import Credentials,IEXFeed,IEXRefused
from scripts.observation_runtime.paper_readonly_watermark import ReadonlyIEXEventConsumer

SCOPE='ALPACA_IEX_QUOTE_OBSERVATION_ONLY_NO_TRADING'
REASON='PROBE_GATE_OR_PROVIDER_UNAVAILABLE'


def bounded_observation(*,symbol:str,seconds:int,watermark:Path,
                        credentials_path:Path,confirm_scope=None,
                        feed_factory=IEXFeed):
    # ALL scope checks precede disk watermark acquisition, credentials and
    # provider access. No ordinary CLI/dev prompt grants credential access.
    if confirm_scope!=SCOPE:
        raise ValueError('IEX_WATERMARKED_EXPLICIT_DATA_ONLY_SCOPE_REQUIRED')
    if (type(symbol) is not str or not symbol.isascii() or not symbol.isalpha()
            or not symbol.isupper() or not 1<=len(symbol)<=8
            or type(seconds) is not int or not 1<=seconds<=60
            or not isinstance(watermark,Path)
            or not isinstance(credentials_path,Path)):
        raise ValueError('IEX_WATERMARKED_PROBE_ARGUMENTS_REFUSED')
    with ReadonlyIEXEventConsumer(path=watermark,symbol=symbol) as consumer:
        # The durable enrolled event lease must precede any private I/O.
        credentials=Credentials.load(credentials_path)
        result=asyncio.run(feed_factory([symbol]).run(
            credentials,seconds=seconds,max_reconnects=0,
            on_fresh_quote=consumer.on_fresh_quote))
        if (type(result) is not dict or result.get('authenticated') is not True
                or result.get('subscribed') is not True
                or type(result.get('result')) is not dict
                or result['result'].get('connection')!='DISCONNECTED'):
            raise IEXRefused('IEX_WATERMARKED_PROBE_PROVIDER_NOT_VERIFIED')
        if (type(result.get('quote_count')) is not int
                or result['quote_count']<=0 or
                result.get('fresh_quote_observed_during_connection') is not True
                or type(consumer.accepted) is not int or consumer.accepted<=0
                or consumer.accepted>result['quote_count']):
            raise IEXRefused('IEX_WATERMARKED_PROBE_NO_FRESH_AUTHENTICATED_QUOTE')
        return {'schema':'ATLAS_IEX_WATERMARKED_READONLY_PROBE_V1',
                'status':'DATA_ONLY_WATERMARKED_FRESH_EVENT_NOT_FINANCIAL_AUTHORITY',
                'authenticated':True,'subscribed':True,
                'connection_closed':True,'accepted_events':consumer.accepted,
                'single_exchange_not_nbbo':True,
                'continuous_executable_prices_verified':False,
                'provider_rights_independently_accepted':False,
                'paper_fill_authorized':False,'live_order_authorized':False}


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    mode=p.add_mutually_exclusive_group(required=True)
    mode.add_argument('--inspect',action='store_true')
    mode.add_argument('--execute-data-only',action='store_true')
    p.add_argument('--confirm-scope',default=None)
    p.add_argument('--symbol',default='MSFT')
    p.add_argument('--seconds',type=int,default=10)
    p.add_argument('--watermark',type=Path,default=None)
    a=p.parse_args(argv)
    if a.inspect:
        if a.confirm_scope is not None or a.watermark is not None:
            print(json.dumps({'status':'REFUSED','reason':REASON}))
            return 1
        print(json.dumps({'schema':'ATLAS_IEX_WATERMARKED_READONLY_PREFLIGHT_V1',
              'status':'REQUIRES_EXPLICIT_DATA_ONLY_SCOPE_AND_PRIOR_ENROLLMENT',
              'credentials_accessed':False,'provider_connected':False,
              'fresh_quote_verified':False,'paper_fill_authorized':False,
              'live_order_authorized':False},sort_keys=True))
        return 0
    try:
        if a.watermark is None:
            raise ValueError('IEX_WATERMARKED_PRIOR_ENROLLMENT_PATH_REQUIRED')
        result=bounded_observation(symbol=a.symbol,seconds=a.seconds,
                  watermark=a.watermark,credentials_path=REPO/'config/alpaca.env',
                  confirm_scope=a.confirm_scope)
        print(json.dumps(result,sort_keys=True))
        return 0
    except (ValueError,IEXRefused,OSError,TimeoutError):
        # Provider errors, headers, secrets and raw quotes are never printed.
        print(json.dumps({'schema':'ATLAS_IEX_WATERMARKED_READONLY_PROBE_V1',
              'status':'REFUSED','reason':REASON,'paper_fill_authorized':False,
              'live_order_authorized':False},sort_keys=True))
        return 1


if __name__=='__main__':
    raise SystemExit(main())
