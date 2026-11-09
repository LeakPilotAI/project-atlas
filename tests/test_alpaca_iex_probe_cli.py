"""Bounded Alpaca IEX CLI: real false-positive fix and synthetic provider tests only."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.observation_runtime import alpaca_iex_probe as probe
from app.investment.alpaca_iex import Credentials, IEXRefused

ROOT=Path(__file__).resolve().parents[1]
SCRIPT=ROOT/'scripts/observation_runtime/alpaca_iex_probe.py'


def run_cli(*args):
    return subprocess.run([sys.executable,str(SCRIPT),*args],
       cwd=ROOT,capture_output=True,text=True,timeout=60)


def test_probe_cli_rejects_invalid_duration_without_connecting():
    p=run_cli('--execute-data-only','--confirm-scope',probe.SCOPE,
              '--seconds','0')
    assert p.returncode==1
    assert json.loads(p.stdout)=={'status':'REFUSED','reason':probe.REASON}


def test_probe_cli_rejects_duplicate_symbols_without_connecting():
    p=run_cli('--execute-data-only','--confirm-scope',probe.SCOPE,
              '--seconds','1','--symbols','MSFT','MSFT')
    assert p.returncode==1
    assert json.loads(p.stdout)['status']=='REFUSED'


def test_missing_explicit_authorization_never_reads_keys_or_connects():
    calls=[]
    def forbidden_loader(path):
        calls.append('KEYS_OPENED')
        raise AssertionError('credentials must never load without exact scope')
    result=probe.main(['--execute-data-only','--seconds','1'],
                      credentials_loader=forbidden_loader,
                      feed_factory=lambda symbols: pytest.fail('network attempted'))
    assert result==1 and calls==[]
    assert probe.SCOPE=='ALPACA_IEX_QUOTE_OBSERVATION_ONLY_NO_TRADING'


def test_old_unscoped_cli_is_not_an_implicit_provider_grant():
    result=run_cli('--seconds','1','--symbols','MSFT')
    assert result.returncode!=0
    assert 'Traceback' not in result.stderr


def test_data_only_offline_inspect_avoids_private_config(monkeypatch,capsys):
    from scripts.observation_runtime import atlas_r12_alpaca_source_admission as source
    monkeypatch.setattr(source,'assess',lambda:{'native_revision':12,
        'catalog':{'research_symbol_count':13487},'qd_forward_publication_verified':False})
    rc=probe.main(['--inspect'],credentials_loader=lambda path:pytest.fail('KEYS_OPENED'),
                  feed_factory=lambda symbols:pytest.fail('NETWORK_OPENED'))
    data=json.loads(capsys.readouterr().out)
    assert rc==0
    assert data['selected_revision']==12
    assert data['provider_authentication_performed'] is False
    assert data['private_credentials_accessed'] is False
    assert data['trading_authorized'] is False


def dummy_creds():
    return Credentials('TEST-ONLY-KEY','TEST-ONLY-SECRET')


class StubFeed:
    def __init__(self, symbols, *, auth=True, subscribed=True, fresh=True,
                 count=1, connection='DISCONNECTED', bad_event=False):
        self.symbols=symbols
        self.auth=auth;self.subscribed=subscribed;self.fresh=fresh
        self.count=count;self.connection=connection;self.bad_event=bad_event
    async def run(self, credentials,*,seconds,max_reconnects,on_fresh_quote):
        assert isinstance(credentials,Credentials)
        assert max_reconnects==0
        assert seconds==1
        if self.fresh:
            on_fresh_quote({'provider':'ALPACA_IEX','symbol':self.symbols[0],
                'timestamp':'2026-11-09T15:00:01Z',
                'paper_fill_authorized':self.bad_event,
                'live_order_authorized':False})
        return {'authenticated':self.auth,'subscribed':self.subscribed,
                'fresh_quote_observed_during_connection':self.fresh,
                'quote_count':self.count,'result':{'connection':self.connection}}


def test_valid_data_only_sample_accepts_only_observed_symbol_without_trading(capsys):
    calls=[]
    def loader(path):
        calls.append('READ_ONLY_AUTH_TEST')
        return dummy_creds()
    rc=probe.main(['--execute-data-only','--confirm-scope',probe.SCOPE,
                   '--seconds','1','--symbols','MSFT','SPY'],
                  credentials_loader=loader,feed_factory=lambda symbols:StubFeed(symbols))
    data=json.loads(capsys.readouterr().out)
    assert rc==0 and calls==['READ_ONLY_AUTH_TEST']
    assert data['status']=='BOUNDED_FRESH_IEX_OBSERVED_NOT_FINANCIAL_AUTHORITY'
    assert data['observed_symbols']==['MSFT']
    assert data['callback_quote_count']==1
    assert data['continuous_executable_prices_verified'] is False
    assert data['provider_rights_independently_accepted'] is False
    assert data['paper_fill_authorized'] is False
    assert data['live_order_authorized'] is False
    assert 'TEST-ONLY' not in json.dumps(data)


@pytest.mark.parametrize('kwargs',[
 {'auth':False}, {'subscribed':False}, {'fresh':False}, {'count':0},
 {'connection':'CONNECTED'}, {'bad_event':True},
])
def test_auth_ack_only_or_missing_fresh_quote_returns_refusal_not_success(kwargs,capsys):
    rc=probe.main(['--execute-data-only','--confirm-scope',probe.SCOPE,
                   '--seconds','1','--symbols','MSFT'],
                  credentials_loader=lambda _:dummy_creds(),
                  feed_factory=lambda symbols:StubFeed(symbols,**kwargs))
    data=json.loads(capsys.readouterr().out)
    assert rc==1
    assert data=={'status':'REFUSED','reason':probe.REASON}


def test_unrelated_fresh_symbol_from_forged_callback_refuses():
    data={'authenticated':True,'subscribed':True,'quote_count':5,
          'fresh_quote_observed_during_connection':True,
          'result':{'connection':'DISCONNECTED'}}
    with pytest.raises(IEXRefused,match='NO_AUTHENTICATED_FRESH_QUOTE'):
        probe.admit_result(data,observed_symbols={'TSLA'},observed_count=1,
                           requested_symbols=['MSFT'])
    with pytest.raises(IEXRefused,match='NO_AUTHENTICATED_FRESH_QUOTE'):
        probe.admit_result(data,observed_symbols={'MSFT'},observed_count=0,
                           requested_symbols=['MSFT'])


def test_actual_offline_inspection_uses_selected_r12_not_credentialed_provider():
    p=run_cli('--inspect')
    assert p.returncode==0,p.stderr
    data=json.loads(p.stdout)
    assert data['selected_revision']==12
    assert data['source_catalog_symbols']==13487
    assert data['forward_source_verified'] is False
    assert data['sample_already_verified'] is False
    assert data['private_credentials_accessed'] is False
