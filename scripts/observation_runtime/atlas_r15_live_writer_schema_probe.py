"""Selected installed R15 live-process two-lane inception schema compatibility.

NONFINANCIAL: no activation, leases, real writer, source entitlement, trading,
or native account-file publication. Uses one bounded installed R15 Python
child, verifies all 12 ORIGINAL read-only Windows native root handles and
both exact 5/7 role rosters against THAT live self PID+creation FILETIME.
The deliberately synthetic acceptance string is never reusable: all handles
close and the observed process exits before returning its proof.
"""
import hashlib
import json
import ntpath
import os
import queue
import subprocess
import sys
import threading
import time
from pathlib import Path

from scripts.observation_runtime.atlas_r15_paper_offline_commissioning import (
    RELEASE, SELECTED_HEAD, selected_code,
)
from scripts.observation_runtime.atlas_r15_disposable_writer_process_audit import (
    EXECUTABLE, _windows_handle_identity,
)
from scripts.observation_runtime.atlas_r15_two_account_enrollment_handoff import (
    inspect as unapproved_handoff,
)
from scripts.observation_runtime.personal_existing_native_resource_evidence import (
    inspect_two_lane_native_roots,
)

SCHEMA = "ATLAS_R15_LIVE_SELF_TWO_LANE_NATIVE_SCHEMA_COMPATIBILITY_V1"
CHILD_SCHEMA = "ATLAS_R15_DISPOSABLE_REAL_PID_TWO_LANE_SCHEMA_CHECK_V1"
# Exactly one process, no process-pool, no long-running service.
CHILD = r'''
import copy
import inspect
import json
import os
import sys
import time
from contextlib import ExitStack
from pathlib import Path
from app.services.personal_paper_runtime import PROFILE, validate_policy
from app.services.quality_dips_autonomous_enrollment import WRITERS as QD_WRITERS
from app.services.perp_operational_contract import WRITERS as HL_WRITERS
from app.services.paper_financial_replay import digest
from scripts.observation_runtime.personal_paper_inception import (
    native_primitives, validate_personal_inception,
)
from scripts.observation_runtime.quality_dips_read_service import observe_self
from scripts.observation_runtime.personal_version_safe_release_clock import (
    require_native_version_safe_clock_source,
)
from scripts.observation_runtime import personal_paper_inception

data = json.loads(sys.argv[1])
if set(data) != {'proposal','roots','policy','expected_installed_root',
                  'selected_native_head','candidate_schema'}:
    raise ValueError('R15_LIVE_SCHEMA_EXACT_CHILD_INPUT_REQUIRED')
if data['candidate_schema'] != 'DISPOSABLE_CANNOT_ISSUE_FINANCIAL_AUTHORITY':
    raise ValueError('R15_LIVE_SCHEMA_FINANCIAL_AUTHORITY_REFUSED')
root = Path(data['expected_installed_root'])
if str(Path.cwd().resolve()).casefold() != str(root.resolve()).casefold():
    raise ValueError('R15_LIVE_SCHEMA_INSTALLED_CWD_REQUIRED')
source = Path(inspect.getfile(personal_paper_inception)).resolve()
if (not source.is_relative_to(root)
        or source != root / 'scripts/observation_runtime/personal_paper_inception.py'
        or require_native_version_safe_clock_source(deep=False)
           != data['selected_native_head']):
    raise ValueError('R15_LIVE_SCHEMA_AUTHENTIC_INSTALLED_SOURCE_REQUIRED')
policy = validate_policy(data['policy'])
proposal, roots = data['proposal'], data['roots']
if (proposal['account_enrollment_accepted'] is not False
        or proposal['both_financial_inceptions_published'] is not False
        or proposal['paper_start_authorized'] is not False
        or roots['all_twelve_distinct_and_empty'] is not True
        or set(proposal['accounts']) != {'QUALITY_DIPS','HYPERLIQUID'}
        or set(roots['lanes']) != {'QUALITY_DIPS','HYPERLIQUID'}):
    raise ValueError('R15_LIVE_SCHEMA_UNAPPROVED_BOTH_LANES_REQUIRED')
native = native_primitives()
process = observe_self()
native_process = {'schema':'QD_OP_PROCESS_ID_V1',**process}
observed = {}
with ExitStack() as held:
    ids = []
    for lane in ('QUALITY_DIPS','HYPERLIQUID'):
        row = proposal['accounts'][lane]
        n = copy.deepcopy(row['provisional_r15_native_enrollment_unaccepted'])
        manifest = copy.deepcopy(row['provisional_r15_parameters'])
        scope = copy.deepcopy(row['provisional_report_scope_unaccepted'])
        if n['writers'] is not None or n['acceptance_id'] is not None:
            raise ValueError('R15_LIVE_SCHEMA_NO_EXISTING_ENROLLMENT_REQUIRED')
        writers = QD_WRITERS if lane == 'QUALITY_DIPS' else HL_WRITERS
        if len(writers) != (5 if lane=='QUALITY_DIPS' else 7):
            raise ValueError('R15_LIVE_SCHEMA_ROLE_COUNTS_CHANGED')
        if set(n['resources']) != set(roots['lanes'][lane]['roots']):
            raise ValueError('R15_LIVE_SCHEMA_NATIVE_ROOT_SET_CHANGED')
        for role,resource in n['resources'].items():
            witness = roots['lanes'][lane]['roots'][role]
            if (resource['path'] != witness['path']
                    or resource['native_id'] != witness['native_id']
                    or not witness['native_identity_verified']
                    or not witness['existing_empty_namespace_verified']):
                raise ValueError('R15_LIVE_SCHEMA_ROOT_SOURCE_CONFLICT')
            path = Path(resource['path'])
            if not path.is_dir() or path.is_symlink() or path.is_junction() or any(path.iterdir()):
                raise ValueError('R15_LIVE_SCHEMA_EXISTING_EMPTY_ROOT_REQUIRED')
            out = held.enter_context(native.w.WindowsOutput(str(path)))
            native_id = native.native.file_identity(out.root_handle)
            if native_id != resource['native_id'] or any(path.iterdir()):
                raise ValueError('R15_LIVE_SCHEMA_ACTUAL_NATIVE_HANDLE_MISMATCH')
            ids.append(tuple(native_id))
        n['writers'] = {k:copy.deepcopy(native_process) for k in writers}
        # NOT an acceptable real enrollment: disposable identity and synthetic
        # ID. Any financial authority must independently reject this record.
        n['acceptance_id'] = 'EXPIRED_DISPOSABLE_NO_FINANCIAL_AUTHORITY'
        e = {'profile':PROFILE, 'personal_policy':copy.deepcopy(policy),
             'lane':lane,'native_enrollment':n,
             'parameters':manifest,'report_scope':scope}
        actual = validate_personal_inception(e)
        if (actual[0] != lane
                or set(actual[1]['writers']) != set(writers)
                or any(w != native_process for w in actual[1]['writers'].values())):
            raise ValueError('R15_LIVE_SCHEMA_CURRENT_PROCESS_ROSTER_REFUSED')
        observed[lane] = {'writer_roles':list(writers),
                          'candidate_only':True,
                          'account_id':n['account_id'],
                          'provisional_inception_digest':digest(manifest),
                          'native_resource_handles_held':6}
    if len(ids)!=12 or len(set(ids))!=12:
        raise ValueError('R15_LIVE_SCHEMA_NATIVE_IDENTITIES_NOT_DISTINCT')
    print(json.dumps({
        'schema':'ATLAS_R15_DISPOSABLE_REAL_PID_TWO_LANE_SCHEMA_CHECK_V1',
        'selected_native_head':data['selected_native_head'],
        'installed_module':str(source),
        'installed_process':process,
        'lanes':observed,
        'native_read_only_root_handles_open':12,
        'synthetic_acceptance_not_valid_for_any_financial_writer':True,
        'native_financial_files_created':0,
        'provider_calls':0,
        'writer_ownership_lease_issued':False,
        'paper_start_authorized':False,
        'live_trading_authorized':False,
    },sort_keys=True),flush=True)
    # Stay alive briefly with all native handles retained so an independent
    # parent can verify the SAME PROCESS HANDLE, then exit and close handles.
    time.sleep(2.5)
'''


def verify_live_child(child, *, parent, native_pid, native_head=SELECTED_HEAD,
                      release=RELEASE, proposal=None):
    if (type(child) is not dict
            or set(child) != {
                'schema','selected_native_head','installed_module',
                'installed_process','lanes','native_read_only_root_handles_open',
                'synthetic_acceptance_not_valid_for_any_financial_writer',
                'native_financial_files_created','provider_calls',
                'writer_ownership_lease_issued','paper_start_authorized',
                'live_trading_authorized'}
            or child['schema'] != CHILD_SCHEMA
            or child['selected_native_head'] != native_head
            or ntpath.normcase(ntpath.normpath(child['installed_module'])) !=
               ntpath.normcase(ntpath.normpath(str(
                   Path(release)/'scripts/observation_runtime/personal_paper_inception.py')))
            or child['native_read_only_root_handles_open'] != 12
            or child['synthetic_acceptance_not_valid_for_any_financial_writer'] is not True
            or child['native_financial_files_created'] != 0
            or child['provider_calls'] != 0
            or any(child[k] is not False for k in (
                'writer_ownership_lease_issued','paper_start_authorized',
                'live_trading_authorized'))):
        raise ValueError('R15_LIVE_SCHEMA_EXACT_NONFINANCIAL_RESULT_REQUIRED')
    identity=child['installed_process']
    expected=str(Path(release)/'python/python.exe')
    if (type(identity) is not dict or set(identity) !=
            {'pid','creation_filetime','image'}
            or type(native_pid) is not int or native_pid <= 0
            or type(parent) is not dict
            or type(parent.get('creation_filetime')) is not int
            or parent['creation_filetime'] <= 0
            or type(identity['pid']) is not int or identity['pid'] != native_pid
            or type(identity['creation_filetime']) is not int
            or identity['creation_filetime'] != parent['creation_filetime']
            or ntpath.normcase(ntpath.normpath(identity['image'])) !=
               ntpath.normcase(ntpath.normpath(parent.get('image','')))
            or ntpath.normcase(ntpath.normpath(identity['image'])) !=
               ntpath.normcase(ntpath.normpath(expected))):
        raise ValueError('R15_LIVE_SCHEMA_NATIVE_PROCESS_INCARCATION_REFUSED')
    from app.services.quality_dips_autonomous_enrollment import WRITERS as QD
    from app.services.perp_operational_contract import WRITERS as HL
    from app.services.paper_financial_replay import digest
    if (type(proposal) is not dict or proposal.get('account_enrollment_accepted') is not False
            or type(child['lanes']) is not dict
            or set(child['lanes']) != {'QUALITY_DIPS','HYPERLIQUID'}):
        raise ValueError('R15_LIVE_SCHEMA_TWO_LANE_PROPOSAL_REFUSED')
    for lane,roles in (('QUALITY_DIPS',QD),('HYPERLIQUID',HL)):
        item=child['lanes'][lane]
        source=proposal['accounts'][lane]
        if (type(item) is not dict or set(item) != {
                'writer_roles','candidate_only','account_id',
                'provisional_inception_digest','native_resource_handles_held'}
                or item['writer_roles'] != list(roles)
                or item['candidate_only'] is not True
                or item['account_id'] != source[
                    'provisional_r15_native_enrollment_unaccepted']['account_id']
                or item['provisional_inception_digest'] != digest(
                    source['provisional_r15_parameters'])
                or item['native_resource_handles_held'] != 6):
            raise ValueError('R15_LIVE_SCHEMA_EXACT_LANE_WRITER_ROSTER_REFUSED')
    return {'schema':SCHEMA,'status':'ACTUAL_INSTALLED_R15_LIVE_SCHEMA_COMPATIBILITY_ONLY',
            'installed_child_pid_expired_after_check':native_pid,
            'installed_child_filetime_expired_after_check':identity['creation_filetime'],
            'native_original_12_root_handles_held':12,
            'quality_dips_writer_roles_schema_compatible':len(QD),
            'hyperliquid_writer_roles_schema_compatible':len(HL),
            'actual_live_process_parent_child_handle_identity_agreed':True,
            'existing_financial_account_native_root_files_created':0,
            'operational_writer_enrolled':False,'operational_ownership_lease_issued':False,
            'native_account_inception_published':False,'paper_start_authorized':False,
            'real_money_orders_authorized':False,'provider_requests':0}


def inspect():
    if os.name!='nt' or sys.platform!='win32':
        raise ValueError('R15_LIVE_SCHEMA_WINDOWS_ONLY')
    before=selected_code()
    if (before['revision']!=14
            or before['selected_native_head']!=SELECTED_HEAD
            or before['financial_authority'] is not False
            or not EXECUTABLE.is_file() or EXECUTABLE.is_symlink()):
        raise ValueError('R15_LIVE_SCHEMA_SELECTED_INSTALLED_RELEASE_REFUSED')
    from pathlib import Path
    policy_path=Path(__file__).resolve().parents[2]/'docs/ATLAS_PERSONAL_PAPER_RELEASE_POLICY.json'
    policy=json.loads(policy_path.read_text(encoding='utf-8-sig'))
    proposal=unapproved_handoff()
    roots_before=inspect_two_lane_native_roots()
    data={'proposal':proposal,'roots':roots_before,'policy':policy,
          'expected_installed_root':str(RELEASE),
          'selected_native_head':SELECTED_HEAD,
          'candidate_schema':'DISPOSABLE_CANNOT_ISSUE_FINANCIAL_AUTHORITY'}
    args=json.dumps(data,sort_keys=True,separators=(',',':'))
    if len(args)>27000:raise ValueError('R15_LIVE_SCHEMA_ARGV_LIMIT_REFUSED')
    proc=None
    try:
        env={key:os.environ[key] for key in (
            'SystemRoot','WINDIR','TEMP','TMP','PATH')}
        env['PYTHONPATH']=';'.join([str(RELEASE),str(RELEASE/'backend')])
        env['PYTHONDONTWRITEBYTECODE']='1'
        proc=subprocess.Popen(
            [str(EXECUTABLE),'-B','-u','-c',CHILD,args],
            cwd=str(RELEASE),env=env,
            stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
            text=True,encoding='utf-8')
        q=queue.Queue(maxsize=1)
        def read_one():
            try:q.put(('value',proc.stdout.readline()))
            except Exception as ex:q.put(('exception',ex))
        reader=threading.Thread(target=read_one,daemon=True)
        reader.start()
        kind,value=q.get(timeout=9)
        reader.join(timeout=.2)
        if kind!='value' or not value or not value.startswith('{'):
            raise ValueError('R15_LIVE_SCHEMA_CHILD_READY_REFUSED')
        samples=[]
        for _ in range(3):
            if proc.poll() is not None:
                raise ValueError('R15_LIVE_SCHEMA_CHILD_EXITED_BEFORE_PARENT_IDENTITY')
            samples.append(_windows_handle_identity(proc._handle))
            time.sleep(.18)
        if any(s!=samples[0] for s in samples[1:]):
            raise ValueError('R15_LIVE_SCHEMA_PARENT_PROCESS_IDENTITY_CHANGED')
        result=verify_live_child(
            json.loads(value),parent=samples[0],native_pid=proc.pid,
            proposal=proposal)
        # The child is explicitly disposable: it must exit normally and
        # release all Windows handles before any result can leave this module.
        stdout,stderr=proc.communicate(timeout=10)
        if proc.returncode!=0 or stderr.strip() or stdout.strip():
            raise ValueError('R15_LIVE_SCHEMA_CHILD_END_OR_OUTPUT_REFUSED')
        if selected_code()!=before or inspect_two_lane_native_roots()!=roots_before:
            raise ValueError('R15_LIVE_SCHEMA_RELEASE_OR_ACCOUNTS_CHANGED')
        result['disposable_child_exited_and_closed_all_native_handles']=True
        result['selector_unchanged_after_child_exit']=True
        return result
    finally:
        if proc is not None:
            if proc.poll() is None:
                proc.kill()
                proc.communicate(timeout=5)
            if proc.stdout is not None:proc.stdout.close()
            if proc.stderr is not None:proc.stderr.close()


if __name__=='__main__':
    print(json.dumps(inspect(),sort_keys=True))
