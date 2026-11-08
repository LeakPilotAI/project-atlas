"""Read-only combined QD/Hyperliquid commissioning scope and evidence gate."""
import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCOPE = ROOT / 'docs/ATLAS_UNIFIED_PAPER_COMMISSIONING_SCOPE_2026-11-07.json'


def inspect(*, root=ROOT, qd_report=None, observation_session=None):
    scope = json.loads((root / 'docs/ATLAS_UNIFIED_PAPER_COMMISSIONING_SCOPE_2026-11-07.json').read_text(encoding='utf-8'))
    expected = {'EXISTING_QUALITY_DIPS_PAPER_COMMISSIONING',
                'HYPERLIQUID_SIMULATED_ACCOUNT_INITIALIZATION_IF_TECHNICALLY_ELIGIBLE',
                'SUPERVISED_UNIFIED_PAPER_TESTING_IF_TECHNICALLY_ACCEPTED',
                'VERIFIED_OWNED_STOP_FLATTEN_RECONCILIATION',
                'LOCAL_NATIVE_PAPER_ACTIVATION_RECORD_IF_TECHNICALLY_ELIGIBLE',
                'CREATE_ONLY_NATIVE_CUSTODY_ENROLLMENT_IF_TECHNICALLY_ELIGIBLE',
                'QUALITY_DIPS_SIMULATED_USD_1000_INCEPTION_IF_TECHNICALLY_ELIGIBLE',
                'HYPERLIQUID_SIMULATED_USDC_1000_INCEPTION_IF_TECHNICALLY_ELIGIBLE'}
    scope_items = scope.get('scope')
    excluded_items = scope.get('exclusions')
    scope_shape_ok = (isinstance(scope_items, list) and isinstance(excluded_items, list)
                      and all(isinstance(x, str) for x in scope_items + excluded_items)
                      and len(scope_items) == len(set(scope_items))
                      and len(excluded_items) == len(set(excluded_items)))
    scope_ok = (scope_shape_ok and scope.get('schema') == 'ATLAS_UNIFIED_PAPER_COMMISSIONING_SCOPE_V1'
                and scope.get('status') == 'OPERATOR_AUTHORIZED_BOUNDED_NATIVE_COMMISSIONING_TECHNICAL_ACCEPTANCE_PENDING'
                and scope.get('runtime_consumable') is False
                and scope.get('startup_authorized') is False
                and scope.get('financial_publication_authorized') is False
                and scope.get('provider_activation_authorized') is False
                and scope.get('historical_gate_promotions') == 0
                and scope.get('authorization_record') == 'EXPLICIT_OPERATOR_CHAT_APPROVAL_NON_SELF_EXECUTING'
                and scope.get('installed_activation_record_created') is False
                and set(scope_items) == expected
                and {'LIVE_ORDERS','REAL_CAPITAL','WALLET_SIGNING','PRODUCTION_STARTUP','GENESIS','VPS_CLOUD','TECHNICAL_GATE_OVERRIDE'} <= set(excluded_items))
    qd = qd_report or {}
    entries = qd.get('checks', [])
    valid_entries = (isinstance(entries, list) and all(isinstance(x, dict) and isinstance(x.get('check'), str) and isinstance(x.get('status'), str) for x in entries))
    unique_entries = valid_entries and len({x['check'] for x in entries}) == len(entries)
    checks = {x['check']: x['status'] for x in entries} if unique_entries else {}
    from scripts.observation_runtime.hyperliquid_native_preflight import inspect as inspect_hyperliquid
    hl = inspect_hyperliquid()
    prerequisites = {
        'OPERATOR_SCOPE': 'APPROVED_NON_ACTIVATING' if scope_ok else 'BLOCKED',
        'QD_SOURCE_PUBLICATION': checks.get('OPERATIONAL_QD_SOURCE_PUBLICATION', 'BLOCKED'),
        'NATIVE_ACTIVATION': 'PASS' if checks.get('ACTIVATION_RECORD_PRESENT') == checks.get('ACTIVATION_NATIVE_VERIFIED') == 'PASS' else 'BLOCKED',
        'QD_FINANCIAL_INCEPTION': checks.get('FINANCIAL_INCEPTION', 'BLOCKED'),
        'QD_RUNTIME_AUTHORIZATION': checks.get('RUNTIME_AUTHORIZATION', 'BLOCKED'),
        'HYPERLIQUID_NATIVE_ACCOUNT_INCEPTION': hl['hyperliquid_native_account_inception'],
        'HYPERLIQUID_PROVIDER_RIGHTS_AND_DATA': hl['provider_rights_and_current_market_data'],
        'UNIFIED_OWNED_DESKTOP_STOP': 'NOT_INDEPENDENTLY_VERIFIED',
    }
    observation = {'status': 'NOT_SUPPLIED', 'financial_execution_authorized': False}
    if observation_session is not None:
        from scripts.observation_runtime.retained_provider_evidence_audit import audit_session
        try:
            observation = audit_session(observation_session)
        except (ValueError, OSError, KeyError, TypeError):
            observation = {'status': 'REFUSED', 'reason': 'RETAINED_OBSERVATION_UNVERIFIED',
                           'financial_execution_authorized': False}
    prerequisites['RETAINED_PROVIDER_RESEARCH'] = (
        'VERIFIED_HISTORICAL_ONLY' if observation.get('archive_integrity') == 'VERIFIED_LOCAL_HASH_CHAIN_NOT_PROVIDER_AUTHORITY'
        else 'NOT_VERIFIED')
    prerequisites['CURRENT_EXECUTABLE_MARKET_PRICES'] = 'NOT_INDEPENDENTLY_VERIFIED'
    return {'schema':'ATLAS_UNIFIED_PAPER_COMMISSIONING_PREFLIGHT_V1',
            'decision':'NO_GO', 'startup_authorized':False, 'live_trading_authorized':False,
            'prerequisites':prerequisites, 'retained_provider_observation':observation, 'hyperliquid_native_inventory':hl,
            'note':'QD source evidence is read from existing preflight; Hyperliquid evidence has no installed verifier yet. No permission is inferred from scope approval.'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--observation-session', type=Path, help='Existing closed local observation directory (read-only)')
    args = parser.parse_args()
    sha = subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    run = subprocess.run([sys.executable,'-m','scripts.observation_runtime.personal_commissioning_preflight',
                          '--json','--expected-source',sha,'--check-native-clock'],
                         cwd=ROOT,capture_output=True,text=True,check=False)
    if run.returncode not in (0,2):
        raise RuntimeError('QD_COMMISSIONING_PREFLIGHT_FAILED')
    print(json.dumps(inspect(qd_report=json.loads(run.stdout), observation_session=args.observation_session),indent=2,sort_keys=True))
    return 2

if __name__ == '__main__':
    raise SystemExit(main())
