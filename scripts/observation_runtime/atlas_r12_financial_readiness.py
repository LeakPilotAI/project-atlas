"""Read-only financial readiness for SELECTED native r12, not PAPER authority.

Use actual selected native Python verification plus existing QD/HL evidence.
The 9 workstreams are an operational audit; no new formal acceptance grant.
Never connects providers, creates accounts, submits orders or starts services.
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT=Path(r'D:\Work\Project Atlas')
APP=Path('D:/AtlasRuntime/releases/2d4879878bf58bea5a3ed0a986b809791f638fec')
STATUS=ROOT/'scripts/atlas_version_safe_r12_selected_status.py'
PY=ROOT/'backend/.venv/Scripts/python.exe'


def checks(rows):
    if not isinstance(rows,list) or any(type(x) is not dict or
        type(x.get('check')) is not str or type(x.get('status')) is not str for x in rows):
        raise ValueError('R12_READINESS_MALFORMED_QD_CHECKS')
    names=[x['check'] for x in rows]
    if len(set(names))!=len(names):raise ValueError('R12_READINESS_DUPLICATE_QD_CHECKS')
    return {x['check']:x['status'] for x in rows}


def evaluate(native,qd,unified):
    """Pure, conservative evaluation: missing acceptance evidence is BLOCKED."""
    if (native.get('status')!='NATIVE_R12_CODE_SELECTED_NOT_FINANCIAL_PAPER'
        or native.get('revision')!=12
        or native.get('selected_release')!=APP.name
        or native.get('native_record_pair_verified') is not True
        or native.get('support_receipt_verified') is not True
        or native.get('selected_clock_source_verified') is not True
        or native.get('independent_proof_verified') is not True
        or any(native.get(k) is not False for k in (
           'financial_authority','paper_accounts_authorized','providers_authorized',
           'orders_authorized','paper_start_authorized','live_trading_authorized'))):
        raise ValueError('R12_READINESS_SELECTED_CODE_IDENTITY_NOT_VERIFIED')
    if qd.get('schema')!='ATLAS_QD_COMMISSIONING_PREFLIGHT_V1' or qd.get('financial_mutations') is not False or qd.get('live_orders') is not False:
        raise ValueError('R12_READINESS_QD_PREFLIGHT_NOT_NONFINANCIAL')
    q=checks(qd.get('checks'))
    if unified.get('schema')!='ATLAS_UNIFIED_PAPER_COMMISSIONING_PREFLIGHT_V1' or unified.get('decision')!='NO_GO' or unified.get('startup_authorized') is not False or unified.get('live_trading_authorized') is not False:
        raise ValueError('R12_READINESS_UNIFIED_NONFINANCIAL_PREFLIGHT_REQUIRED')
    u=unified.get('prerequisites')
    if type(u) is not dict or u.get('OPERATOR_SCOPE') not in ('APPROVED_NON_ACTIVATING','BLOCKED'):
        raise ValueError('R12_READINESS_UNIFIED_PREREQUISITES_INVALID')
    rows=[
       ('QD_FORWARD_SOURCE', 'OPERATIONAL_QD_SOURCE_PUBLICATION',q.get('OPERATIONAL_QD_SOURCE_PUBLICATION','BLOCKED'),
        'Accept a current operator-owned native QD forward publisher, custody, completeness and source rights'),
       ('QD_DATA_RIGHTS','QD_DATA_RIGHTS','NOT_INDEPENDENTLY_VERIFIED',
        'Validate Alpaca free IEX entitlement, supported Robinhood-listed universe, executable eligible quotes and venue constraints'),
       ('HYPERLIQUID_PROVIDER_AND_DATA','HYPERLIQUID_PROVIDER_RIGHTS_AND_DATA',u.get('HYPERLIQUID_PROVIDER_RIGHTS_AND_DATA','NOT_VERIFIED'),
        'Verify rights, independent current perp order books, funding and fee inputs without live orders'),
       ('CURRENT_EXECUTABLE_PRICES','CURRENT_EXECUTABLE_MARKET_PRICES',u.get('CURRENT_EXECUTABLE_MARKET_PRICES','NOT_VERIFIED'),
        'Independently qualify bid/ask, staleness, session rules, fees and slippage for all intended venues'),
       ('FINANCIAL_CLOCK_AND_STORAGE','FINANCIAL_CLOCK_OWNERSHIP','NOT_INDEPENDENTLY_VERIFIED',
        'Establish a separate continuous financial NTP lease and trusted native ledger/storage writer authority; r12 code-only NTP is not enough'),
       ('NATIVE_ACTIVATION','ACTIVATION_NATIVE_VERIFIED',u.get('NATIVE_ACTIVATION','BLOCKED'),
        'Commission and independently bind the native operator activation record after source/clock/custody acceptance'),
       ('DISTINCT_PAPER_ACCOUNTS','PAPER_FINANCIAL_INCEPTION',
        'PASS' if u.get('QD_FINANCIAL_INCEPTION')=='PASS' and u.get('HYPERLIQUID_NATIVE_ACCOUNT_INCEPTION')=='PASS' else 'NOT_INDEPENDENTLY_VERIFIED',
        'Create-once verify isolated QD USD and Hyperliquid USDC simulated accounts plus writer/drain ownership only after admission'),
       ('OWNED_STOP_FLATTEN','UNIFIED_OWNED_DESKTOP_STOP',u.get('UNIFIED_OWNED_DESKTOP_STOP','NOT_VERIFIED'),
        'Independently prove one-click Start/Stop, simulated flatten, durable logs and crash/restart recovery'),
       ('FORWARD_PAPER_RUNTIME_SOAK','QD_RUNTIME_AUTHORIZATION',u.get('QD_RUNTIME_AUTHORIZATION','BLOCKED'),
        'Accept continuous supervised PAPER sessions, Discord/read-only dashboard, reconciliation and multi-month results')]
    gates=[{'gate':a,'evidence':b,'observed':c,'accepted':False,'next_evidence':d} for a,b,c,d in rows]
    # These are workstreams, NOT formal acceptance decisions. Their flags can
    # only be promoted by a future separate native, provider and finance reviewer.
    assert len(gates)==9 and len({x['gate'] for x in gates})==9
    return {'schema':'ATLAS_SELECTED_R12_FINANCIAL_READINESS_ASSESSMENT_V1',
       'selected_release':APP.name,'native_revision':12,
       'selected_code_verified':True,'selected_code_is_financial_authority':False,
       'decision':'NO_GO','accepted_financial_operating_gates':0,
       'formal_acceptance_records_created':0,'total_financial_workstreams':9,
       'gates':gates,'startup_authorized':False,'provider_access_authorized':False,
       'simulated_orders_authorized':False,'live_trading_authorized':False,
       'financial_ledger_mutation':False,
       'warning':'Selected r12 and 180s nonfinancial NTP do NOT prove PAPER data, clock, writer, Stop or accounts; legacy V7-only clock diagnostic is excluded.'}


def run(*,deep=False):
    sha=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    native_cmd=[str(APP/'python/python.exe'),'-I','-B','-S',str(STATUS)]
    if deep:native_cmd.append('--deep')
    proc=subprocess.run(native_cmd,cwd=ROOT,capture_output=True,text=True,timeout=120)
    if proc.returncode!=0:raise ValueError('R12_READINESS_NATIVE_SELECTED_STATUS_REFUSED:'+proc.stderr[-260:])
    native=json.loads(proc.stdout)
    qd_cmd=[str(PY),'-B','-m','scripts.observation_runtime.personal_commissioning_preflight','--json','--expected-source',sha]
    proc=subprocess.run(qd_cmd,cwd=ROOT,capture_output=True,text=True,timeout=120)
    if proc.returncode not in (0,2):raise ValueError('R12_READINESS_QD_PREFLIGHT_REFUSED:'+proc.stderr[-260:])
    qd=json.loads(proc.stdout)
    sys.path.insert(0,str(ROOT))
    from scripts.observation_runtime.unified_paper_commissioning_preflight import inspect
    unified=inspect(qd_report=qd)
    data=evaluate(native,qd,unified)
    data['audited_git_source']=sha
    data['qd_source_clean']=checks(qd['checks']).get('TRACKED_SOURCE_UNCHANGED')=='PASS'
    data['independent_selected_app_deep_verification']=native.get('deep_application_verified') is True
    return data


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--deep',action='store_true')
    args=p.parse_args(argv)
    result=run(deep=args.deep)
    print(json.dumps(result,sort_keys=True,indent=2))
    return 2 # no-go has a distinct exit status: never imply startup-ready


if __name__=='__main__':
    raise SystemExit(main())
