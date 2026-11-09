"""Read-only version-safe nonfinancial code-install proposal admission and refusals."""
import copy
import hashlib
import json
from pathlib import Path

import pytest

from scripts.build_release_candidate import verify_candidate
from scripts.native_install_plan import prepare_install_inputs
from scripts import install_verified_release as installer

ROOT=Path(__file__).resolve().parents[1]
P=ROOT/'docs/ATLAS_VERSION_SAFE_CODE_ONLY_INSTALL_PROPOSAL_R1_2026-11-09.json'
PROPOSAL_SHA='539d8619fc52ca724762b38d4675292a38a72a29df3a0a4aa531358d8f62aa36'


def proposal():
    assert hashlib.sha256(P.read_bytes()).hexdigest()==PROPOSAL_SHA
    return json.loads(P.read_bytes())


def test_native_code_install_proposal_is_review_only_and_denied_by_existing_adapter():
    p=proposal()
    assert p['schema']=='ATLAS_VERSION_SAFE_NONFINANCIAL_CODE_INSTALL_REVIEW_V1'
    assert p['status']=='DESIGN_NOT_PERMISSION'
    assert p['release_installer_currently_allows_this_candidate'] is False
    assert p['future_version_pinned_installer_required'] is True
    assert p['independent_installed_runtime_readback_required'] is True
    for key in ('native_code_install_authorized','selection_authorized',
                'paper_account_inception_authorized','provider_connections_authorized',
                'simulated_trading_authorized','live_trading_authorized',
                'approval_record_present','execution_attempted'):
        assert p[key] is False
    assert p['candidate']['source_commit'] not in (
        installer.INDEPENDENT_NTP_CODE_INSTALL_SOURCE_COMMIT,
        installer.INDEPENDENT_NTP_CODE_INSTALL_V8_SOURCE_COMMIT)
    with pytest.raises(ValueError,match='UNSELECTED_CODE_SCOPE_REQUIRED'):
        installer.validate_proposal(p)


def test_exact_archive_dependency_and_plan_hashes_pass_source_only():
    p=proposal();c=p['candidate'];d=p['dependencies']; n=p['native_plan']
    assert verify_candidate(c['archive_path'], expected_sha256=c['archive_sha256'])['source_files']==1008
    assert hashlib.sha256(Path(c['selection_inventory_path']).read_bytes()).hexdigest()==c['selection_sha256']
    assert hashlib.sha256(Path(d['receipt_path']).read_bytes()).hexdigest()==d['receipt_file_sha256']
    assert hashlib.sha256(Path(d['native_source_physical_receipt_path']).read_bytes()).hexdigest()==d['native_source_physical_receipt_sha256']
    physical=json.loads(Path(d['native_source_physical_receipt_path']).read_bytes())
    assert physical['status']=='PHYSICAL_FILE_ID_CONTENT_NAMESPACE_VERIFIED'
    assert physical['source_image_self_execution_verified'] is False
    assert physical['native_file_handles_after_close']==0
    assert physical['native_directory_handles_after_close']==0
    receipt=json.loads(Path(d['receipt_path']).read_bytes())
    plan=prepare_install_inputs(archive=c['archive_path'],archive_sha256=c['archive_sha256'],
        source_commit=c['source_commit'],inventory_digest=c['inventory_sha256'],
        dependency_receipt=receipt,dependency_digest=d['full_source_inventory_sha256'],
        require_tracked=True)
    assert len(plan['runtime'])==c['source_files']==1008
    assert len(plan['dependencies'])==d['python_files']==9566
    assert len(plan['names'])==n['files']==10574
    assert len(plan['directories'])+1==n['directories']==914
    assert plan['total']==n['bytes']==265175432
    python_rows=sorted(plan['dependencies'].values(),key=lambda row:row['path'])
    assert hashlib.sha256(json.dumps(python_rows,sort_keys=True,separators=(',',':')).encode()).hexdigest()==d['python_inventory_sha256']
    assert not Path(n['destination']).exists()
    assert not Path(n['receipt_path']).exists()
    assert not Path(n['receipt_path']).with_suffix('.pending.jsonl').exists()


@pytest.mark.parametrize('fault',('archive','inventory','dependency','source'))
def test_tampered_candidate_or_dependency_refuses_without_native_effect(fault):
    p=proposal();c=p['candidate'];d=p['dependencies']
    receipt=json.loads(Path(d['receipt_path']).read_bytes())
    args=dict(archive=c['archive_path'],archive_sha256=c['archive_sha256'],
        source_commit=c['source_commit'],inventory_digest=c['inventory_sha256'],
        dependency_receipt=receipt,dependency_digest=d['full_source_inventory_sha256'],
        require_tracked=True)
    if fault=='archive':args['archive_sha256']='0'*64
    elif fault=='inventory':args['inventory_digest']='0'*64
    elif fault=='dependency':args['dependency_digest']='0'*64
    elif fault=='source':args['source_commit']='a'*40
    with pytest.raises(ValueError):prepare_install_inputs(**args)
    assert not Path(p['native_plan']['destination']).exists()


def test_cannot_reuse_historical_v8_installer_proposal_or_selection():
    p=proposal(); n=p['native_plan']; c=p['candidate']
    assert n['previous_selected_revision']==11
    assert n['previous_selected_head']=='933482b46a31af43270a193a94a83353e945fbecc4eb4661e8b7f8e9c8262997'
    assert n['r12_absent_at_review'] is True
    import json as _json
    r11=_json.loads(Path('D:/AtlasRuntime/selection/r0011.json').read_bytes())['record']
    from scripts.release_selection import digest
    assert digest(r11)==n['previous_selected_head']
    assert r11['selected']['release']!=c['source_commit']
    assert not Path('D:/AtlasRuntime/selection/r0012.json').exists()
