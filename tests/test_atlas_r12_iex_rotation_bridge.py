"""Real in-memory IEXFeed roster handoff using catalog plans, zero provider sockets."""
import json
import subprocess
import sys
from datetime import datetime,timezone

import pytest
from app.investment.alpaca_iex import IEXFeed,IEXRefused
from scripts.observation_runtime import atlas_r12_iex_rotation_bridge as bridge
from scripts.observation_runtime.atlas_r12_iex_rotation_plan import plan as plan_roster
from scripts.observation_runtime.alpaca_equity_catalog import inventory_snapshot


def source(n=67):
    return inventory_snapshot([{'class':'us_equity','symbol':f'S{i:03d}',
                                'status':'active','tradable':True,
                                'exchange':'NASDAQ','id':str(i)}
                                for i in range(n)],
                               captured_at='2026-11-09T15:00:00+00:00')


def test_actual_13487_research_catalog_offline_bridge_no_credentials_or_socket():
    value=bridge.inspect(monitored_symbols=('MSFT',),offset=100)
    assert value['status']=='OFFLINE_DATA_ONLY_ROSTER_HANDOFF_NOT_CONNECTED'
    assert value['catalog_count']==13487
    assert value['requested_symbol_count']==30
    assert value['requested_symbols'][0]=='MSFT'
    assert len(value['rotating_research_symbols'])==29
    assert value['provider_connection_started'] is False
    assert value['authenticated'] is False
    assert value['subscription_acknowledged'] is False
    assert value['fresh_quote_verified'] is False
    assert value['position_owner_independently_accepted'] is False
    assert value['native_forward_publication_created'] is False
    assert value['research_cursor_written'] is False
    assert value['paper_accounts_authorized'] is False
    assert value['startup_authorized'] is False


def test_actual_iexfeed_rotation_clears_existing_fresh_quote_and_requires_new_ack():
    rows=source()
    pins=['S000']
    fakeclock=[datetime(2026,11,9,15,0,0,tzinfo=timezone.utc).timestamp()+0.5]
    feed=IEXFeed(['S000'],clock=lambda:fakeclock[0],
                 position_symbols=lambda:list(pins))
    p1=bridge.apply_to_feed(feed=feed,catalog=rows,offset=0,monitored_symbols=pins)
    assert p1['requested_symbol_count']==30
    old=p1['requested_symbols']
    feed.receive('[{"T":"success","msg":"authenticated"}]')
    feed.receive(json.dumps([{'T':'subscription','quotes':old}]))
    feed.receive(json.dumps([{'T':'q','S':'S000','bp':100,'ap':101,
                       'bs':2,'as':1,'bx':'V','ax':'V','c':['R'],'z':'C',
                       't':'2026-11-09T15:00:00Z'}]))
    assert feed.snapshot()['quotes'][0]['state']=='FRESH'
    p2=bridge.apply_to_feed(feed=feed,catalog=rows,
                              offset=p1['next_offset'],monitored_symbols=pins)
    assert p2['requested_symbols'][0]=='S000'
    assert p2['requested_symbols']!=old
    assert p2['feed_roster_revision']==p1['feed_roster_revision']+1
    assert feed.connection=='DISCONNECTED'
    assert feed.authenticated is False and feed.subscribed is False
    assert not feed.quotes
    assert not any(x['state']=='FRESH' for x in feed.snapshot()['quotes'])
    assert p2['prior_quote_cache_not_fresh'] is True
    assert p2['fresh_quote_verified'] is False
    assert p2['paper_execution_authorized'] is False


def test_all_three_rosters_complete_catalog_without_duplicate_coverage():
    rows=source()
    pins=['S000','S004']
    feed=IEXFeed(['S000'],position_symbols=lambda:list(pins))
    visited=[];cursor=0
    for count in (28,28,9):
        result=bridge.apply_to_feed(feed=feed,catalog=rows,offset=cursor,
                                   monitored_symbols=pins)
        assert len(result['rotating_research_symbols'])==count
        assert result['requested_symbols'][:2]==pins
        assert result['requested_symbol_count']<=30
        visited+=result['rotating_research_symbols']
        cursor=result['next_offset']
    assert cursor==65
    assert len(visited)==len(set(visited))==65
    assert set(visited)=={r['symbol'] for r in rows['rows']}-set(pins)
    assert feed.connection=='DISCONNECTED'
    assert feed.snapshot()['paper_startup_authorized'] is False


def test_forged_pin_input_refused_before_feed_rotation():
    rows=source()
    pins=['S000']
    feed=IEXFeed(['S000'],position_symbols=lambda:list(pins))
    with pytest.raises(IEXRefused,match='QD_IEX_POSITION_OWNER_SNAPSHOT_CHANGED'):
        bridge.apply_to_feed(feed=feed,catalog=rows,monitored_symbols=['S001'])
    assert feed.roster_revision==0 and feed.symbols==('S000',)


def test_missing_independent_position_reader_refuses_even_for_small_roster():
    rows=source()
    feed=IEXFeed(['S000'])
    with pytest.raises(IEXRefused,match='QD_IEX_ACCEPTED_POSITION_OWNER_READER_REQUIRED'):
        bridge.apply_to_feed(feed=feed,catalog=rows,offset=0)


def test_owner_changes_between_readback_and_handoff_refused():
    rows=source()
    calls=[0]
    def owned():
        calls[0]+=1
        return ['S000'] if calls[0]==1 else ['S001']
    feed=IEXFeed(['S000'],position_symbols=owned)
    with pytest.raises(IEXRefused,match='QD_IEX_POSITION_OWNER_SNAPSHOT_CHANGED'):
        bridge.apply_to_feed(feed=feed,catalog=rows,offset=0)
    assert feed.symbols==('S000',)
    assert feed.roster_revision==0


def test_owner_changes_after_hand_off_refuses_and_disables_cache():
    rows=source()
    calls=[0]
    def owned():
        calls[0]+=1
        return ['S000'] if calls[0]<4 else ['S001']
    feed=IEXFeed(['S000'],position_symbols=owned)
    with pytest.raises(IEXRefused,match='QD_IEX_POSITION_OWNER_SNAPSHOT_CHANGED'):
        bridge.apply_to_feed(feed=feed,catalog=rows,offset=0)
    assert feed.connection=='DISCONNECTED'
    assert feed.authenticated is False
    assert feed.snapshot()['paper_startup_authorized'] is False


@pytest.mark.parametrize('field,value',[
    ('paper_execution_authorized',True),
    ('live_order_authorized',True),
    ('robinhood_brokerage_verified',True),
    ('source','ALPACA_TRADING'),
])
def test_broadened_source_authority_never_reaches_feed(field,value):
    rows=source();rows[field]=value
    pins=['S000']
    feed=IEXFeed(['S000'],position_symbols=lambda:list(pins))
    with pytest.raises(ValueError,match='QD_IEX_RESEARCH_CATALOG_SCOPE_REQUIRED'):
        bridge.apply_to_feed(feed=feed,catalog=rows,offset=0)
    assert feed.roster_revision==0


def test_actual_cli_offline_bridge_is_no_go():
    proc=subprocess.run([sys.executable,'-B','-m',
         'scripts.observation_runtime.atlas_r12_iex_rotation_bridge',
         '--inspect','--monitor','MSFT','--offset','100'],
         cwd=bridge.ROOT,text=True,capture_output=True,timeout=45)
    assert proc.returncode==2,proc.stderr
    row=json.loads(proc.stdout)
    assert row['catalog_count']==13487
    assert row['requested_symbol_count']==30
    assert row['requested_symbols'][0]=='MSFT'
    assert row['paper_execution_authorized'] is False
    assert row['provider_connection_started'] is False


@pytest.mark.asyncio
async def test_active_feed_rotation_rate_limit_preserves_existing_roster():
    rows=source()
    now=[1000.0]
    pins=['S000']
    feed=IEXFeed(['S000'],clock=lambda:now[0],position_symbols=lambda:list(pins))
    await feed.run_lock.acquire()  # synthetic occupied session, NO socket
    try:
        first=bridge.apply_to_feed(feed=feed,catalog=rows,offset=0,
                                  monitored_symbols=pins)
        original=tuple(feed.symbols)
        rev=feed.roster_revision
        with pytest.raises(IEXRefused,match='IEX_ROTATION_RATE_LIMIT'):
            bridge.apply_to_feed(feed=feed,catalog=rows,
                                 offset=first['next_offset'],monitored_symbols=pins)
        assert feed.symbols==original
        assert feed.roster_revision==rev
        now[0]+=31.0
        second=bridge.apply_to_feed(feed=feed,catalog=rows,
                                    offset=first['next_offset'],monitored_symbols=pins)
        assert second['feed_roster_revision']==rev+1
        assert tuple(second['requested_symbols'])==feed.symbols
        assert second['fresh_quote_verified'] is False
        assert feed.connection=='DISCONNECTED'
    finally:
        feed.run_lock.release()
