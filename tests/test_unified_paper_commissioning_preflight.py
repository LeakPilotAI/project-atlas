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
