"""Inert native-run candidate contract. A plan cannot issue execution consent."""

import copy
import hashlib
import ntpath

from app.services.paper_financial_replay import body, strict
from scripts.observation_runtime.aip06_harness import BASE, LIMITS, ROOTS, SCOPE_HASH, need

REPO=ntpath.dirname(ntpath.dirname(BASE))
RUNTIME=ntpath.join(BASE,'qd-native-install-2e13e1d5b0f44498','candidate','python')
ENTRY=ntpath.join(REPO,'scripts','observation_runtime','aip06_acceptance_controller.py')
SCHEMA='AIP06_NATIVE_CANDIDATE_PLAN_V1'
EXCLUDED=('test_abrupt_process_exit_and_recovery_do_not_duplicate','test_abrupt_process_crash_recovery')


def schedule():
    """Proposed order and proof obligations, never invented case results."""
    obligations={
        'F01':('tests/test_unified_actual_native_lanes.py::test_actual_two_strategy_orders_fills_funding_partial_exits_and_shutdown','entry-partial-full-cuts-fees'),
        'F02':('tests/test_perp_native_shutdown.py::test_actual_native_stop_flattens_remaining_and_reconciles_session','maker-funding-margin-native-replay'),
        'F03':('tests/test_unified_actual_native_lanes.py::test_actual_qd_scanner_publication_refuses_incomplete_source','source-account-currency-isolation'),
        'F04':('tests/test_unified_actual_native_lanes.py::test_actual_native_global_reservation_race_is_one_pending_effect','one-effect-two-distinct-race-children'),
        'F05':(None,'native-hard-session-loss-refusal-no-write-other-account'),
        'F06':(None,'native-input-loss-stale-clock-provider-expiry-refusal'),
        'F07':('tests/test_qd_unified_shutdown.py::test_global_qd_stop_cannot_falsely_complete','missing-drain-identity-refuses-clean-stop'),
        'F08':('tests/test_unified_actual_native_lanes.py::test_global_native_ack_loss_refuses_replay_and_restart','unknown-ack-never-reapply'),
        'F09':(None,'interrupted-native-once-only-inception-exact-cuts'),
        'F10':('tests/test_unified_actual_native_lanes.py::test_real_child_crash_after_native_fill_before_order_and_global_ack','declared-exit71-original-handle-recovery'),
        'F11':(None,'actual-native-capacity-load-and-reserved-stop-not-mocked-headroom'),
        'F12':(None,'current-native-source-binding-and-producer-continuation-notification-contracts')}
    rows=[{'id':key,'source_case':case,'proof':proof,'status':'NATIVE_CASE_BINDING_PENDING' if case is None
           else 'SOURCE_CASE_IDENTIFIED_NATIVE_EXECUTION_PENDING','max_children':2 if key=='F04' else 1,
           'ack':'exact-account-operation-revision-native-source-projection-report-global',
           'on_failure':'PRESERVE_FIRST_FAILURE_CLEAN_OWNED_ONLY_ABORT_NO_RETRY'} for key,(case,proof) in obligations.items()]
    rows+= [{'id':'BOOTSTRAP-IPC-FAULTS','source_case':None,'proof':'missing-or-conflicting-escrow-bootstrap-ACK-credit-and-drain',
             'status':'NATIVE_FAULT_INJECTOR_BINDING_PENDING','max_children':2},
            {'id':'OWNERSHIP-PROBES','source_case':None,'proof':'current-supervisor-complete-roster-contained-unexpected-child-refusal',
             'status':'NATIVE_PROBE_BINDING_PENDING','max_children':2}]
    for sample in (1,2,3):
        rows.append({'id':f'STOP-{sample}','sample':sample,'root':ROOTS[f'S{sample}'],
          'source_case':f'tests/test_personal_owned_stop_timing.py::test_three_owned_native_shutdowns_include_exit_and_post_exit_readback[{sample}]',
          'max_children':1,'reader':'COLD_AFTER_ORIGINAL_WRITER_EXIT','deadline_ns':8*10**9,
          'cash':'1015.9136','revision':3,'status':'SOURCE_CASE_IDENTIFIED_NATIVE_EXECUTION_PENDING',
          'required':['ACK','DRAIN','RECONCILIATION','REPORT','DURABLE_READBACK','WRITER_EXIT','COLD_READER_EXIT',
                      'HANDLES_CLOSED','THREE_READERS_AGREE','FRESH_STRICT_PROCESS_SNAPSHOT','AGGREGATE_RELEASE']})
    return rows


def phase_budgets():
    # Proposed maximum envelopes, not predicted or measured performance.
    # Exhaustion is FAIL. All original inner bounds remain stricter where lower.
    return {'preflight_bootstrap':60,'financial_fault_groups':12*20,'bootstrap_ipc_faults':20,
            'ownership_probes':60,'three_ready_and_complete_stop':3*(40+8),'final_evidence':16,
            'reserved_cleanup':60}


def environment():
    return {'PYTHONDONTWRITEBYTECODE':'1','PYTHONNOUSERSITE':'1','PYTEST_DISABLE_PLUGIN_AUTOLOAD':'1',
            'PYTHONPATH':';'.join((ntpath.join(RUNTIME,'Lib','site-packages'),ntpath.join(REPO,'backend'),
                                 ntpath.join(REPO,'tests'),REPO)),
            'TEMP':ntpath.join(ROOTS['E'],'TEMP'),'TMP':ntpath.join(ROOTS['E'],'TEMP')}


def case_environment():
    return {'P':{'ATLAS_PERP_ORDER_TEST_ROOT':ROOTS['P'],'ATLAS_UNIFIED_QD_TEST_ROOT':ROOTS['Q']},
            'Q':{'ATLAS_AUTO_RUNTIME_ROOT':ROOTS['Q']},'F':{'ATLAS_D1_RUN_ROOT':ROOTS['F']},
            'N':{'ATLAS_PERSONAL_PIPELINE_TEST_ROOT':ROOTS['N']},
            'T':{'ATLAS_OWNED_STOP_TIMING_PARENT':ROOTS['T'],'ATLAS_OWNED_STOP_READER_MODE':'COLD'}}


def candidate_plan(*, source_pins, runtime_inventory, async_review):
    value={'schema':SCHEMA,'scope':SCOPE_HASH,'native_authority':False,'authorization':'PENDING',
       'entry':ENTRY,'working_directory':REPO,'executable':ntpath.join(RUNTIME,'python.exe'),
       'roots':dict(ROOTS),'limits':dict(LIMITS),'source_pins':copy.deepcopy(source_pins),
       'runtime_inventory':copy.deepcopy(runtime_inventory),'async_review':copy.deepcopy(async_review),
       'network':'DENY_SOCKET_BIND_CONNECT_EXTERNAL_DNS_PROVIDERS','environment':environment(),'case_environment':case_environment(),
       'excluded_native_launch_cases':list(EXCLUDED),'schedule':schedule(),'phase_budgets':phase_budgets(),
       'gates':{'B1':'BLOCKED_OUTER_OWNER_RETAINED_LAUNCH_BINDING_AND_NATIVE_GRADER_NOT_SUPPLIED',
                'B2':'RESOLVED_EXACT_PREDECLARED_RACE_COMMANDS_SOURCE_ONLY',
                'B3':'BLOCKED_DEFAULT_ASYNC_SOCKETPAIR_COMPATIBILITY',
                'B4':'BLOCKED_NATIVE_FAULT_INJECTOR_AND_ACTUAL_CAPACITY_BINDINGS',
                'B5':'BLOCKED_FRESH_NATIVE_IDENTITIES_ACLS_JOB_PROCESS_SOCKET_PREFLIGHT',
                'B6':'PENDING_FRESH_SINGLE_USE_OPERATOR_AUTHORIZATION'},
       'outer_owner':{'entry':ENTRY,'role':'outer-owner','controller_role':'controller',
           'required':['original-retained-controller-launch-handle','current-parent-creation-identity',
                       'complete-Job-roster','shared-budget-including-owner','finite-EOF-cleanup',
                       'independent-controller-exit-and-native-result-grade'],
           'binding':'NOT_IMPLEMENTED_NO_RAW_POPEN_FALLBACK'},
       'abort':'FIRST_FAILURE_NO_RETRY_OWNED_CLEANUP_ONLY_NO_OPERATIONAL_ROLLBACK'}
    validate_plan(value)
    return value


def validate_plan(value):
    need(type(value) is dict and set(value)=={'schema','scope','native_authority','authorization','entry','working_directory',
         'executable','roots','limits','source_pins','runtime_inventory','async_review','network','environment','case_environment',
         'excluded_native_launch_cases','schedule','phase_budgets','gates','outer_owner','abort'},'EXACT_NATIVE_PLAN_SCHEMA')
    need(value['schema']==SCHEMA and value['scope']==SCOPE_HASH and value['native_authority'] is False
         and value['authorization']=='PENDING','CANDIDATE_PLAN_NOT_EXECUTION_CONSENT')
    need(value['roots']==dict(ROOTS) and value['limits']==dict(LIMITS)
         and value['entry']==ENTRY and value['working_directory']==REPO
         and value['executable']==ntpath.join(RUNTIME,'python.exe'),'EXACT_NATIVE_PLAN_PATHS_AND_LIMITS')
    need(value['network']=='DENY_SOCKET_BIND_CONNECT_EXTERNAL_DNS_PROVIDERS'
         and value['excluded_native_launch_cases']==list(EXCLUDED) and value['schedule']==schedule(),
         'NO_SCHEDULE_GUARD_OR_EXCLUSION_WEAKENING')
    need(value['phase_budgets']==phase_budgets() and sum(value['phase_budgets'].values())==600,
         'NO_NATIVE_SESSION_DEADLINE_EXPANSION')
    pins=value['source_pins']
    need(type(pins) is dict and pins and ENTRY in pins and all(type(k) is str and k.startswith(REPO+chr(92))
         and ntpath.normpath(k)==k and type(v) is str and len(v)==64 and set(v)<=set('0123456789abcdef')
         for k,v in pins.items()),'EXPLICIT_NATIVE_SOURCE_PINS')
    inventory=value['runtime_inventory']
    need(type(inventory) is dict and set(inventory)=={'path','sha256','files','directories','read_bytes',
             'native_identity_accepted','complete_acl_accepted'}
         and type(inventory['path']) is str and inventory['path'].startswith(BASE+chr(92))
         and ntpath.normpath(inventory['path'])==inventory['path']
         and type(inventory['sha256']) is str and len(inventory['sha256'])==64
         and set(inventory['sha256'])<=set('0123456789abcdef')
         and all(type(inventory[k]) is int and inventory[k]>=0 for k in ('files','directories','read_bytes'))
         and 0<inventory['files']<=16000 and inventory['directories']<=16000 and inventory['read_bytes']<=1024**3
         and inventory['native_identity_accepted'] is False and inventory['complete_acl_accepted'] is False,
         'RUNTIME_BYTE_INVENTORY_NOT_NATIVE_IDENTITY_CLEARANCE')
    need(type(value['async_review']) is dict and value['async_review'].get('compatible') is False
         and value['async_review'].get('native_execution') is False,
         'SOURCE_ASYNC_REVIEW_CANNOT_GRANT_NATIVE_COMPATIBILITY')
    need(type(value['gates']) is dict and set(value['gates'])=={f'B{i}' for i in range(1,7)}
         and value['gates']['B6']=='PENDING_FRESH_SINGLE_USE_OPERATOR_AUTHORIZATION'
         and all(value['gates'][k].startswith('BLOCKED_') for k in ('B1','B3','B4','B5')),
         'UNRESOLVED_TECHNICAL_GATES_CANNOT_BE_ASSERTED_READY')
    need(type(value['outer_owner']) is dict and value['outer_owner'].get('binding')=='NOT_IMPLEMENTED_NO_RAW_POPEN_FALLBACK',
         'NO_UNVERIFIED_OUTER_OWNER')
    need(value['environment']==environment() and value['case_environment']==case_environment(),'EXACT_TEST_ENVIRONMENT')
    return copy.deepcopy(value)


def decode_plan(raw, expected_sha256):
    need(type(raw) is bytes and 0<len(raw)<=1024**2 and hashlib.sha256(raw).hexdigest()==expected_sha256,
         'NATIVE_PLAN_BYTES_OR_PIN_MISMATCH')
    value=strict(raw.decode('utf8'));need(body(value).encode()==raw,'CANONICAL_NATIVE_PLAN_BYTES')
    return validate_plan(value)


def require_execution_ready(value):
    validate_plan(value)
    # This prepared candidate deliberately has no authority-minting API or
    # generic native backend callback. Missing ownership/async/native evidence
    # cannot be bypassed with a JSON READY flag or an old grant.
    raise ValueError('TECHNICAL_PREREQUISITES_BLOCKED_NO_CONTROLLER_LAUNCH')
