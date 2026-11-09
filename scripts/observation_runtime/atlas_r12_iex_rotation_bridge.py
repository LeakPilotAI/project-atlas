"""Offline bridge: reviewed Alpaca research rotation plan -> existing IEXFeed roster.

Changes only the supplied in-memory feed's data-only subscription request.
DOES NOT connect a socket, read Alpaca credentials, create source publications,
mutate a research cursor, or grant financial PAPER/trading authority.
A separately accepted position owner is required for operational use.
"""
import argparse
import json
import sys
from pathlib import Path

ROOT=Path(r'D:\Work\Project Atlas')
sys.path.insert(0,str(ROOT/'backend'))
from app.investment.alpaca_iex import IEXFeed, IEXRefused
from scripts.observation_runtime.atlas_r12_iex_rotation_plan import inspect as inspect_plan
from scripts.observation_runtime.atlas_r12_iex_rotation_plan import plan as plan_roster

SCHEMA='ATLAS_R12_IEX_OFFLINE_FEED_ROSTER_HANDOFF_V1'


def apply_to_feed(*, feed, catalog, offset=0, monitored_symbols=None):
    """Never trust a caller's claimed position symbols over feed owner's reader.

    Feed must already be constructed with an independent position-symbol
    reader; do not install or replace one here. A changed owner rejects handoff.
    """
    if type(feed) is not IEXFeed or not callable(feed.position_symbols):
        raise IEXRefused('QD_IEX_ACCEPTED_POSITION_OWNER_READER_REQUIRED')
    pinned=feed.position_symbols()
    if (type(pinned) is not list or any(type(x) is not str for x in pinned)
        or type(monitored_symbols) not in (list,type(None))
        or monitored_symbols is not None and monitored_symbols!=pinned):
        raise IEXRefused('QD_IEX_POSITION_OWNER_SNAPSHOT_CHANGED')
    roster=plan_roster(catalog,offset=offset,monitored_symbols=pinned)
    requested=roster['requested_symbols']
    # An empty data-only research roster is never a subscription.
    if not requested or len(requested)>30:
        raise IEXRefused('QD_IEX_NO_BOUNDED_SYMBOL_ROSTER')
    if feed.position_symbols()!=pinned:
        raise IEXRefused('QD_IEX_POSITION_OWNER_SNAPSHOT_CHANGED')
    request={'schema':'QD_IEX_ROSTER_V1','symbols':requested,
             'required_symbols':pinned,'capacity':30}
    feed.request_roster(request)
    if feed.position_symbols()!=pinned:
        feed.disconnect('IEX_POSITION_OWNER_CHANGED_AFTER_ROTATION')
        raise IEXRefused('QD_IEX_POSITION_OWNER_SNAPSHOT_CHANGED')
    view=feed.snapshot()
    if (tuple(feed.symbols)!=tuple(requested)
        or view.get('connection')!='DISCONNECTED'
        or view.get('authenticated') is not False
        or view.get('subscribed') is not False
        or view.get('paper_startup_authorized') is not False
        or any(x.get('state')=='FRESH' for x in view.get('quotes',[]))):
        feed.disconnect('IEX_ROSTER_HANDOFF_NOT_ISOLATED')
        raise IEXRefused('QD_IEX_ROSTER_REQUIRES_NEW_AUTH_AND_ACK')
    return {'schema':SCHEMA,
       'status':'OFFLINE_DATA_ONLY_ROSTER_HANDOFF_NOT_CONNECTED',
       'catalog_sha256':roster['catalog_sha256'],
       'catalog_count':roster['catalog_count'],
       'pinned_research_symbols':pinned,
       'rotating_research_symbols':roster['rotating_research_symbols'],
       'requested_symbols':requested,
       'requested_symbol_count':len(requested),
       'offset':roster['offset'],'next_offset':roster['next_offset'],
       'feed_roster_revision':feed.roster_revision,
       'feed_disconnected':True,'prior_quote_cache_not_fresh':True,
       'position_owner_independently_accepted':False,
       'provider_connection_started':False,
       'authenticated':False,'subscription_acknowledged':False,
       'fresh_quote_verified':False,
       'market_data_entitlement_accepted':False,
       'native_forward_publication_created':False,
       'research_cursor_written':False,
       'paper_accounts_authorized':False,
       'paper_execution_authorized':False,
       'live_trading_authorized':False,
       'startup_authorized':False}


def inspect(*,offset=0,monitored_symbols=()):
    # This CLI intentionally uses a local synthetic owner and NO provider.
    # The real user-owned position reader must be separately commissioned.
    if type(monitored_symbols) not in (tuple,list):
        raise IEXRefused('QD_IEX_OFFLINE_INSPECTION_SCOPE_REQUIRED')
    proposed=inspect_plan(offset=offset,monitored_symbols=monitored_symbols)
    local_pins=list(monitored_symbols)
    # start from same roster: no live socket or account identity.
    feed=IEXFeed(proposed['requested_symbols'],
                 position_symbols=lambda: list(local_pins))
    source=json.loads((ROOT/'logs/research/alpaca_equity_inventory.json').read_text(encoding='utf-8'))
    return apply_to_feed(feed=feed,catalog=source,offset=offset,
                         monitored_symbols=local_pins)


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--inspect',action='store_true',required=True)
    p.add_argument('--offset',type=int,default=0)
    p.add_argument('--monitor',action='append',default=[])
    a=p.parse_args(argv)
    print(json.dumps(inspect(offset=a.offset,monitored_symbols=a.monitor),
                     sort_keys=True))
    return 2  # no financial PAPER admission is possible from offline feed state


if __name__=='__main__':
    raise SystemExit(main())
