"""Offline premarket qualification: concrete engine checks, no production activation."""
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts.observation_runtime import atlas_premarket_paper_offline_qualification as pre

ROOT=Path(__file__).resolve().parents[1]


def test_actual_premarket_command_requires_no_credentials_and_reports_no_go():
    p=subprocess.run([str(ROOT/'backend/.venv/Scripts/python.exe'),
        '-B','-m','scripts.observation_runtime.atlas_premarket_paper_offline_qualification',
        '--offline-only'],cwd=ROOT,capture_output=True,text=True,timeout=160)
    assert p.returncode==2,p.stderr
    body=json.loads(p.stdout)
    assert body['schema']=='ATLAS_NONFINANCIAL_PREMARKET_OFFLINE_QUALIFICATION_V1'
    assert body['status']=='OFFLINE_SIMULATIONS_PASS_FINANCIAL_PAPER_NO_GO'
    assert body['native_revision']==12
    assert body['native_selected_readback_verified'] is True
    assert body['alpaca_research_symbol_count']==13487
    assert body['iex_roster_size']==30
    assert len(body['quality_dips_disposable_scenarios'])==4
    assert {r['scenario'] for r in body['quality_dips_disposable_scenarios']}==set(pre.SCENARIOS)
    assert all(r['incremental_recovery_clean'] is True
               and r['snapshot_and_incremental_cash_reconciled'] is True
               and r['paper_execution_authorized'] is False
               for r in body['quality_dips_disposable_scenarios'])
    for key in ('current_iex_quotes_verified','forward_qd_source_accepted',
                'full_paper_production_ready','hyperliquid_native_account_accepted',
                'hyperliquid_provider_data_accepted','iex_config_credentials_opened',
                'kalshi_operational_scope_accepted','live_trading_authorized',
                'stop_financial_owner_accepted','paper_accounts_created',
                'paper_orders_authorized','provider_connections_opened','startup_authorized'):
        assert body[key] is False
    assert body['financial_gates_accepted']==0


def test_no_unscoped_qualified_premarket_start_cli_is_available():
    p=subprocess.run([str(ROOT/'backend/.venv/Scripts/python.exe'),
        '-B','-m','scripts.observation_runtime.atlas_premarket_paper_offline_qualification'],
        cwd=ROOT,capture_output=True,text=True,timeout=20)
    assert p.returncode!=0
    assert not p.stdout
    assert 'required' in p.stderr
    assert not 'ALPACA_API_SECRET' in p.stderr


@pytest.mark.parametrize('change',[
 {'status':'R12_PAPER_TRADING_READY'},
 {'revision':11},
 {'r12_head':'0'*64},
 {'support_receipt_verified':False},
 {'selected_clock_source_verified':False},
 {'financial_authority':True},
 {'orders_authorized':True},
 {'live_trading_authorized':True},
])
def test_installed_native_identity_or_authority_broadening_refuses(monkeypatch,change):
    import scripts.observation_runtime.atlas_premarket_paper_offline_qualification as module
    canonical={
       'status':'NATIVE_R12_CODE_SELECTED_NOT_FINANCIAL_PAPER',
       'revision':12,'selected_release':module.APP.name,'r12_head':module.HEAD,
       'native_record_pair_verified':True,'selected_clock_source_verified':True,
       'support_receipt_verified':True,'independent_proof_verified':True,
       'deep_application_verified':False,
       'financial_authority':False,'paper_accounts_authorized':False,
       'providers_authorized':False,'orders_authorized':False,
       'paper_start_authorized':False,'live_trading_authorized':False}
    canonical.update(change)
    monkeypatch.setattr(module.subprocess,'run',
        lambda *args,**kwargs:SimpleNamespace(returncode=0,stdout=json.dumps(canonical)))
    with pytest.raises(ValueError,match='SELECTED_RELEASE_OR_SCOPE_REFUSED'):
        module.check_native_status()


def test_selected_native_diagnostic_failure_cannot_be_reinterpreted(monkeypatch):
    monkeypatch.setattr(pre.subprocess,'run',
        lambda *args,**kwargs:SimpleNamespace(returncode=1,stderr='REFUSED',stdout='{}'))
    with pytest.raises(ValueError,match='INSTALLED_R12_READBACK_REFUSED'):
        pre.check_native_status()


def test_no_real_credentials_are_loaded_from_offline_report(monkeypatch):
    from app.investment.alpaca_iex import Credentials
    monkeypatch.setattr(Credentials,'load',lambda *args:pytest.fail('CREDENTIALS MUST NEVER LOAD'))
    result=pre.inspect(deep=False)
    assert result['provider_connections_opened'] is False
    assert result['iex_config_credentials_opened'] is False
    assert result['paper_orders_authorized'] is False
    assert result['financial_gates_accepted']==0


def test_script_contains_no_provider_or_financial_mutation_entrypoints():
    raw=Path(pre.__file__).read_text(encoding='utf-8')
    assert 'Credentials.load(' not in raw
    assert 'IEXFeed(' not in raw
    assert 'initialize_paper_account(' not in raw
    assert 'execute_data_only' not in raw
    assert "return 2 # NO-GO is deliberate" in raw
    assert '--offline-only' in raw
