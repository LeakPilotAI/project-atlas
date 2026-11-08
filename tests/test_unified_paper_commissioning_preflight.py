import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('unified_preflight', ROOT/'scripts/observation_runtime/unified_paper_commissioning_preflight.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_unified_scope_does_not_promote_unverified_accounts():
    report = module.inspect(qd_report={'checks':[{'check':'OPERATIONAL_QD_SOURCE_PUBLICATION','status':'PASS'},
        {'check':'ACTIVATION_RECORD_PRESENT','status':'PASS'}, {'check':'ACTIVATION_NATIVE_VERIFIED','status':'PASS'},
        {'check':'FINANCIAL_INCEPTION','status':'PASS'}, {'check':'RUNTIME_AUTHORIZATION','status':'PASS'}]})
    assert report['prerequisites']['OPERATOR_SCOPE'] == 'APPROVED_NON_ACTIVATING'
    assert report['prerequisites']['HYPERLIQUID_NATIVE_ACCOUNT_INCEPTION'] == 'NOT_INDEPENDENTLY_VERIFIED'
    assert report['decision'] == 'NO_GO' and report['startup_authorized'] is False


def test_unified_preflight_blocks_missing_qd_evidence():
    report = module.inspect(qd_report={'checks':[]})
    assert report['prerequisites']['QD_SOURCE_PUBLICATION'] == 'BLOCKED'
    assert report['prerequisites']['NATIVE_ACTIVATION'] == 'BLOCKED'


def test_hyperliquid_inventory_cannot_authorize_from_directory_names(tmp_path):
    from scripts.observation_runtime.hyperliquid_native_preflight import inspect
    (tmp_path/'Hyperliquid').mkdir()
    report = inspect(root=tmp_path)
    assert 'Hyperliquid' in report['custody_child_names']
    assert report['hyperliquid_native_account_inception'] == 'NOT_INDEPENDENTLY_VERIFIED'
    assert report['paper_startup_authorized'] is False


def test_hyperliquid_budget_inventory_is_read_only_and_non_authorizing(tmp_path):
    import sqlite3
    from scripts.observation_runtime.hyperliquid_native_preflight import inspect
    budget = tmp_path/'budget.sqlite'
    with sqlite3.connect(budget) as db:
        db.execute('CREATE TABLE budget (id INTEGER, max_attempts INTEGER, attempted INTEGER)')
        db.execute('INSERT INTO budget VALUES (1,12,2)')
    before = budget.read_bytes()
    result = inspect(root=tmp_path, budget_path=budget)
    assert result['request_budget_inventory'] == 'EXISTING_LEDGER_STRUCTURE_VALID_NOT_AUTHORIZED'
    assert result['provider_rights_and_current_market_data'] == 'NOT_INDEPENDENTLY_VERIFIED'
    assert budget.read_bytes() == before

def test_unified_preflight_refuses_foreign_observation(tmp_path):
    result = module.inspect(qd_report={'checks': []}, observation_session=tmp_path)
    assert result['retained_provider_observation']['status'] == 'REFUSED'
    assert result['decision'] == 'NO_GO'
    assert result['startup_authorized'] is False


def test_unified_preflight_no_observation_is_not_authority():
    result = module.inspect(qd_report={'checks': []})
    assert result['retained_provider_observation']['status'] == 'NOT_SUPPLIED'
    assert result['retained_provider_observation']['financial_execution_authorized'] is False

def test_closed_provider_research_cannot_satisfy_current_prices():
    import uuid
    from scripts.observation_runtime.desktop_observation import Session, REPO
    root = REPO / 'logs/observation-only' / ('session-test-' + uuid.uuid4().hex)
    session = Session(root, test=True)
    session.append('ALPACA_IEX_SESSION_RESULT', {'authenticated': True, 'subscribed': True,
                                                  'fresh_quote_observed_during_connection': True})
    session.append('HYPERLIQUID_RESEARCH', {'books': {'BTC': {}, 'ETH': {}, 'SOL': {}},
                                           'financial_execution_authorized': False})
    session.append('DATA_COLLECTION_STOP', {'financial_writers': False})
    session.append('SESSION_STOP', {'financial_writers': False})
    result = module.inspect(qd_report={'checks': []}, observation_session=root)
    assert result['prerequisites']['RETAINED_PROVIDER_RESEARCH'] == 'VERIFIED_HISTORICAL_ONLY'
    assert result['prerequisites']['CURRENT_EXECUTABLE_MARKET_PRICES'] == 'NOT_INDEPENDENTLY_VERIFIED'
    assert result['retained_provider_observation']['alpaca_fresh_quote_received'] is True
    assert result['decision'] == 'NO_GO'
    assert result['startup_authorized'] is False


def test_unified_preflight_refuses_duplicate_qd_evidence():
    report = module.inspect(qd_report={'checks': [
        {'check': 'ACTIVATION_RECORD_PRESENT', 'status': 'BLOCKED'},
        {'check': 'ACTIVATION_RECORD_PRESENT', 'status': 'PASS'},
        {'check': 'ACTIVATION_NATIVE_VERIFIED', 'status': 'PASS'},
        {'check': 'FINANCIAL_INCEPTION', 'status': 'PASS'}]})
    assert report['prerequisites']['NATIVE_ACTIVATION'] == 'BLOCKED'
    assert report['prerequisites']['QD_FINANCIAL_INCEPTION'] == 'BLOCKED'
    assert report['decision'] == 'NO_GO'


def test_unified_preflight_refuses_malformed_qd_evidence():
    for checks in (None, {}, [None], [{'check': 'FINANCIAL_INCEPTION', 'status': True}]):
        report = module.inspect(qd_report={'checks': checks})
        assert report['prerequisites']['QD_FINANCIAL_INCEPTION'] == 'BLOCKED'
        assert report['startup_authorized'] is False


def test_unified_scope_requires_live_and_unattended_exclusions(tmp_path):
    import json
    import shutil
    source = ROOT / 'docs/ATLAS_UNIFIED_PAPER_COMMISSIONING_SCOPE_2026-11-07.json'
    target = tmp_path / 'docs'
    target.mkdir()
    scope = json.loads(source.read_text(encoding='utf-8'))
    scope['exclusions'].remove('PRODUCTION_STARTUP')
    (target / source.name).write_text(json.dumps(scope), encoding='utf-8')
    report = module.inspect(root=tmp_path, qd_report={'checks': []})
    assert report['prerequisites']['OPERATOR_SCOPE'] == 'BLOCKED'
    assert report['decision'] == 'NO_GO'
