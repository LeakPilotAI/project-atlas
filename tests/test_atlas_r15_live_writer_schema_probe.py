"""Selected installed R15 actual live self / 5+7 role schema; NO enrollment."""
import copy
import ntpath
import sys

import pytest

from app.services.paper_financial_replay import digest
from app.services.quality_dips_autonomous_enrollment import WRITERS as QD
from app.services.perp_operational_contract import WRITERS as HL
from scripts.observation_runtime import atlas_r15_live_writer_schema_probe as probe
from scripts.observation_runtime.atlas_r15_two_account_enrollment_handoff import (
    inspect as handoff,
)


def specimen():
    p=handoff()
    identity={'pid':7012,'creation_filetime':134388576100000000,
              'image':str(probe.EXECUTABLE)}
    parent={'creation_filetime':identity['creation_filetime'],
            'image':identity['image'],
            'pid_observed_by_parent_process_handle':None}
    child={
        'schema':probe.CHILD_SCHEMA,
        'selected_native_head':probe.SELECTED_HEAD,
        'installed_module':str(
            probe.RELEASE/'scripts/observation_runtime/personal_paper_inception.py'),
        'installed_process':identity,
        'lanes':{
            lane:{
                'writer_roles':list(roles),
                'candidate_only':True,
                'account_id':p['accounts'][lane][
                    'provisional_r15_native_enrollment_unaccepted']['account_id'],
                'provisional_inception_digest':digest(p['accounts'][lane][
                    'provisional_r15_parameters']),
                'native_resource_handles_held':6,
            } for lane,roles in (('QUALITY_DIPS',QD),('HYPERLIQUID',HL))
        },
        'native_read_only_root_handles_open':12,
        'synthetic_acceptance_not_valid_for_any_financial_writer':True,
        'native_financial_files_created':0,'provider_calls':0,
        'writer_ownership_lease_issued':False,
        'paper_start_authorized':False,'live_trading_authorized':False,
    }
    return {'child':child,'parent':parent,'native_pid':7012,'proposal':p}


def test_pure_live_native_roster_check_is_never_an_operational_enrollment():
    data=specimen()
    original=copy.deepcopy(data)
    result=probe.verify_live_child(**data)
    assert data==original
    assert result['schema']==probe.SCHEMA
    assert result['native_original_12_root_handles_held']==12
    assert result['quality_dips_writer_roles_schema_compatible']==5
    assert result['hyperliquid_writer_roles_schema_compatible']==7
    assert result['actual_live_process_parent_child_handle_identity_agreed'] is True
    assert result['operational_writer_enrolled'] is False
    assert result['operational_ownership_lease_issued'] is False
    assert result['native_account_inception_published'] is False
    assert result['paper_start_authorized'] is False
    assert result['real_money_orders_authorized'] is False
    assert result['provider_requests']==0


@pytest.mark.parametrize('damage',[
    'fake_schema','extra_approval_field','changed_selected_head',
    'wrong_installed_module','missing_module','missing_lane',
    'extra_lane','missing_qd_role','missing_hl_funding',
    'missing_hl_mark','extra_hl_role','qd_wrong_account',
    'hl_changed_digest','changed_handle_count','changed_lane_handle_count',
    'candidate_promoted','fake_financial_source_file',
    'pretend_provider_call','fake_ownership_lease','fake_paper_start',
    'fake_live_order','fake_synthetic_acceptance','expired_child_pid',
    'changed_child_filetime','changed_child_image','changed_parent_image',
    'changed_parent_filetime','bad_native_pid','bad_parent',
    'source_real_enrollment_pretend',
])
def test_real_r15_writer_schema_qualification_refuses_tamper(damage):
    data=specimen()
    c=data['child']
    q=c['lanes']['QUALITY_DIPS']
    h=c['lanes']['HYPERLIQUID']
    if damage=='fake_schema':c['schema']='FINANCIAL_ENROLLMENT'
    elif damage=='extra_approval_field':c['financial_approved']=True
    elif damage=='changed_selected_head':c['selected_native_head']='f'*64
    elif damage=='wrong_installed_module':c['installed_module']=r'D:\other\personal_paper_inception.py'
    elif damage=='missing_module':c.pop('installed_module')
    elif damage=='missing_lane':c['lanes'].pop('HYPERLIQUID')
    elif damage=='extra_lane':c['lanes']['KALSHI']={}
    elif damage=='missing_qd_role':q['writer_roles'].remove('source')
    elif damage=='missing_hl_funding':h['writer_roles'].remove('funding')
    elif damage=='missing_hl_mark':h['writer_roles'].remove('mark')
    elif damage=='extra_hl_role':h['writer_roles'].append('options')
    elif damage=='qd_wrong_account':q['account_id']='foreign'
    elif damage=='hl_changed_digest':h['provisional_inception_digest']='0'*64
    elif damage=='changed_handle_count':c['native_read_only_root_handles_open']=11
    elif damage=='changed_lane_handle_count':q['native_resource_handles_held']=7
    elif damage=='candidate_promoted':q['candidate_only']=False
    elif damage=='fake_financial_source_file':c['native_financial_files_created']=1
    elif damage=='pretend_provider_call':c['provider_calls']=1
    elif damage=='fake_ownership_lease':c['writer_ownership_lease_issued']=True
    elif damage=='fake_paper_start':c['paper_start_authorized']=True
    elif damage=='fake_live_order':c['live_trading_authorized']=True
    elif damage=='fake_synthetic_acceptance':c['synthetic_acceptance_not_valid_for_any_financial_writer']=False
    elif damage=='expired_child_pid':c['installed_process']['pid']=9999
    elif damage=='changed_child_filetime':c['installed_process']['creation_filetime']+=1
    elif damage=='changed_child_image':c['installed_process']['image']=r'D:\not-installed.exe'
    elif damage=='changed_parent_image':data['parent']['image']=r'D:\other.exe'
    elif damage=='changed_parent_filetime':data['parent']['creation_filetime']+=1
    elif damage=='bad_native_pid':data['native_pid']=0
    elif damage=='bad_parent':data['parent'].pop('creation_filetime')
    elif damage=='source_real_enrollment_pretend':
        data['proposal']['account_enrollment_accepted']=True
    with pytest.raises((ValueError,KeyError,TypeError)):
        probe.verify_live_child(**data)


@pytest.mark.skipif(sys.platform!='win32',reason='Real native Windows selected R15 process required')
def test_actual_installed_r15_self_holds_12_native_roots_and_validates_5_plus_7_roles():
    # Bounded actual installed R15 executable; confirmed dead before return.
    result=probe.inspect()
    assert result['schema']==probe.SCHEMA
    assert result['status']=='ACTUAL_INSTALLED_R15_LIVE_SCHEMA_COMPATIBILITY_ONLY'
    assert result['quality_dips_writer_roles_schema_compatible']==5
    assert result['hyperliquid_writer_roles_schema_compatible']==7
    assert result['native_original_12_root_handles_held']==12
    assert result['disposable_child_exited_and_closed_all_native_handles'] is True
    assert result['selector_unchanged_after_child_exit'] is True
    assert result['existing_financial_account_native_root_files_created']==0
    assert result['operational_writer_enrolled'] is False
    assert result['operational_ownership_lease_issued'] is False
    assert result['native_account_inception_published'] is False
    assert result['paper_start_authorized'] is False
