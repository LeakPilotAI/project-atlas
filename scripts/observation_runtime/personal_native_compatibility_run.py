"""Source-prepared native fixture entry. --plan is inert;execution needs approval."""
import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path

REPO=Path(__file__).resolve().parents[2]
sys.dont_write_bytecode=True
sys.path[:0]=[str(REPO),str(REPO/'backend'),str(REPO/'tests')]

from scripts.observation_runtime.personal_native_scope import (
    AUTHORIZATION,
    ROOT,
    require_scope,
)

SCOPE_FILE=REPO/'docs/PERSONAL_NATIVE_V5_SOURCE_MANIFEST_REVIEW_2026-10-27.json'
SOURCE_FILES=(
    'scripts/observation_runtime/personal_native_job.py',
    'scripts/observation_runtime/personal_native_windows_api.py',
    'scripts/observation_runtime/personal_native_launch_contract.py',
    'tests/test_personal_native_cleanup_failure_offline.py',
    'tests/test_personal_native_failure_retention_offline.py',
    'tests/test_personal_native_job_behavior_offline.py',
    'tests/test_personal_native_job_cleanup_offline.py',
    'tests/test_personal_native_job_containment_offline.py',
    'tests/test_personal_native_job_ownership_offline.py',
    'tests/test_personal_native_launch_contract_offline.py',
    'tests/test_personal_native_live_handle_retention_offline.py',
    'tests/test_personal_native_windows_api_offline.py',
    'tests/test_personal_v5_manifest_review_pure.py',
    'scripts/observation_runtime/personal_native_scope.py',
    'scripts/observation_runtime/personal_native_compatibility_run.py',
    'scripts/observation_runtime/personal_paper_inception.py',
    'scripts/observation_runtime/quality_dips_one_time_publisher.py',
    'scripts/observation_runtime/native_fixture_budget.py',
    'scripts/observation_runtime/disposable_host_owner.py',
    'scripts/observation_runtime/quality_dips_read_service.py',
    'scripts/volume_inspector/windows_output.py',
    'scripts/volume_inspector/snapshot_store.py',
    'scripts/volume_inspector/financial_record_store.py',
    'scripts/volume_inspector/financial_reporting.py',
    'scripts/volume_inspector/operational_autonomous_store.py',
    'scripts/volume_inspector/operational_perp_store.py',
    'backend/app/services/personal_paper_runtime.py',
    'backend/app/services/personal_current_pins.py',
    'backend/app/services/personal_publication_custody.py',
    'backend/app/services/paper_financial_replay.py',
    'backend/app/services/paper_financial_audit.py',
    'backend/app/services/paper_daily_report.py',
    'backend/app/services/paper_perp_transition.py',
    'backend/app/services/quality_dips_autonomous_paper.py',
    'backend/app/services/quality_dips_autonomous_enrollment.py',
    'backend/app/services/perp_operational_contract.py',
    'backend/app/investment/quality_dips_operational_contract.py',
    'docs/ATLAS_PERSONAL_PAPER_RELEASE_POLICY.json',
    'tests/personal_native_compatibility_fixture.py',
    'tests/personal_native_compatibility_child.py',
    'tests/test_personal_native_compatibility.py',
    'tests/test_personal_paper_inception_memory.py',
    'tests/test_personal_paper_runtime.py',
    'tests/test_personal_session_reservation_integrity.py',
    'tests/test_quality_dips_autonomous_enrollment.py',
    'tests/test_paper_epoch_fixture.py',
    'tests/test_perp_financial_v2.py',
)


def verify_source_scope(scope,read=None):
    # Reproducibility check,not an authority issuer or account acceptance.
    if (scope.get('schema')!='ATLAS_PERSONAL_NATIVE_COMPATIBILITY_PROPOSAL_V1'
            or scope.get('authorization_required')!=AUTHORIZATION or scope.get('root')!=ROOT
            or scope.get('limits')!={'seconds':600,'entries':4096,'charged_bytes':134217728}
            or type(scope.get('source_files')) is not dict or set(scope['source_files'])!=set(SOURCE_FILES)):
        raise ValueError('NATIVE_SCOPE_SOURCE_BINDING_REQUIRED')
    read=read or (lambda name:(REPO/name).read_bytes())
    for name,expected in scope['source_files'].items():
        if type(expected) is not str or hashlib.sha256(read(name).replace(b'\r\n',b'\n')).hexdigest()!=expected:raise ValueError('NATIVE_SCOPE_SOURCE_CHANGED')


def plan():
    return {'schema':'PERSONAL_NATIVE_TEST_SCOPE_V1','authorization_required':AUTHORIZATION,
            'status':'PROPOSED_NOT_AUTHORIZED','root':ROOT,'seconds':600,'entries':4096,'bytes':134217728,
            'operational_accounts':False,'providers':False,'network_listeners':False,'genesis':False,
            'source_manifest':SCOPE_FILE.relative_to(REPO).as_posix(),'execution_ready':False,
            'test_file':'tests/test_personal_native_compatibility.py','cleanup':'REAP_EXACT_RETAINED_CHILDREN_KEEP_EVIDENCE_NO_RECURSIVE_DELETE'}


def require_operator_approval(approved_scope):
    """A separate operator decision is required before consuming V5."""
    approval_path = REPO / "docs/PERSONAL_NATIVE_COMPATIBILITY_OPERATOR_APPROVAL_V5.json"

    if not approval_path.is_file():
        raise ValueError("NATIVE_OPERATOR_APPROVAL_RECORD_REQUIRED")

    approval = json.loads(approval_path.read_text(encoding="utf8"))

    expected = {
        "schema": "ATLAS_NATIVE_OPERATOR_APPROVAL_V1",
        "authorization": AUTHORIZATION,
        "root": ROOT,
        "decision": "APPROVED_FOR_NATIVE_TESTS_ONLY",
        "financial_startup_authorized": False,
        "live_trading_authorized": False,
    }

    if approval != expected or approved_scope != AUTHORIZATION:
        raise ValueError("NATIVE_OPERATOR_APPROVAL_INVALID")


def execute(approved_scope):
    require_scope(approved_scope,ROOT)
    require_operator_approval(approved_scope)
    if os.name!='nt':raise ValueError('WINDOWS_NATIVE_TEST_ONLY')
    from scripts.observation_runtime.native_fixture_budget import create_session
    started=time.monotonic_ns()
    scope=json.loads(SCOPE_FILE.read_text(encoding='utf8'))
    verify_source_scope(scope)
    if scope.get('execution_ready') is not True:
        raise ValueError('NATIVE_CONTAINMENT_NOT_READY_FOR_EXECUTION')
    b=create_session(Path(ROOT),started_monotonic_ns=started,authorization=approved_scope)
    b.directory(b.root/'native');b.directory(b.root/'evidence')
    os.environ['ATLAS_PERSONAL_NATIVE_TEST_APPROVAL']=approved_scope
    from personal_native_compatibility_fixture import OwnedChild
    child=OwnedChild(['--suite'],seconds=480);result=child.finish()
    usage=b.usage();b.write(b.root/'evidence'/'session-finished.json',json.dumps({'child':result,'usage':usage,'financial_startup_authorized':False},indent=2).encode())
    print(json.dumps({'returncode':result['returncode'],'usage':b.usage(),'financial_startup_authorized':False}))
    return result['returncode']


def main(args=None):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--plan',action='store_true')
    parser.add_argument('--execute',action='store_true');parser.add_argument('--approved-scope')
    options=parser.parse_args(args)
    if options.plan and not options.execute and options.approved_scope is None:print(json.dumps(plan(),indent=2));return 0
    if not options.execute or options.plan or options.approved_scope!=AUTHORIZATION:raise ValueError('REFUSED_NO_EXPLICIT_OPERATOR_APPROVED_NATIVE_SCOPE')
    # Flag records the already received operator decision;it is not a permission
    # source,a financial trust root or an operational release authorization.
    return execute(options.approved_scope)


if __name__=='__main__':raise SystemExit(main())
