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
