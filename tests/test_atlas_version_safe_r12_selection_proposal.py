"""R12 version-safe nonfinancial selector proposal is native-read-only and fail closed."""
import copy
import hashlib
import json
import subprocess
from pathlib import Path

import pytest

from scripts import atlas_version_safe_r12_selection_proposal as p
from scripts.release_selection import digest,validate_spec

ROOT=Path(__file__).resolve().parents[1]


def native_records():
    # Test input from real native selector history; file namespace is not modified.
    return [json.loads((p.SEL/f'r{i:04d}.json').read_bytes())['record']
            for i in range(1,12)]


def test_actual_installed_python_native_readonly_preview_and_no_selection():
    proc=subprocess.run([str(p.APP/'python/python.exe'),'-I','-B','-S',
        str(Path(p.__file__)),'--inspect'],text=True,capture_output=True,timeout=120)
    assert proc.returncode==0,proc.stderr
    obj=json.loads(proc.stdout)
    assert obj['status']=='READY_FOR_SEPARATE_OPERATOR_REVIEW_NOT_AUTHORIZED'
    assert obj['revision']==12
    assert obj['operation']=='08ca065b488c6e1748976aeb251939c3'
    assert obj['proposed_head']=='f4cf83bb1e98ecb7cfa3be37fe27e80a79b339dc26f73358a1702349b47958fd'
    assert obj['predecessor_records_verified']==11
    assert obj['installed_clock_source_match'] is True
    assert obj['support_receipt_verified'] is True
    assert obj['r12_published'] is False
    assert obj['code_selection_authorized'] is False
    assert obj['financial_authority'] is False
    assert not (p.SEL/'r0012.json').exists()
    assert not (p.SEL/'r0012.pending').exists()


def test_no_workspace_python_may_admit_operational_selection():
    with pytest.raises(ValueError,match='ATLAS_R12_INSTALLED_ISOLATED_PYTHON_REQUIRED'):
        p.installed_context()


def test_complete_native_r11_history_links_and_operation_uniqueness():
    rows=native_records()
    ids=p.validated_chain(rows,digest,validate_spec)
    assert len(rows)==len(ids)==11
    assert digest(rows[-1])==p.R11_HEAD
    assert rows[-1]['selected']['release']==p.V7
    assert rows[-1]['revision']==11


@pytest.mark.parametrize('tamper,match',[
    ('missing','ATLAS_R12_EXACT_11_PREDECESSORS_REQUIRED'),
    ('duplicate_operation','ATLAS_R12_HISTORICAL_NATIVE_CHAIN_INVALID'),
    ('head','ATLAS_R12_HISTORICAL_NATIVE_CHAIN_INVALID'),
    ('wrong_previous','ATLAS_R12_HISTORICAL_NATIVE_CHAIN_INVALID'),
    ('wrong_release','SELECTION_FOREIGN_OPERATIONAL_PATH'),
    ('invalid_action','ATLAS_R12_HISTORICAL_NATIVE_CHAIN_INVALID'),
    ('wrong_revision','ATLAS_R12_HISTORICAL_NATIVE_CHAIN_INVALID'),
    ('wrong_restore','ATLAS_R12_HISTORICAL_RESTORE_INVALID'),
])
def test_wrong_predecessor_chain_fails_before_native_publication(tamper,match):
    rows=copy.deepcopy(native_records())
    if tamper=='missing':rows.pop()
    elif tamper=='duplicate_operation':rows[-1]['operation']=rows[0]['operation']
    elif tamper=='head':rows[1]['operation']='a'*32
    elif tamper=='wrong_previous':rows[2]['previous']='f'*64
    elif tamper=='wrong_release':rows[-1]['selected']['release']=p.RELEASE
    elif tamper=='invalid_action':rows[-1]['action']='APPROVE'
    elif tamper=='wrong_revision':rows[-1]['revision']=99
    else:
        for row in rows:
            if row['action']=='ROLLBACK':
                row['restores']='f'*64
                break
        else:
            pytest.skip('Native V7 history contained no rollback for this test')
    with pytest.raises(ValueError,match=match):
        p.validated_chain(rows,digest,validate_spec)
    assert not (p.SEL/'r0012.json').exists()


def test_broken_support_status_hash_refuses_before_native_files(monkeypatch):
    monkeypatch.setattr(p,'SUPPORT_STATUS_PIN','0'*64)
    with pytest.raises(ValueError,match='ATLAS_R12_SUPPORT_STATUS_SOURCE_CHANGED'):
        p.check_external_support()


def test_unreviewed_support_status_hash_refuses_before_import(monkeypatch):
    monkeypatch.setattr(p,'SUPPORT_STATUS_PIN',None)
    with pytest.raises(ValueError,match='ATLAS_R12_SUPPORT_STATUS_PIN_NOT_REVIEWED'):
        p.check_external_support()


def test_r12_selected_target_spec_pinned_to_real_immutable_app():
    spec={'schema':'QD_INSTALLED_RELEASE_REFERENCE_V1','domain':'WINDOWS_LOCAL',
          'release':p.RELEASE,'root':str(p.APP),
          'receipt':str(p.APP_RECEIPT),'receipt_sha256':p.APP_SHA,
          'artifact_digest':p.ARTIFACT}
    assert validate_spec(spec,'WINDOWS_LOCAL')==spec
    assert hashlib.sha256(p.APP_RECEIPT.read_bytes()).hexdigest()==p.APP_SHA
    assert hashlib.sha256((p.SUPPORT_ROOT/'receipt.json').read_bytes()).hexdigest()==p.SUPPORT_RECEIPT_SHA
    assert p.SUPPORT_ROOT.is_dir() and p.SUPPORT_LAUNCHER.is_dir()
    assert not (p.SEL/'r0012.json').exists()


def test_review_only_source_has_no_publish_capability():
    source=Path(p.__file__).read_text(encoding='utf-8')
    assert 'NativeInstalledReleaseVerifier().open(target)' in source
    assert 'admit_version_safe_clock_source(' in source
    assert 'store.records()' in source
    assert 'store.publish(' not in source
    assert '.change(' not in source
    assert 'IndependentNtpClock(' not in source
    assert 'operator_approval_record_present' in source
    assert "'code_selection_authorized':False" in source
    assert "'financial_accounts_authorized':False" in source
    assert "'simulated_orders_authorized':False" in source
    assert not (p.SEL/'r0012.json').exists()


def test_create_only_r12_review_is_exact_pinned_nonfinancial_artifact():
    raw=p.REVIEW.read_bytes()
    assert hashlib.sha256(raw).hexdigest()==(
        '6bf4567c4a196b801f0effa3fc74d3292e96ea2a94094cafc19f006e5ed73588')
    value=json.loads(raw)
    assert value['schema']=='ATLAS_VERSION_SAFE_R12_NONFINANCIAL_SELECTION_REVIEW_V1'
    assert value['status']=='READY_FOR_SEPARATE_OPERATOR_REVIEW_NOT_AUTHORIZED'
    assert value['predecessor_head']==p.R11_HEAD
    assert value['predecessor_selected_release']==p.V7
    assert value['predecessor_records_verified']==11
    assert value['proposed_revision']==12
    assert value['row']['revision']==12
    assert value['row']['previous']==p.R11_HEAD
    assert value['row']['operation']=='08ca065b488c6e1748976aeb251939c3'
    assert value['row']['selected']['release']==p.RELEASE
    assert value['row']['selected']['receipt_sha256']==p.APP_SHA
    assert value['row']['selected']['artifact_digest']==p.ARTIFACT
    assert value['proposed_head']==digest(value['row'])
    assert value['proposed_head']=='f4cf83bb1e98ecb7cfa3be37fe27e80a79b339dc26f73358a1702349b47958fd'
    assert value['support_receipt_sha256']==p.SUPPORT_RECEIPT_SHA
    assert value['support_manifest_sha256']==p.SUPPORT_MANIFEST_SHA
    assert value['installed_clock_source_match'] is True
    assert value['clock_profile']==p.PROFILE
    for flag in ('operator_approval_record_present','r12_published','code_selection_authorized',
                 'financial_accounts_authorized','providers_authorized',
                 'paper_start_authorized','simulated_orders_authorized',
                 'live_trading_authorized'):
        assert value[flag] is False
    assert not (p.SEL/'r0012.json').exists()
    assert not (p.SEL/'r0012.pending').exists()


def test_proposed_synthetic_r12_matches_frozen_installed_clock_binding():
    from scripts.observation_runtime.personal_version_safe_release_clock import admit_version_safe_clock_source
    row=json.loads(p.REVIEW.read_bytes())['row']
    source=p.APP/'scripts/observation_runtime/personal_version_safe_release_clock.py'
    head,spec=admit_version_safe_clock_source(source_file=source,
                                               records=[*native_records(),row])
    assert head==digest(row)
    assert spec['release']==p.RELEASE
    assert spec['artifact_digest']==p.ARTIFACT
    assert not (p.SEL/'r0012.json').exists()


def test_changed_synthetic_r12_does_not_admit_installed_clock():
    from scripts.observation_runtime.personal_version_safe_release_clock import admit_version_safe_clock_source
    original=json.loads(p.REVIEW.read_bytes())['row']
    bad=copy.deepcopy(original)
    bad['selected']['receipt_sha256']='f'*64
    source=p.APP/'scripts/observation_runtime/personal_version_safe_release_clock.py'
    # Pure installed-clock source accepts only structural selection; it does NOT
    # verify the artifact digest/receipt until independent native open().
    _,spec=admit_version_safe_clock_source(source_file=source,
                                           records=[*native_records(),bad])
    assert spec['receipt_sha256']=='f'*64
    assert not (p.SEL/'r0012.json').exists()
