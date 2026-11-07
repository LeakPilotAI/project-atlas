"""Read-only combined QD/Hyperliquid commissioning scope and evidence gate."""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCOPE = ROOT / 'docs/ATLAS_UNIFIED_PAPER_COMMISSIONING_SCOPE_2026-11-07.json'


def inspect(*, root=ROOT, qd_report=None):
    scope = json.loads((root / 'docs/ATLAS_UNIFIED_PAPER_COMMISSIONING_SCOPE_2026-11-07.json').read_text(encoding='utf-8'))
    expected = {'EXISTING_QUALITY_DIPS_PAPER_COMMISSIONING',
                'HYPERLIQUID_SIMULATED_ACCOUNT_INITIALIZATION_IF_TECHNICALLY_ELIGIBLE',
                'SUPERVISED_UNIFIED_PAPER_TESTING_IF_TECHNICALLY_ACCEPTED',
                'VERIFIED_OWNED_STOP_FLATTEN_RECONCILIATION',
                'LOCAL_NATIVE_PAPER_ACTIVATION_RECORD_IF_TECHNICALLY_ELIGIBLE',
                'CREATE_ONLY_NATIVE_CUSTODY_ENROLLMENT_IF_TECHNICALLY_ELIGIBLE',
                'QUALITY_DIPS_SIMULATED_USD_1000_INCEPTION_IF_TECHNICALLY_ELIGIBLE',
                'HYPERLIQUID_SIMULATED_USDC_1000_INCEPTION_IF_TECHNICALLY_ELIGIBLE'}
    scope_ok = (scope.get('schema') == 'ATLAS_UNIFIED_PAPER_COMMISSIONING_SCOPE_V1'
                and scope.get('status') == 'OPERATOR_AUTHORIZED_BOUNDED_NATIVE_COMMISSIONING_TECHNICAL_ACCEPTANCE_PENDING'
                and scope.get('runtime_consumable') is False
                and scope.get('startup_authorized') is False
                and scope.get('financial_publication_authorized') is False
                and scope.get('provider_activation_authorized') is False
                and scope.get('historical_gate_promotions') == 0
                and scope.get('authorization_record') == 'EXPLICIT_OPERATOR_CHAT_APPROVAL_NON_SELF_EXECUTING'
                and scope.get('installed_activation_record_created') is False
                and set(scope.get('scope', [])) == expected
                and {'LIVE_ORDERS','REAL_CAPITAL','GENESIS','VPS_CLOUD','TECHNICAL_GATE_OVERRIDE'} <= set(scope.get('exclusions', [])))
    qd = qd_report or {}
    checks = {x.get('check'): x.get('status') for x in qd.get('checks', [])}
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
    return {'schema':'ATLAS_UNIFIED_PAPER_COMMISSIONING_PREFLIGHT_V1',
            'decision':'NO_GO', 'startup_authorized':False, 'live_trading_authorized':False,
            'prerequisites':prerequisites, 'hyperliquid_native_inventory':hl,
            'note':'QD source evidence is read from existing preflight; Hyperliquid evidence has no installed verifier yet. No permission is inferred from scope approval.'}


def main():
    sha = subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    run = subprocess.run([sys.executable,'-m','scripts.observation_runtime.personal_commissioning_preflight',
                          '--json','--expected-source',sha,'--check-native-clock'],
                         cwd=ROOT,capture_output=True,text=True,check=False)
    if run.returncode not in (0,2):
        raise RuntimeError('QD_COMMISSIONING_PREFLIGHT_FAILED')
    print(json.dumps(inspect(qd_report=json.loads(run.stdout)),indent=2,sort_keys=True))
    return 2

if __name__ == '__main__':
    raise SystemExit(main())
