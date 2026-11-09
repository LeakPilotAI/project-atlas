"""Selected r12 financial no-go audit. No providers, account creation or orders."""
import copy
import json
import subprocess
from pathlib import Path

import pytest

from scripts.observation_runtime import atlas_r12_financial_readiness as audit


def fixture():
    native={'status':'NATIVE_R12_CODE_SELECTED_NOT_FINANCIAL_PAPER',
       'revision':12,'selected_release':audit.APP.name,
       'native_record_pair_verified':True,'support_receipt_verified':True,
       'selected_clock_source_verified':True,'independent_proof_verified':True,
       'deep_application_verified':True,'financial_authority':False,
       'paper_accounts_authorized':False,'providers_authorized':False,
       'orders_authorized':False,'paper_start_authorized':False,
       'live_trading_authorized':False}
    qd={'schema':'ATLAS_QD_COMMISSIONING_PREFLIGHT_V1',
        'financial_mutations':False,'live_orders':False,
        'checks':[{'check':'OPERATIONAL_QD_SOURCE_PUBLICATION','status':'BLOCKED'},
                  {'check':'ACTIVATION_NATIVE_VERIFIED','status':'BLOCKED'},
                  {'check':'RUNTIME_AUTHORIZATION','status':'BLOCKED'}]}
    unified={'schema':'ATLAS_UNIFIED_PAPER_COMMISSIONING_PREFLIGHT_V1',
       'decision':'NO_GO','startup_authorized':False,'live_trading_authorized':False,
       'prerequisites':{'OPERATOR_SCOPE':'APPROVED_NON_ACTIVATING',
             'HYPERLIQUID_PROVIDER_RIGHTS_AND_DATA':'NOT_INDEPENDENTLY_VERIFIED',
             'CURRENT_EXECUTABLE_MARKET_PRICES':'NOT_INDEPENDENTLY_VERIFIED',
             'NATIVE_ACTIVATION':'BLOCKED','QD_FINANCIAL_INCEPTION':'BLOCKED',
             'HYPERLIQUID_NATIVE_ACCOUNT_INCEPTION':'NOT_INDEPENDENTLY_VERIFIED',
             'UNIFIED_OWNED_DESKTOP_STOP':'NOT_INDEPENDENTLY_VERIFIED',
             'QD_RUNTIME_AUTHORIZATION':'BLOCKED'}}
    return native,qd,unified


def test_nine_gates_are_read_only_and_not_treated_as_passed():
    result=audit.evaluate(*fixture())
    assert result['schema']=='ATLAS_SELECTED_R12_FINANCIAL_READINESS_ASSESSMENT_V1'
    assert result['selected_code_verified'] is True
    assert result['decision']=='NO_GO'
    assert result['accepted_financial_operating_gates']==0
    assert result['formal_acceptance_records_created']==0
    assert result['total_financial_workstreams']==9
    assert len(result['gates'])==9
    assert len({x['gate'] for x in result['gates']})==9
    assert all(x['accepted'] is False for x in result['gates'])
    assert all(x['next_evidence'] for x in result['gates'])
    assert result['startup_authorized'] is False
    assert result['provider_access_authorized'] is False
    assert result['simulated_orders_authorized'] is False
    assert result['live_trading_authorized'] is False
    assert result['financial_ledger_mutation'] is False


@pytest.mark.parametrize('field,value',[
   ('status','UNVERIFIED'),('revision',11),
   ('selected_release','af96bec0484a8e43f9965610e071a907a0d316bf'),
   ('native_record_pair_verified',False),('support_receipt_verified',False),
   ('selected_clock_source_verified',False),('independent_proof_verified',False),
   ('financial_authority',True),('paper_accounts_authorized',True),
   ('providers_authorized',True),('orders_authorized',True),
   ('paper_start_authorized',True),('live_trading_authorized',True)])
def test_native_selection_or_authority_changes_refuse(field,value):
    n,q,u=fixture();n[field]=value
    with pytest.raises(ValueError,match='R12_READINESS_SELECTED_CODE_IDENTITY_NOT_VERIFIED'):
        audit.evaluate(n,q,u)


def test_duplicate_or_malformed_qd_checks_refuse():
    n,q,u=fixture();q['checks'].append(q['checks'][0])
    with pytest.raises(ValueError,match='R12_READINESS_DUPLICATE_QD_CHECKS'):
        audit.evaluate(n,q,u)
    q['checks']=[{'check':'A','status':None}]
    with pytest.raises(ValueError,match='R12_READINESS_MALFORMED_QD_CHECKS'):
        audit.evaluate(n,q,u)


def test_unified_ready_or_live_trading_claim_does_not_auto_accept():
    n,q,u=fixture();u['decision']='GO'
    with pytest.raises(ValueError,match='R12_READINESS_UNIFIED_NONFINANCIAL_PREFLIGHT_REQUIRED'):
        audit.evaluate(n,q,u)
    n,q,u=fixture();u['startup_authorized']=True
    with pytest.raises(ValueError,match='R12_READINESS_UNIFIED_NONFINANCIAL_PREFLIGHT_REQUIRED'):
        audit.evaluate(n,q,u)
    n,q,u=fixture();q['financial_mutations']=True
    with pytest.raises(ValueError,match='R12_READINESS_QD_PREFLIGHT_NOT_NONFINANCIAL'):
        audit.evaluate(n,q,u)


def test_even_forged_passed_source_and_accounts_do_not_promote_nine_gates():
    n,q,u=fixture()
    for row in q['checks']:row['status']='PASS'
    for field in ('QD_FINANCIAL_INCEPTION','HYPERLIQUID_NATIVE_ACCOUNT_INCEPTION',
                  'QD_RUNTIME_AUTHORIZATION','NATIVE_ACTIVATION','UNIFIED_OWNED_DESKTOP_STOP'):
        u['prerequisites'][field]='PASS'
    out=audit.evaluate(n,q,u)
    assert out['accepted_financial_operating_gates']==0
    assert all(x['accepted'] is False for x in out['gates'])
    assert out['simulated_orders_authorized'] is False


def test_actual_r12_audit_process_refuses_start_and_reports_nine_gates():
    p=subprocess.run([str(audit.PY),'-B','-m',
       'scripts.observation_runtime.atlas_r12_financial_readiness'],
       cwd=audit.ROOT,capture_output=True,text=True,timeout=120)
    assert p.returncode==2,p.stderr
    value=json.loads(p.stdout)
    assert value['selected_code_verified'] is True
    assert value['native_revision']==12
    assert value['decision']=='NO_GO'
    assert value['accepted_financial_operating_gates']==0
    assert value['qd_source_clean'] is True
    assert value['startup_authorized'] is False
    assert not p.stderr
