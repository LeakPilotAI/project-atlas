"""One-command, read-only Atlas premarket qualification. NEVER starts trading.

Runs the actual selected r12 native verifier, QD/HL financial NO-GO readiness,
disposable QD PAPER scenarios and offline IEX roster inspection. Explicitly no
credential load, no provider sockets, no financial account, no orders, no OS
startup services, no mutation of source/native selector.
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT=Path(r'D:\Work\Project Atlas')
APP=Path(r'D:\AtlasRuntime\releases\2d4879878bf58bea5a3ed0a986b809791f638fec')
SELECTED_STATUS=ROOT/'scripts/atlas_version_safe_r12_selected_status.py'
HEAD='f4cf83bb1e98ecb7cfa3be37fe27e80a79b339dc26f73358a1702349b47958fd'
SCENARIOS=('take_profit','stop_loss','gap_down','no_entry')


def check_native_status(*,deep=False):
    cmd=[str(APP/'python/python.exe'),'-I','-B','-S',str(SELECTED_STATUS)]
    if deep:
        cmd.append('--deep')
    p=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True,timeout=120)
    if p.returncode!=0:
        raise ValueError('ATLAS_PREMARKET_INSTALLED_R12_READBACK_REFUSED')
    try:
        data=json.loads(p.stdout)
    except (ValueError,UnicodeError):
        raise ValueError('ATLAS_PREMARKET_SELECTED_STATUS_MALFORMED') from None
    if (type(data) is not dict
        or data.get('status')!='NATIVE_R12_CODE_SELECTED_NOT_FINANCIAL_PAPER'
        or data.get('revision')!=12
        or data.get('selected_release')!=APP.name
        or data.get('r12_head')!=HEAD
        or data.get('native_record_pair_verified') is not True
        or data.get('selected_clock_source_verified') is not True
        or data.get('support_receipt_verified') is not True
        or data.get('independent_proof_verified') is not True
        or data.get('deep_application_verified') is not deep
        or any(data.get(key) is not False for key in (
          'financial_authority','paper_accounts_authorized','providers_authorized',
          'orders_authorized','paper_start_authorized','live_trading_authorized'))):
        raise ValueError('ATLAS_PREMARKET_SELECTED_RELEASE_OR_SCOPE_REFUSED')
    return data


def inspect(*,deep=False):
    from scripts.observation_runtime.atlas_r12_financial_readiness import run as finance
    from scripts.observation_runtime.atlas_r12_iex_rotation_bridge import inspect as roster
    from scripts.observation_runtime.alpaca_iex_probe import main as probe_main
    from scripts.observation_runtime.disposable_v3_paper_demo import run_demo
    from scripts.observation_runtime.disposable_v3_incremental_demo import run_incremental_demo
    from scripts.observation_runtime.hyperliquid_native_preflight import inspect as hyperliquid
    from contextlib import redirect_stdout
    from io import StringIO

    native=check_native_status(deep=deep)
    gates=finance(deep=False)
    if (gates.get('decision')!='NO_GO'
        or gates.get('native_revision')!=12
        or gates.get('accepted_financial_operating_gates')!=0
        or gates.get('startup_authorized') is not False
        or gates.get('provider_access_authorized') is not False
        or gates.get('simulated_orders_authorized') is not False):
        raise ValueError('ATLAS_PREMARKET_FINANCIAL_NO_GO_EVIDENCE_CHANGED')

    output=StringIO()
    with redirect_stdout(output):
        code=probe_main(['--inspect'])
    if code!=0:
        raise ValueError('ATLAS_PREMARKET_IEX_OFFLINE_SCOPE_REFUSED')
    try:
        iex=json.loads(output.getvalue())
    except (ValueError,UnicodeError):
        raise ValueError('ATLAS_PREMARKET_IEX_INSPECT_MALFORMED') from None
    if (iex.get('status')!='REQUIRES_EXPLICIT_DATA_ONLY_SESSION_APPROVAL'
        or iex.get('selected_revision')!=12
        or iex.get('private_credentials_accessed') is not False
        or iex.get('provider_authentication_performed') is not False
        or iex.get('trading_authorized') is not False):
        raise ValueError('ATLAS_PREMARKET_IEX_OFFLINE_AUTHORITY_CHANGED')

    research=roster(offset=0,monitored_symbols=())
    if (research.get('requested_symbol_count')!=30
        or research.get('catalog_count')<10000
        or research.get('provider_connection_started') is not False
        or research.get('paper_execution_authorized') is not False
        or research.get('startup_authorized') is not False):
        raise ValueError('ATLAS_PREMARKET_RESEARCH_ROSTER_UNVERIFIED')

    simulation=[]
    for scenario in SCENARIOS:
        initial=run_demo(scenario=scenario)
        incremental=run_incremental_demo(scenario=scenario)
        if (initial.get('scenario')!=scenario or incremental.get('scenario')!=scenario
            or initial.get('data_source')!='SYNTHETIC'
            or incremental.get('data_source')!='SYNTHETIC'
            or initial.get('cash_reconciled') is not True
            or incremental.get('cash_reconciled') is not True
            or incremental.get('recovery_status')!='CLEAN'
            or incremental.get('open_positions')!=0
            or initial.get('forward_trading_authorized') is not False
            or incremental.get('forward_trading_authorized') is not False
            or initial.get('live_order_authorized') is not False
            or incremental.get('live_order_authorized') is not False):
            raise ValueError('ATLAS_PREMARKET_DISPOSABLE_V3_RECONCILIATION_REFUSED')
        simulation.append({'scenario':scenario,
                           'snapshot_and_incremental_cash_reconciled':True,
                           'incremental_recovery_clean':True,
                           'paper_execution_authorized':False})
    hl=hyperliquid()
    if (hl.get('schema')!='ATLAS_HYPERLIQUID_NATIVE_PREFLIGHT_V1'
        or hl.get('paper_startup_authorized') is not False
        or hl.get('live_trading_authorized') is not False
        or hl.get('hyperliquid_native_account_inception')!='NOT_INDEPENDENTLY_VERIFIED'
        or hl.get('provider_rights_and_current_market_data')!='NOT_INDEPENDENTLY_VERIFIED'):
        raise ValueError('ATLAS_PREMARKET_HYPERLIQUID_SCOPE_CHANGED')

    return {'schema':'ATLAS_NONFINANCIAL_PREMARKET_OFFLINE_QUALIFICATION_V1',
        'status':'OFFLINE_SIMULATIONS_PASS_FINANCIAL_PAPER_NO_GO',
        'selected_release':APP.name,'native_revision':12,
        'native_selected_readback_verified':True,
        'installed_application_deep_verified':deep,
        'quality_dips_disposable_scenarios':simulation,
        'alpaca_research_symbol_count':research['catalog_count'],
        'iex_roster_size':research['requested_symbol_count'],
        'iex_config_credentials_opened':False,
        'provider_connections_opened':False,
        'current_iex_quotes_verified':False,
        'forward_qd_source_accepted':False,
        'hyperliquid_native_account_accepted':False,
        'hyperliquid_provider_data_accepted':False,
        'stop_financial_owner_accepted':False,
        'kalshi_operational_scope_accepted':False,
        'financial_gates_accepted':0,
        'full_paper_production_ready':False,
        'startup_authorized':False,'paper_accounts_created':False,
        'paper_orders_authorized':False,'live_trading_authorized':False,
        'next_action':'Run the approved one-time data-only Alpaca IEX probe DURING regular stock-market hours; never use this offline report as a startup grant.'}


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--offline-only',action='store_true',required=True)
    p.add_argument('--deep',action='store_true')
    args=p.parse_args(argv)
    result=inspect(deep=args.deep)
    print(json.dumps(result,sort_keys=True,indent=2))
    return 2 # NO-GO is deliberate


if __name__=='__main__':
    raise SystemExit(main())
