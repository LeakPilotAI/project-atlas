"""Real selected-r12 Alpaca research catalog, bounded IEX source, no financial grant."""
import copy
import hashlib
import json
import subprocess
from pathlib import Path

import pytest

from scripts.observation_runtime import atlas_r12_alpaca_source_admission as src
from scripts.observation_runtime.alpaca_equity_catalog import inventory_snapshot


def sample():
    return inventory_snapshot([
        {'class':'us_equity','symbol':name,'status':'active','tradable':True,
         'exchange':'NASDAQ','id':name} for name in ('MSFT','AVGO','SPY')],
        captured_at='2026-11-09T00:00:00+00:00')


def save(tmp_path,payload):
    path=tmp_path/'snapshot.json';path.write_text(json.dumps(payload),encoding='utf-8')
    return path


def probe(**override):
    row={'schema':'ATLAS_IEX_BOUNDED_DATA_ONLY_PROBE_V1',
        'authenticated':True,'subscribed':True,'connection_closed':True,
        'quote_count':3,'fresh_quote_observed_during_connection':True,
        'paper_fill_authorized':False,'live_order_authorized':False}
    row.update(override)
    return row


def test_real_existing_research_inventory_and_capacity_do_not_mint_paper_access():
    data=src.inventory()
    assert data['provider_research_inventory_verified'] is True
    assert data['research_symbol_count']>=10000
    assert data['required_nonoverlapping_30_symbol_rosters']==(
        data['research_symbol_count']+29)//30
    assert len(data['read_only_preview'])==8
    assert data['catalog_content_sha256']==(
        '40eb4b04a18804a4841f37611452c978e0e92c4096222974b1f98f14c7f159f5')
    assert data['robinhood_brokerage_coverage_verified'] is False
    assert data['paper_execution_eligible_from_catalog'] is False


def test_synthetic_research_asset_scope_and_digest_pass_offline(tmp_path):
    out=src.inventory(save(tmp_path,sample()))
    assert out['research_symbol_count']==3
    assert out['read_only_preview']==['AVGO','MSFT','SPY']
    assert out['required_nonoverlapping_30_symbol_rosters']==1
    assert out['paper_execution_eligible_from_catalog'] is False
    assert out['robinhood_brokerage_coverage_verified'] is False


@pytest.mark.parametrize('field,value',[
    ('schema','BROKERAGE_ACCEPTED'),('source','ROBINHOOD'),
    ('paper_execution_authorized',True),('live_order_authorized',True),
    ('robinhood_brokerage_verified',True)])
def test_research_record_with_broadened_scope_refused(tmp_path,field,value):
    fake=sample();fake[field]=value
    with pytest.raises(ValueError,match='R12_ALPACA_RESEARCH_ONLY_INVENTORY_REQUIRED'):
        src.inventory(save(tmp_path,fake))


def test_catalog_digest_tamper_refuses_without_any_financial_side_effect(tmp_path):
    fake=sample();fake['rows'][0]['symbol']='FAKE'
    with pytest.raises(ValueError,match='DIGEST_OR_SYMBOL'):
        src.inventory(save(tmp_path,fake))


def test_catalog_duplicate_symbols_refused_even_if_digest_recomputed(tmp_path):
    fake=sample()
    fake['rows'][1]['symbol']=fake['rows'][0]['symbol']
    with pytest.raises(ValueError,match='UNSORTED_OR_DUPLICATE'):
        src.inventory(save(tmp_path,fake))


def test_catalog_asset_class_and_provider_trade_flags_refused(tmp_path):
    for bad_key,bad_value in [('asset_class','crypto'),('provider_tradable',False),('exchange',42)]:
        fake=sample();fake['rows'][0][bad_key]=bad_value
        with pytest.raises(ValueError,match='ASSET_SCOPE_CHANGED'):
            src.inventory(save(tmp_path,fake))


def test_non_file_and_symlink_and_invalid_json_refuse(tmp_path):
    with pytest.raises(ValueError,match='ABSENT_OR_UNSAFE'):
        src.inventory(tmp_path/'not-there.json')
    invalid=tmp_path/'invalid.json';invalid.write_text('NO JSON',encoding='utf-8')
    with pytest.raises(ValueError,match='MALFORMED'):
        src.inventory(invalid)


@pytest.mark.parametrize('field,bad',[
   ('schema','ALPACA_PAPER_ORDER_PROOF'),('authenticated',False),
   ('subscribed',False),('connection_closed',False),
   ('quote_count',0),('quote_count',True),
   ('fresh_quote_observed_during_connection',False),
   ('paper_fill_authorized',True),('live_order_authorized',True)])
def test_iex_bounded_probe_requires_actual_observation_not_fill_claim(field,bad):
    with pytest.raises(ValueError,match='R12_IEX_BOUNDED_REAL_DATA_EVIDENCE_REQUIRED'):
        src.validate_bounded_iex_probe(probe(**{field:bad}))


def test_even_accepted_observation_is_not_continuous_financial_entitlement():
    result=src.validate_bounded_iex_probe(probe())
    assert result['observed_authenticated_iex_quote'] is True
    assert result['sample_connection_closed'] is True
    assert result['continuous_live_quote_freshness_verified'] is False
    assert result['provider_data_rights_accepted'] is False
    assert result['paper_execution_authorized'] is False


def test_broadened_selected_release_refused_before_inventory(monkeypatch,tmp_path):
    from scripts.observation_runtime import atlas_r12_financial_readiness as finance
    monkeypatch.setattr(finance,'run',lambda *,deep: {'native_revision':11,'decision':'NO_GO',
       'selected_code_verified':True,'accepted_financial_operating_gates':0,'startup_authorized':False})
    with pytest.raises(ValueError,match='R12_IEX_SELECTED_FINANCIAL_GATE_STATUS_REQUIRED'):
        src.assess(catalog_path=tmp_path/'not-there.json')


def test_metadata_only_config_never_reads_private_credential_bytes(monkeypatch,tmp_path):
    from scripts.observation_runtime import atlas_r12_financial_readiness as finance
    import scripts.observation_runtime.quality_dips_source_inventory as qd
    monkeypatch.setattr(finance,'run',lambda *,deep: {'native_revision':12,'decision':'NO_GO',
       'selected_code_verified':True,'accepted_financial_operating_gates':0,'startup_authorized':False})
    monkeypatch.setattr(qd,'inspect',lambda *,root=None: {
       'schema':'ATLAS_QD_NATIVE_SOURCE_INVENTORY_V1',
       'operational_publication_verified':False,
       'reason':'SIMULATED_QD_SOURCE_EMPTY'})
    conf=tmp_path/'alpaca.env'
    conf.write_text('ALPACA_API_SECRET=DO_NOT_READ',encoding='utf-8')
    original=Path.read_bytes
    def private_guard(obj):
        if Path(obj)==conf:pytest.fail('PRIVATE_ALPACA_CONFIG_MUST_NOT_BE_OPENED')
        return original(obj)
    monkeypatch.setattr(Path,'read_bytes',private_guard)
    result=src.assess(catalog_path=save(tmp_path,sample()),config_path=conf,
                      source_root=tmp_path)
    assert result['credential_configuration_file_present'] is True
    assert result['credentials_opened_or_authenticated'] is False
    assert result['provider_connections_opened'] is False
    assert result['financial_accounts_created'] is False
    assert result['orders_submitted'] is False
    assert result['financial_paper_gates_accepted']==0
    assert result['status']=='RESEARCH_UNIVERSE_VERIFIED_FORWARD_SOURCE_BLOCKED'


def test_actual_selected_r12_catalog_custody_inspection_returns_no_go_not_auth():
    result=subprocess.run([str(src.ROOT/'backend/.venv/Scripts/python.exe'),'-B',
            '-m','scripts.observation_runtime.atlas_r12_alpaca_source_admission',
            '--inspect'],cwd=src.ROOT,capture_output=True,text=True,timeout=150)
    assert result.returncode==2,result.stderr
    out=json.loads(result.stdout)
    assert out['native_revision']==12
    assert out['catalog']['research_symbol_count']>=10000
    assert out['catalog']['provider_research_inventory_verified'] is True
    assert out['qd_forward_publication_verified'] is False
    assert out['contract_entitlement_independently_verified'] is False
    assert out['bounded_iex_data_session_verified'] is False
    assert out['robinhood_brokerage_coverage_verified'] is False
    assert out['financial_paper_gates_accepted']==0
    assert out['startup_authorized'] is False
