"""Read-only IEX observation roster planner for the selected r12 QD research universe.

Never opens Alpaca credentials/sockets, authorizes a trade, or starts a scanner.
A 30-symbol plan is NOT 30 fresh quotes, market coverage or a custody grant.
Keep explicitly supplied monitored symbols pinned; rotate other catalog assets.
"""
import argparse
import hashlib
import json
import math
import re
from pathlib import Path

ROOT=Path(r'D:\Work\Project Atlas')
CATALOG=ROOT/'logs/research/alpaca_equity_inventory.json'
MAX_SYMBOLS=30
MAX_PINNED=10
SYMBOL=re.compile(r'[A-Z][A-Z0-9.-]{0,14}\Z')


def catalog_symbols(snapshot):
    if (type(snapshot) is not dict
        or snapshot.get('schema')!='ATLAS_ALPACA_EQUITY_RESEARCH_INVENTORY_V1'
        or snapshot.get('source')!='ALPACA_US_EQUITY_ASSETS'
        or snapshot.get('paper_execution_authorized') is not False
        or snapshot.get('live_order_authorized') is not False
        or snapshot.get('robinhood_brokerage_verified') is not False):
        raise ValueError('QD_IEX_RESEARCH_CATALOG_SCOPE_REQUIRED')
    rows=snapshot.get('rows')
    if type(rows) is not list or not 0<len(rows)<=20000:
        raise ValueError('QD_IEX_RESEARCH_CATALOG_ROWS_REQUIRED')
    if any(type(r) is not dict
           or r.get('asset_class')!='us_equity'
           or r.get('provider_tradable') is not True
           or type(r.get('symbol')) is not str
           or SYMBOL.fullmatch(r['symbol']) is None
           for r in rows):
        raise ValueError('QD_IEX_RESEARCH_CATALOG_ASSET_INVALID')
    symbols=[r['symbol'] for r in rows]
    if symbols!=sorted(set(symbols)):
        raise ValueError('QD_IEX_RESEARCH_CATALOG_ORDER_OR_DUPLICATE')
    digest=hashlib.sha256(json.dumps(rows,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    if digest!=snapshot.get('sha256'):
        raise ValueError('QD_IEX_RESEARCH_CATALOG_DIGEST_CHANGED')
    return symbols


def plan(snapshot,*,offset=0,monitored_symbols=()):
    if type(offset) is not int or offset<0:
        raise ValueError('QD_IEX_OBSERVATION_CURSOR_INVALID')
    if type(monitored_symbols) not in (list,tuple):
        raise ValueError('QD_IEX_PINNED_POSITION_LIST_REQUIRED')
    pinned=list(monitored_symbols)
    if (len(pinned)>MAX_PINNED or len(pinned)!=len(set(pinned))
        or any(type(x) is not str or SYMBOL.fullmatch(x) is None for x in pinned)):
        raise ValueError('QD_IEX_PINNED_POSITION_SCOPE_INVALID')
    symbols=catalog_symbols(snapshot)
    if any(x not in symbols for x in pinned):
        raise ValueError('QD_IEX_PINNED_SYMBOL_NOT_IN_RESEARCH_UNIVERSE')
    # The planner is an admission-independent shortlist. It never claims that
    # monitored_symbols came from an accepted financial custody snapshot.
    pinned_set=set(pinned)
    available=[s for s in symbols if s not in pinned_set]
    capacity=MAX_SYMBOLS-len(pinned)
    start=offset%len(available) if available else 0
    # Do not wrap inside a roster: finish each catalog cycle without
    # repeating already visited symbols before beginning the next cycle.
    fresh=available[start:start+capacity]
    proposed=pinned+fresh
    if len(proposed)!=len(set(proposed)) or len(proposed)>MAX_SYMBOLS:
        raise ValueError('QD_IEX_ROSTER_OVER_CAPACITY_OR_DUPLICATE')
    return {
      'schema':'ATLAS_R12_IEX_RESEARCH_OBSERVATION_ROSTER_V1',
      'status':'OFFLINE_ROSTER_PLAN_NOT_A_PROVIDER_SUBSCRIPTION',
      'catalog_sha256':snapshot['sha256'],
      'catalog_count':len(symbols),
      'offset':offset,
      'next_offset':offset+len(fresh),
      'pinned_research_symbols':pinned,
      'rotating_research_symbols':fresh,
      'requested_symbols':proposed,
      'requested_symbol_count':len(proposed),
      'max_iex_websocket_symbols':MAX_SYMBOLS,
      'full_universe_one_connection_supported':False,
      'minimum_rosters_with_same_pinned_symbols':(
          math.ceil(len(available)/capacity) if available else 1),
      'monitored_symbols_independently_verified':False,
      'robinhood_brokerage_coverage_verified':False,
      'authenticated_iex_connection':False,
      'fresh_quote_delivery_verified':False,
      'provider_rights_accepted':False,
      'financial_paper_accounts_authorized':False,
      'paper_execution_authorized':False,
      'live_trading_authorized':False,
      'startup_authorized':False,
    }


def inspect(*,offset=0,monitored_symbols=(),catalog_path=CATALOG):
    path=Path(catalog_path)
    if not path.is_file() or path.is_symlink() or path.stat().st_size>5*1024*1024:
        raise ValueError('QD_IEX_RESEARCH_CATALOG_FILE_NOT_ACCEPTED')
    return plan(json.loads(path.read_text(encoding='utf-8')),
                offset=offset,monitored_symbols=monitored_symbols)


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--inspect',action='store_true',required=True)
    p.add_argument('--offset',type=int,default=0)
    p.add_argument('--monitor',action='append',default=[])
    a=p.parse_args(argv)
    print(json.dumps(inspect(offset=a.offset,monitored_symbols=a.monitor),sort_keys=True))
    return 2  # NO-GO: offline plans never claim authenticated market-data rights


if __name__=='__main__':
    raise SystemExit(main())
