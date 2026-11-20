"""Research-only Alpaca IEX rotation plans: no sockets, authority, or trading."""
import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.observation_runtime import atlas_r12_iex_rotation_plan as roster
from scripts.observation_runtime.alpaca_equity_catalog import inventory_snapshot


def sample(count=67):
    return inventory_snapshot([
      {'class':'us_equity','symbol':f'S{i:03d}','status':'active',
       'tradable':True,'exchange':'NASDAQ','id':str(i)}
      for i in range(count)],captured_at='2026-11-09T11:00:00+00:00')


def test_actual_inventory_cannot_mint_live_iex_or_paper_authority():
    value=roster.inspect()
    assert value['catalog_count']==13487
    assert value['requested_symbol_count']==30
    assert len(value['requested_symbols'])==len(set(value['requested_symbols']))==30
    assert value['minimum_rosters_with_same_pinned_symbols']==450
    assert value['next_offset']==30
    assert value['full_universe_one_connection_supported'] is False
    assert value['authenticated_iex_connection'] is False
    assert value['fresh_quote_delivery_verified'] is False
    assert value['robinhood_brokerage_coverage_verified'] is False
    assert value['financial_paper_accounts_authorized'] is False
    assert value['paper_execution_authorized'] is False
    assert value['startup_authorized'] is False


def test_full_cycle_no_duplicate_symbols_between_rosters():
    source=sample()
    seen=[]
    offset=0
    for size in (30,30,7):
        item=roster.plan(source,offset=offset)
        assert item['requested_symbol_count']==size
        seen+=item['rotating_research_symbols']
        offset=item['next_offset']
    assert len(seen)==len(set(seen))==67
    assert seen==[r['symbol'] for r in source['rows']]
    assert offset==67
    assert roster.plan(source,offset=offset)['requested_symbols'][:4]==seen[:4]


def test_monitored_research_symbols_are_reserved_in_each_rotation():
    source=sample()
    seen=[];cursor=0
    for _ in range(3):
        p=roster.plan(source,offset=cursor,monitored_symbols=['S000','S004'])
        assert p['pinned_research_symbols']==['S000','S004']
        assert p['requested_symbols'][:2]==['S000','S004']
        assert p['requested_symbol_count']<=30
        assert len(p['requested_symbols'])==len(set(p['requested_symbols']))
        seen+=p['rotating_research_symbols']
        cursor=p['next_offset']
    assert len(seen)==65 and len(set(seen))==65
    assert 'S000' not in seen and 'S004' not in seen
    assert set(seen)=={r['symbol'] for r in source['rows']}-{'S000','S004'}
    assert cursor==65
    assert p['monitored_symbols_independently_verified'] is False
    assert p['fresh_quote_delivery_verified'] is False


@pytest.mark.parametrize('pin',[('UNKNOWN',),('S000','S000'),tuple(f'S{i:03d}' for i in range(11)),('',),('s000',)])
def test_unknown_duplicate_or_excess_pinned_symbols_refuse(pin):
    with pytest.raises(ValueError,match='QD_IEX_PINNED_'):
        roster.plan(sample(),monitored_symbols=pin)


@pytest.mark.parametrize('offset',[-1,True,1.5,'2'])
def test_invalid_or_ambiguous_cursor_is_rejected(offset):
    with pytest.raises(ValueError,match='CURSOR_INVALID'):
        roster.plan(sample(),offset=offset)


@pytest.mark.parametrize('field,value',[
    ('paper_execution_authorized',True),('live_order_authorized',True),
    ('robinhood_brokerage_verified',True),('source','ROBINHOOD_BROKERAGE'),
    ('schema','ATLAS_LIVE_ACCOUNT_V1')])
def test_research_inventory_scope_refuses_broadened_authority(field,value):
    catalog=sample();catalog[field]=value
    with pytest.raises(ValueError,match='QD_IEX_RESEARCH_CATALOG_SCOPE_REQUIRED'):
        roster.plan(catalog)


def test_tampered_digest_and_duplicate_rows_refuse():
    catalog=sample()
    catalog['rows'][0]['symbol']='OVERRIDE'
    with pytest.raises(ValueError,match='CATALOG_ORDER_OR_DUPLICATE|CATALOG_DIGEST_CHANGED'):
        roster.plan(catalog)
    catalog=sample()
    catalog['rows'][1]['symbol']=catalog['rows'][0]['symbol']
    with pytest.raises(ValueError,match='CATALOG_ORDER_OR_DUPLICATE'):
        roster.plan(catalog)


def test_roster_plan_no_provider_access_in_cli():
    p=subprocess.run([sys.executable,'-B','-m',
       'scripts.observation_runtime.atlas_r12_iex_rotation_plan',
       '--inspect','--monitor','MSFT','--offset','100'],
       cwd=roster.ROOT,capture_output=True,text=True,timeout=45)
    assert p.returncode==2,p.stderr
    data=json.loads(p.stdout)
    assert data['requested_symbols'][0]=='MSFT'
    assert data['catalog_count']==13487
    assert data['max_iex_websocket_symbols']==30
    assert data['status']=='OFFLINE_ROSTER_PLAN_NOT_A_PROVIDER_SUBSCRIPTION'
    assert data['paper_execution_authorized'] is False
    assert data['authenticated_iex_connection'] is False
