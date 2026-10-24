"""Static operator-scope guard; no services/providers/financial records."""
import importlib.util
import json
from pathlib import Path

import pytest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('paper_scope_guard',ROOT/'scripts/check_paper_release_policy.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)


def policies():
    return tuple(json.loads((ROOT/'docs'/name).read_text()) for name in ('ATLAS_PAPER_RELEASE_POLICY.json','ATLAS_DEPLOYMENT_POLICY.json'))


def test_actual_policy_and_all_runtime_sources():
    result=m.audit()
    assert result['source_files']>500 and result['issues']==[]
    assert result['startup_authorized'] is False and result['operational_acceptance'] is False


@pytest.mark.parametrize('field',['live_money_implementation_allowed','real_order_routing_allowed','real_capital_enrollment_allowed',
    'paper_to_live_promotion_allowed','live_toggle_or_dormant_path_allowed','operational_startup_authorized','financial_provisioning_authorized'])
def test_no_scope_or_authority_promotion(field):
    p,d=policies();p[field]=True
    with pytest.raises(ValueError):m.check_policy(p,d)


@pytest.mark.parametrize('field,value',[('max_entry_usd','101'),('hypothetical_opening_cash','2000'),('max_open_positions',True),
    ('manual_entries',False),('manual_exits',False),('scale_in',True),('legacy_adoption',True),('universe','MSFT_ONLY'),
    ('fees_bps_per_side','0'),('overnight_allowed',False)])
def test_exact_operator_account_intent(field,value):
    p,d=policies();p['account'][field]=value
    with pytest.raises(ValueError):m.check_policy(p,d)


@pytest.mark.parametrize('source',[
    'broker.submit_order(symbol="MSFT")', 'exchange.createOrder("BTC")', 'broker.cancel_order("x")',
    'broker.modify_order("x")', 'broker.replace_order("x")', 'from alpaca.trading.client import TradingClient',
    'import ccxt as market', 'from hyperliquid.exchange import Exchange',
    'importlib.import_module("alpaca.trading.client")','__import__("ccxt")',
    'getattr(broker,"place_order")({})', 'LIVE_TRADING_ENABLED=False', 'class LiveExecutionAdapter: pass',
    'os.getenv("ATLAS_ENABLE_LIVE_TRADING")', 'path="/api/live/orders"',
    'url="https://api.alpaca.markets/v2/orders"', 'from alpaca import trading',
    'def place_order(payload): return payload', 'settings={"live_trading_enabled":False}'])
def test_python_live_routing_or_dormant_paths_refuse(source):
    assert m.source_findings('backend/app/new.py',source)


@pytest.mark.parametrize('name,source',[('a.js','broker.submitOrder({})'),('a.ps1','EnableLiveTrading=$false'),
    ('a.html','<script>router.createOrder({})</script>'),('a.ts','const liveTradingToggle = false;')])
def test_other_runtime_languages_refuse(name,source):
    assert m.source_findings(name,source)


@pytest.mark.parametrize('source',[
    'book.place_paper_order()', '"""No real broker orders. Live execution disabled."""\nx=1',
    'from alpaca.data.historical import StockHistoricalDataClient', 'task.cancel()',
    'report={"live_execution":False}', 'value=state.live_execution'])
def test_research_paper_data_and_status_are_not_live_routing(source):
    assert m.source_findings('backend/app/example.py',source)==[]


def test_disabled_legacy_guard_is_frozen_and_no_broad_exemption():
    p,_=policies()
    assert set(p['retained_legacy_safety_guards'])=={'backend/app/prediction/policy.py'}
    assert m.source_findings('legacy.py','LIVE_EXECUTION=False',retained_false=True)==[]
    assert m.source_findings('legacy.py','LIVE_EXECUTION=True',retained_false=True)
    assert m.source_findings('legacy.py','LIVE_EXECUTION=False\nbroker.submit_order()',retained_false=True)
    assert m.source_findings('a.js','function enableLiveTrading() {}')


def test_new_gate_inventory_does_not_claim_acceptance_or_trials():
    p,d=policies()
    assert tuple(p['paper_release_gates'])==m.GATES
    assert all(g['status'] in ('BLOCKED','NOT_STARTED') for g in p['paper_release_gates'].values())
    p['paper_release_gates']['P7_SEVEN_DAY_TRIAL']['status']='PASS'
    with pytest.raises(ValueError):m.check_policy(p,d)
    p,d=policies();p['new_live_permission']=True
    with pytest.raises(ValueError):m.check_policy(p,d)
    p,d=policies();p['release_program']='LIVE'
    with pytest.raises(ValueError):m.check_policy(p,d)


def test_policy_matches_operational_contract_without_native_resources():
    from app.investment.quality_dips_operational_contract import validate_enrollment
    from test_quality_dips_operational_contract import fixture
    p,_=policies();e=fixture().e;validate_enrollment(e)
    assert e['account']['hypothetical_opening_cash']==p['account']['hypothetical_opening_cash']
    assert e['policy']['max_entry_usd']==p['account']['max_entry_usd']
    assert e['policy']['max_positions']==p['account']['max_open_positions']
    assert e['policy']['universe']==p['account']['universe']


def test_ci_runs_policy_guard_and_tests_before_runtime_regressions():
    source=(ROOT/'.github/workflows/atlas-tests.yml').read_text()
    assert 'python scripts/check_paper_release_policy.py' in source
    assert 'tests/test_paper_first_release_policy.py' in source


@pytest.mark.parametrize('damage',['change','delete'])
def test_retained_legacy_change_or_deletion_requires_review(tmp_path,damage):
    for name in ('docs/ATLAS_PAPER_RELEASE_POLICY.json','docs/ATLAS_DEPLOYMENT_POLICY.json','backend/app/prediction/policy.py'):
        target=tmp_path/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes((ROOT/name).read_bytes())
    target=tmp_path/'backend/app/prediction/policy.py'
    target.write_bytes(target.read_bytes().replace(b'\r\n',b'\n'))
    assert m.audit(tmp_path)['issues']==[]  # Same legacy source in Linux checkout.
    if damage=='delete':
        # Disposable source fixture only, not any original project file.
        target.unlink()
        with pytest.raises(ValueError,match='GUARD_MISSING'):m.audit(tmp_path)
    else:
        target.write_text(target.read_text().replace('LIVE_EXECUTION = False','LIVE_EXECUTION = True'))
        issues=m.audit(tmp_path)['issues']
        assert any('LEGACY_SAFETY_GUARD_CHANGED' in issue['findings'] for issue in issues)
