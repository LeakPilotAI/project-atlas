"""Bounded enrolled Alpaca IEX watermark is explicitly scoped and fail-closed."""
import json
import subprocess
import sys
from datetime import UTC,datetime,timedelta
from pathlib import Path

import pytest

import scripts.observation_runtime.alpaca_iex_watermarked_probe as probe
from scripts.observation_runtime.paper_readonly_watermark import advance_watermark,read_watermark

ROOT=Path(__file__).resolve().parents[1]
STAMP=datetime(2026,11,7,tzinfo=UTC)


def enrolled(tmp_path):
    path=tmp_path/'probe.json'
    advance_watermark(path,symbol='MSFT',provider_timestamp=(STAMP-timedelta(seconds=1)).isoformat())
    return path


def fake_feed(*,fresh=True,auth=True,subscribed=True,quote_count=1):
    class Feed:
        def __init__(self,symbols):
            assert symbols==['MSFT']
        async def run(self,creds,*,seconds,max_reconnects,on_fresh_quote):
            assert seconds==1 and max_reconnects==0
            if fresh:
                on_fresh_quote({'symbol':'MSFT','provider':'ALPACA_IEX',
                    'timestamp':STAMP.isoformat(),'bid':'100','ask':'100.1',
                    'bid_lots':1,'ask_lots':2,
                    'paper_fill_authorized':False,'live_order_authorized':False})
            return {'authenticated':auth,'subscribed':subscribed,
                'fresh_quote_observed_during_connection':fresh,
                'quote_count':quote_count,
                'result':{'connection':'DISCONNECTED'}}
    return Feed


def test_unscoped_function_never_acquires_watermark_or_reads_private_config(tmp_path,monkeypatch):
    path=enrolled(tmp_path)
    from scripts.observation_runtime import paper_readonly_watermark as watermark
    monkeypatch.setattr(watermark,'readonly_watermark_writer',lambda p:pytest.fail('watermark accessed'))
    monkeypatch.setattr(probe.Credentials,'load',lambda p:pytest.fail('KEYS READ'))
    with pytest.raises(ValueError,match='EXPLICIT_DATA_ONLY_SCOPE_REQUIRED'):
        probe.bounded_observation(symbol='MSFT',seconds=1,watermark=path,
            credentials_path=tmp_path/'fake',feed_factory=lambda s:pytest.fail('SOCKET'))
    assert read_watermark(path,symbol='MSFT')==(STAMP-timedelta(seconds=1)).isoformat()


def test_enrollment_absent_refuses_before_credentials_even_with_scope(tmp_path,monkeypatch):
    monkeypatch.setattr(probe.Credentials,'load',lambda p:pytest.fail('KEYS READ'))
    with pytest.raises(ValueError,match='PRIOR_STATE_REQUIRED'):
        probe.bounded_observation(symbol='MSFT',seconds=1,
            watermark=tmp_path/'missing.json',credentials_path=tmp_path/'private',
            confirm_scope=probe.SCOPE,feed_factory=lambda s:pytest.fail('SOCKET'))


@pytest.mark.parametrize('symbol,seconds',[
   ('msft',1),('MSFT;X',1),('MSFT',0),('MSFT',61),
   ('MSFT',True),('MSFT',1.2)
])
def test_invalid_arguments_refuse_prior_to_private_config(tmp_path,symbol,seconds,monkeypatch):
    monkeypatch.setattr(probe.Credentials,'load',lambda p:pytest.fail('KEYS READ'))
    with pytest.raises(ValueError,match='ARGUMENTS_REFUSED'):
        probe.bounded_observation(symbol=symbol,seconds=seconds,
          watermark=tmp_path/'missing',credentials_path=tmp_path/'missing',
          confirm_scope=probe.SCOPE)


def test_scoped_fresh_event_updates_replay_watermark_and_returns_only_data_scope(tmp_path,monkeypatch):
    path=enrolled(tmp_path)
    monkeypatch.setattr(probe.Credentials,'load',lambda p:object())
    result=probe.bounded_observation(symbol='MSFT',seconds=1,
        watermark=path,credentials_path=tmp_path/'fake',
        confirm_scope=probe.SCOPE,feed_factory=fake_feed())
    assert result['status']=='DATA_ONLY_WATERMARKED_FRESH_EVENT_NOT_FINANCIAL_AUTHORITY'
    assert result['accepted_events']==1
    assert result['authenticated'] is True and result['subscribed'] is True
    assert result['provider_rights_independently_accepted'] is False
    assert result['continuous_executable_prices_verified'] is False
    assert result['paper_fill_authorized'] is False
    assert read_watermark(path,symbol='MSFT')==STAMP.isoformat()
    with pytest.raises(ValueError,match='REPLAY_REFUSED'):
        probe.bounded_observation(symbol='MSFT',seconds=1,
            watermark=path,credentials_path=tmp_path/'fake',
            confirm_scope=probe.SCOPE,feed_factory=fake_feed())
    assert read_watermark(path,symbol='MSFT')==STAMP.isoformat()


@pytest.mark.parametrize('kwargs',[
    {'fresh':False}, {'quote_count':0}, {'auth':False,'fresh':False},
    {'subscribed':False,'fresh':False}
])
def test_no_fresh_quote_or_provider_ack_is_not_success(tmp_path,monkeypatch,kwargs):
    path=enrolled(tmp_path)
    initial=read_watermark(path,symbol='MSFT')
    monkeypatch.setattr(probe.Credentials,'load',lambda p:object())
    with pytest.raises(ValueError,match='NO_FRESH_AUTHENTICATED_QUOTE|PROVIDER_NOT_VERIFIED'):
        probe.bounded_observation(symbol='MSFT',seconds=1,
            watermark=path,credentials_path=tmp_path/'fake',
            confirm_scope=probe.SCOPE,feed_factory=fake_feed(**kwargs))
    # If a callback already arrived, the durable replay watermark MUST stay
    # advanced even when contradictory final transport accounting is refused;
    # rolling it back would permit the same event to be reprocessed.
    expected=STAMP.isoformat() if kwargs.get('fresh',True) else initial
    assert read_watermark(path,symbol='MSFT')==expected


def test_inspect_offline_never_reads_credentials_or_watermark(tmp_path,monkeypatch,capsys):
    monkeypatch.setattr(probe.Credentials,'load',lambda p:pytest.fail('KEYS READ'))
    assert probe.main(['--inspect'])==0
    row=json.loads(capsys.readouterr().out)
    assert row['credentials_accessed'] is False
    assert row['provider_connected'] is False
    assert row['paper_fill_authorized'] is False
    assert probe.main(['--inspect','--watermark',str(tmp_path/'any')])==1
    assert json.loads(capsys.readouterr().out)['status']=='REFUSED'


def test_cli_requires_data_only_scope_before_credentials(tmp_path,monkeypatch,capsys):
    path=enrolled(tmp_path)
    monkeypatch.setattr(probe.Credentials,'load',lambda p:pytest.fail('KEYS READ'))
    assert probe.main(['--execute-data-only','--watermark',str(path),'--seconds','1'])==1
    assert json.loads(capsys.readouterr().out)['status']=='REFUSED'
    assert probe.main(['--execute-data-only','--confirm-scope',probe.SCOPE,
                       '--seconds','1'])==1
    assert json.loads(capsys.readouterr().out)['status']=='REFUSED'


def test_actual_offline_cli_and_unscoped_legacy_cli_do_not_touch_provider():
    src=ROOT/'scripts/observation_runtime/alpaca_iex_watermarked_probe.py'
    for args,code in [(['--inspect'],0),(['--symbol','MSFT','--seconds','1'],2)]:
        p=subprocess.run([sys.executable,'-B',str(src),*args],
                         capture_output=True,text=True,cwd=ROOT,timeout=30)
        assert p.returncode==code,p.stderr
        if code==0:
            assert json.loads(p.stdout)['fresh_quote_verified'] is False
