"""Bounded Alpaca IEX CLI: real false-positive fix and synthetic provider tests only."""
import json
import subprocess
import sys
from pathlib import Path

import pytest
from app.investment.alpaca_iex import Credentials, IEXRefused

from scripts.observation_runtime import alpaca_iex_probe as probe

ROOT=Path(__file__).resolve().parents[1]
SCRIPT=ROOT/'scripts/observation_runtime/alpaca_iex_probe.py'


@pytest.fixture(autouse=True)
def simulated_legacy_selector_only_for_unit_tests(monkeypatch, tmp_path):
    """Historical selection fixtures stay synthetic; installed R22 is never spoofed.

    Direct CLI subprocesses do not inherit monkeypatches and must inspect
    the genuine selected revision 22 and its full installed-native source.
    """
    from scripts.observation_runtime import atlas_r15_paper_offline_commissioning as r15
    monkeypatch.setattr(probe, 'R22_SELECTED_ENVELOPE',
                        tmp_path / 'historical-unit-selection-has-no-r22')
    monkeypatch.setattr(r15, 'inspect', lambda: {
        'schema': 'ATLAS_SELECTED_R15_OFFLINE_FINANCIAL_COMMISSIONING_V1',
        'decision': 'NO_GO', 'selected_native_revision': 14,
        'selected_code_verified': True,
        'installed_financial_clock_source_binding_verified': True,
        'financial_operating_gates_independently_accepted': 0,
        'current_iex_equity_quotes_verified': False,
        'native_qd_forward_writer_enrolled': False,
        'paper_start_authorized': False,
        'provider_connection_opened': False,
        'credential_bytes_read': False,
        'live_trading_authorized': False,
        'quality_dips_research_catalog_symbols': 13487,
    })


def run_cli(*args):
    return subprocess.run([sys.executable,str(SCRIPT),*args],
       cwd=ROOT,capture_output=True,text=True,timeout=60,check=False)


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


def test_data_only_offline_inspect_avoids_private_config(monkeypatch,capsys,tmp_path):
    from scripts.observation_runtime import atlas_r12_alpaca_source_admission as source
    monkeypatch.setattr(probe, 'R14_SELECTED_ENVELOPE', tmp_path/'no-r14-selection')
    monkeypatch.setattr(probe, 'R15_SELECTED_ENVELOPE', tmp_path/'no-r15-selection')
    monkeypatch.setattr(source,'assess',lambda:{'native_revision':12,
        'catalog':{'research_symbol_count':13487},'qd_forward_publication_verified':False,
        'startup_authorized':False,'contract_entitlement_independently_verified':False})
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


def test_actual_offline_inspection_uses_selected_r22_not_credentialed_provider():
    p=run_cli('--inspect')
    assert p.returncode==0,p.stderr
    data=json.loads(p.stdout)
    assert data['selected_revision']==22
    assert data['source_catalog_symbols']==13487
    assert data['forward_source_verified'] is False
    assert data['sample_already_verified'] is False
    assert data['private_credentials_accessed'] is False
    assert data['provider_connected'] is False
    assert data['provider_rights_independently_accepted'] is False
    assert data['current_executable_quotes_verified'] is False
    assert data['trading_authorized'] is False


def test_r14_offline_inspect_never_reads_alpaca_keys_or_network(monkeypatch,capsys,tmp_path):
    monkeypatch.setattr(probe, 'R15_SELECTED_ENVELOPE', tmp_path/'no-r15-selection')
    from scripts.observation_runtime import (
        atlas_r14_two_lane_source_preflight as source,
    )
    monkeypatch.setattr(probe.Credentials,'load',
        lambda *_:pytest.fail('PRIVATE_KEYS_MUST_NOT_BE_OPENED'))
    monkeypatch.setattr(source,'inspect', lambda: {
        'schema':'ATLAS_R14_TWO_LANE_FINANCIAL_SOURCE_PREFLIGHT_V1',
        'decision':'NO_GO',
        'selected_code_revision':13,
        'financial_operating_gates_accepted':0,
        'paper_startup_authorized':False,
        'provider_connections_opened':False,
        'quality_dips':{
            'research_inventory_verified':True,
            'catalog_symbols':13487,
            'operational_source_publication_verified':False,
            'robinhood_equity_etf_universe_verified':False},
        'hyperliquid':{'native_financial_writer_verified':False}})
    result=probe.main(['--inspect'],
        credentials_loader=lambda *_:pytest.fail('CREDENTIAL_LOAD_NOT_AUTHORIZED'),
        feed_factory=lambda *_:pytest.fail('NETWORK_OR_SOCKET_NOT_AUTHORIZED'))
    value=json.loads(capsys.readouterr().out)
    assert result==0
    assert value['selected_revision']==13
    assert value['source_catalog_symbols']==13487
    for field in ('private_credentials_accessed','provider_connected',
                  'provider_authentication_performed',
                  'provider_rights_independently_accepted',
                  'current_executable_quotes_verified',
                  'robinhood_universe_verified','trading_authorized',
                  'sample_already_verified'):
        assert value[field] is False


@pytest.mark.parametrize('field,value',[
    ('decision','GO'),
    ('selected_code_revision',12),
    ('financial_operating_gates_accepted',1),
    ('paper_startup_authorized',True),
    ('provider_connections_opened',True),
])
def test_r14_offline_preview_cannot_upgrade_financial_authority(
        monkeypatch,capsys,tmp_path,field,value):
    monkeypatch.setattr(probe, 'R15_SELECTED_ENVELOPE', tmp_path/'no-r15-selection')
    from scripts.observation_runtime import (
        atlas_r14_two_lane_source_preflight as source,
    )
    base={
        'schema':'ATLAS_R14_TWO_LANE_FINANCIAL_SOURCE_PREFLIGHT_V1',
        'decision':'NO_GO','selected_code_revision':13,
        'financial_operating_gates_accepted':0,
        'paper_startup_authorized':False,'provider_connections_opened':False,
        'quality_dips':{
            'research_inventory_verified':True,
            'catalog_symbols':13487,
            'operational_source_publication_verified':False,
            'robinhood_equity_etf_universe_verified':False},
        'hyperliquid':{'native_financial_writer_verified':False}}
    base[field]=value
    monkeypatch.setattr(source,'inspect',lambda:base)
    rc=probe.main(['--inspect'],
        credentials_loader=lambda *_:pytest.fail('KEYS_OPENED'),
        feed_factory=lambda *_:pytest.fail('NETWORK_OPENED'))
    result=json.loads(capsys.readouterr().out)
    assert rc==1
    assert result=={'status':'REFUSED','reason':probe.REASON}


def test_r14_selected_invalid_source_report_refuses_without_r12_fallback(
        monkeypatch,capsys,tmp_path):
    monkeypatch.setattr(probe, 'R15_SELECTED_ENVELOPE', tmp_path/'no-r15-selection')
    from scripts.observation_runtime import atlas_r12_alpaca_source_admission as r12
    from scripts.observation_runtime import (
        atlas_r14_two_lane_source_preflight as source,
    )
    monkeypatch.setattr(source,'inspect',
        lambda: (_ for _ in ()).throw(ValueError('NATIVE_CHAIN_MISMATCH')))
    monkeypatch.setattr(r12,'assess',
        lambda:pytest.fail('R12_FALLBACK_MUST_NOT_BYPASS_SELECTED_R14'))
    rc=probe.main(['--inspect'],
        credentials_loader=lambda *_:pytest.fail('KEYS_OPENED'),
        feed_factory=lambda *_:pytest.fail('NETWORK_OPENED'))
    assert rc==1
    assert json.loads(capsys.readouterr().out)['status']=='REFUSED'


def test_credentials_mode_still_requires_exact_explicit_data_only_scope(
        capsys,monkeypatch):
    monkeypatch.setattr(probe.Credentials,'load',
        lambda *_:pytest.fail('CREDENTIALS_MUST_NOT_BE_READ'))
    assert probe.main(['--execute-data-only','--seconds','1','--symbols','MSFT'])==1
    assert json.loads(capsys.readouterr().out)=={
        'status':'REFUSED','reason':probe.REASON}


def test_selected_r15_inspect_does_not_read_keys_or_open_provider(monkeypatch,capsys):
    monkeypatch.setattr(probe.Credentials,'load',
        lambda *_:pytest.fail('PRIVATE_ALPACA_KEYS_NOT_AUTHORIZED'))
    result=probe.main(
        ['--inspect'],
        credentials_loader=lambda *_:pytest.fail('KEYS_OPENED'),
        feed_factory=lambda *_:pytest.fail('PROVIDER_SOCKET_OPENED'))
    view=json.loads(capsys.readouterr().out)
    assert result==0
    assert view['selected_revision']==14
    assert view['source_catalog_symbols']==13487
    assert view['forward_source_verified'] is False
    for field in ('provider_authentication_performed','private_credentials_accessed',
                  'provider_connected','provider_rights_independently_accepted',
                  'current_executable_quotes_verified','trading_authorized'):
        assert view[field] is False


def test_r15_selected_forged_financial_go_fails_before_credentials(monkeypatch,capsys):
    from scripts.observation_runtime import atlas_r15_paper_offline_commissioning as r15
    original=r15.inspect()
    for field,forgery in (
        ('decision','GO'),
        ('selected_native_revision',13),
        ('native_qd_forward_writer_enrolled',True),
        ('provider_connection_opened',True),
        ('paper_start_authorized',True),
        ('financial_operating_gates_independently_accepted',1),
    ):
        monkeypatch.setattr(r15,'inspect',lambda f=field,v=forgery: {**original,f:v})
        result=probe.main(
            ['--execute-data-only','--confirm-scope',probe.SCOPE,
             '--seconds','1','--symbols','MSFT'],
            credentials_loader=lambda *_:pytest.fail(
                'CREDENTIALS_MUST_NOT_OPEN_WHEN_SELECTED_R15_GATE_REFUSES'),
            feed_factory=lambda *_:pytest.fail('PROVIDER_MUST_NOT_CONNECT'))
        assert result==1
        assert json.loads(capsys.readouterr().out)=={
            'status':'REFUSED','reason':probe.REASON}

def test_r22_selection_supersedes_r15_without_keys_or_provider(monkeypatch, tmp_path, capsys):
    from scripts.observation_runtime import atlas_r15_paper_offline_commissioning as r15
    selected = tmp_path / "r0022.json"
    selected.write_text("selected-branch-fixture-only", encoding="ascii")
    monkeypatch.setattr(probe, "R22_SELECTED_ENVELOPE", selected)
    monkeypatch.setattr(probe, "_inspect_current_r22_source", lambda: 13487)
    monkeypatch.setattr(r15, "inspect",
                        lambda: pytest.fail("HISTORICAL_R15_MUST_NOT_RUN"))
    monkeypatch.setattr(probe.Credentials, "load",
                        lambda *_: pytest.fail("CREDENTIALS_MUST_NOT_BE_OPENED"))
    rc = probe.main(["--inspect"],
                    credentials_loader=lambda *_: pytest.fail("KEYS_OPENED"),
                    feed_factory=lambda *_: pytest.fail("PROVIDER_OPENED"))
    packet = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert packet["selected_revision"] == 22
    assert packet["source_catalog_symbols"] == 13487
    for key in ("forward_source_verified", "private_credentials_accessed",
                "provider_connected", "trading_authorized",
                "provider_rights_independently_accepted",
                "current_executable_quotes_verified"):
        assert packet[key] is False


def test_r22_native_selection_refusal_never_falls_back_or_opens_keys(
        monkeypatch, tmp_path, capsys):
    from scripts.observation_runtime import atlas_r15_paper_offline_commissioning as r15
    selected = tmp_path / "r0022.json"
    selected.write_text("selected-branch-fixture-only", encoding="ascii")
    monkeypatch.setattr(probe, "R22_SELECTED_ENVELOPE", selected)
    monkeypatch.setattr(probe, "_inspect_current_r22_source",
                        lambda: (_ for _ in ()).throw(ValueError(
                            "IEX_SELECTED_R22_EXACT_NATIVE_CHAIN_REQUIRED")))
    monkeypatch.setattr(r15, "inspect",
                        lambda: pytest.fail("R15_FALLBACK_NOT_AUTHORIZED"))
    rc = probe.main(
        ["--execute-data-only", "--confirm-scope", probe.SCOPE,
         "--seconds", "1", "--symbols", "MSFT"],
        credentials_loader=lambda *_: pytest.fail("KEYS_MUST_NOT_OPEN"),
        feed_factory=lambda *_: pytest.fail("NETWORK_MUST_NOT_OPEN"))
    assert rc == 1
    assert json.loads(capsys.readouterr().out) == {
        "status": "REFUSED", "reason": probe.REASON}
