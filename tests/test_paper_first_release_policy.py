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

@pytest.mark.parametrize('field,value',[
    ('deployment_drive','C:'),('windows_identity','NEW_SERVICE_ACCOUNT'),
    ('additional_windows_accounts_allowed',True),('c_deployment_allowed',True),
    ('runtime_root','C:/AtlasRuntime'),('financial_root','D:/Work/Project Atlas/data'),
    ('custody_root','C:/AtlasCustody'),('custody_independence_established',True),
    ('backup_independence_established',True),('drive_root_acl_change_allowed',True),
    ('project_acl_change_allowed',True),('provisioning_authorized',True),
    ('additional_windows_accounts_allowed',0),('schema','ATLAS_UNREVIEWED_LAYOUT'),
])
def test_d_only_single_existing_account_boundary(field,value):
    p,d=policies();d['local_layout'][field]=value
    with pytest.raises(ValueError,match='D_ONLY_SINGLE_ACCOUNT_LAYOUT_REQUIRED'):
        m.check_policy(p,d)


def test_d_only_layout_is_a_proposal_not_resource_or_authority():
    p,d=policies()
    assert d['local_layout']==m.LOCAL_LAYOUT
    assert d['storage_provisioning_authorized'] is False
    assert d['paper_startup_authorized'] is False
    p['deployment_policy_reference']='untrusted-local-policy.json'
    with pytest.raises(ValueError,match='D_ONLY_SINGLE_ACCOUNT_LAYOUT_REQUIRED'):
        m.check_policy(p,d)


def local_proposal():
    return json.loads((ROOT/'docs/LOCAL_SUPERVISED_PAPER_PROFILE_PROPOSAL_V1.json').read_text())


def test_local_profile_is_a_proposal_and_strict_contract_rejects_it():
    from app.investment.quality_dips_operational_contract import validate_enrollment
    p=local_proposal();m.check_local_paper_proposal(p)
    with pytest.raises(ValueError):validate_enrollment(p)
    release,deployment=policies();m.check_policy(release,deployment)
    assert release['required_blocked_gates']==['B1','C1','D1','E1']


@pytest.mark.parametrize('field,value',[
    ('status','ACCEPTED'),('runtime_consumable',True),('startup_authorized',True),
    ('financial_publication_authorized',True),('strict_profile_unchanged',False),
    ('canonical_gate_changes',1),('canonical_gate_changes',False),('profile_id','STRICT_OPERATIONAL'),
    ('architecture_reference','C:/Atlas'),('backup_policy','INDEPENDENT_ROLLBACK_PROTECTION'),
])
def test_local_profile_cannot_self_accept_or_change_strict_authority(field,value):
    p=local_proposal();p[field]=value
    with pytest.raises(ValueError):m.check_local_paper_proposal(p)


@pytest.mark.parametrize('field',['essential_controls','reduced_assurances','refuse_on','acceptance_required'])
@pytest.mark.parametrize('damage',['missing','duplicate','malformed'])
def test_local_profile_controls_and_reductions_cannot_disappear(field,damage):
    p=local_proposal()
    if damage=='missing':p[field].pop()
    if damage=='duplicate':p[field][-1]=p[field][0]
    if damage=='malformed':p[field][0]={}
    with pytest.raises(ValueError):m.check_local_paper_proposal(p)


def test_local_profile_is_not_an_operational_policy_replacement():
    _p,d=policies()
    with pytest.raises(ValueError):m.check_policy(local_proposal(),d)
    proposal=local_proposal();proposal['trial_progress']['authorized_days']=1
    with pytest.raises(ValueError):m.check_local_paper_proposal(proposal)


def test_local_profile_trial_counters_do_not_coerce_booleans():
    proposal=local_proposal();proposal['trial_progress']['authorized_days']=False
    with pytest.raises(ValueError):m.check_local_paper_proposal(proposal)


def autonomous_proposal():
    return json.loads((ROOT/'docs/AUTONOMOUS_PAPER_ONLY_PROFILE_PROPOSAL_V1.json').read_text())


def test_autonomous_target_proposed_strict_contract_unchanged():
    from app.investment.quality_dips_operational_contract import validate_enrollment
    proposal=autonomous_proposal();m.check_autonomous_paper_proposal(proposal)
    assert proposal['automation']['per_trade_confirmation'] is False
    assert proposal['automation']['automatic_partial_full_exits'] is True
    with pytest.raises(ValueError):validate_enrollment(proposal)
    _p,d=policies()
    with pytest.raises(ValueError):m.check_policy(proposal,d)
    m.check_local_paper_proposal(local_proposal())


@pytest.mark.parametrize('field,value',[
    ('startup_authorized',True),('financial_publication_authorized',True),('provider_connection_authorized',True),
    ('runtime_consumable',True),('status','ACCEPTED'),('canonical_gate_changes',1),('strict_profile_unchanged',False),
])
def test_autonomous_proposal_cannot_authorize_itself(field,value):
    p=autonomous_proposal();p[field]=value
    with pytest.raises(ValueError):m.check_autonomous_paper_proposal(p)


@pytest.mark.parametrize('section,field,value',[
    ('account','max_entry_notional_usd','101'),('account','max_open_positions',2),('account','borrowing',True),
    ('account','leverage',True),('account','scale_in',True),('account','force_end_of_day_liquidation',True),
    ('automation','per_trade_confirmation',True),('automation','automatic_entries',False),
    ('automation','automatic_partial_full_exits',False),('automation','global_stop','LIQUIDATE_AND_RESET'),
    ('automation','session_authorization','NONE'),('simulation','double_count_costs',True),
    ('simulation','unknown_effect','REPLAY'),('simulation','entry_reference','LAST_PRICE'),
    ('l1_contract','no_size_evidence','INVENT_LIQUIDITY'),('l1_contract','required_fields',[]),
    ('trial_progress','authorized_days',1),('trial_progress','authorized_days',False),
])
def test_autonomous_target_safety_and_evidence_cannot_silently_change(section,field,value):
    p=autonomous_proposal();p[section][field]=value
    with pytest.raises(ValueError):m.check_autonomous_paper_proposal(p)


@pytest.mark.parametrize('field',['essential_controls','acceptance_required'])
def test_autonomous_required_controls_cannot_be_omitted(field):
    p=autonomous_proposal();p[field].pop()
    with pytest.raises(ValueError):m.check_autonomous_paper_proposal(p)
