"""Verified one-shot unselected native release; read-only historical evidence."""
import hashlib
import json
from pathlib import Path

import pytest

from scripts import install_version_safe_candidate as installer

ROOT=Path(__file__).resolve().parents[1]
RUNTIME=Path('D:/AtlasRuntime/releases')/installer.SOURCE
RECEIPT=ROOT/'logs/diagnostics'/('qd-unselected-release-'+installer.SOURCE+'.json')
REPORT=ROOT/'logs/diagnostics/atlas-version-safe-independent-code-install-readback-20261109.json'
JOURNAL=RECEIPT.with_suffix('.pending.jsonl')


def test_genuine_native_receipt_and_separate_readback_are_pinned_unselected():
    status=installer.inspect_version_safe_code_only_status()
    assert status['status']=='INSTALLED_CODE_ONLY_UNSELECTED_RECEIPT_PINNED'
    assert status['independent_readback_recorded'] is True
    assert status['artifact_digest']==installer.INSTALLED_ARTIFACT_DIGEST
    assert status['receipt_sha256']==installer.INSTALLED_RECEIPT_SHA
    assert status['target_files']==10574
    assert status['financial_authority'] is False
    assert status['release_selection'] is False
    assert hashlib.sha256(RECEIPT.read_bytes()).hexdigest()==installer.INSTALLED_RECEIPT_SHA
    assert hashlib.sha256(REPORT.read_bytes()).hexdigest()==installer.INDEPENDENT_READBACK_SHA
    assert RUNTIME.is_dir() and JOURNAL.is_file()
    assert not Path('D:/AtlasRuntime/selection/r0012.json').exists()
    assert not Path('D:/AtlasRuntime/selection/r0012.pending').exists()


@pytest.mark.parametrize('pin_name',["INSTALLED_RECEIPT_SHA","INDEPENDENT_READBACK_SHA"])
def test_changed_receipt_or_separate_readback_pin_refuses_without_mutation(monkeypatch,pin_name):
    observed=hashlib.sha256(RECEIPT.read_bytes()).hexdigest()
    monkeypatch.setattr(installer,pin_name,'0'*64)
    with pytest.raises(ValueError,match='VERSION_SAFE_INSTALL_PIN_CHANGED'):
        installer.inspect_version_safe_code_only_status()
    assert hashlib.sha256(RECEIPT.read_bytes()).hexdigest()==observed


def test_completed_code_install_refuses_any_repetition_before_ntp(monkeypatch):
    from scripts.observation_runtime import atlas_independent_ntp_clock as ntp
    monkeypatch.setattr(ntp,'IndependentNtpClock',lambda **kw:pytest.fail('NO_NTP_ON_REPEAT'))
    observed=hashlib.sha256(RECEIPT.read_bytes()).hexdigest()
    with pytest.raises(ValueError,match='INSTALLATION_ALREADY_EXISTS_PRESERVE_NO_RETRY'):
        installer.main(['--execute-reviewed-code-only','--confirm-scope',installer.APPROVAL_CONFIRMATION])
    assert hashlib.sha256(RECEIPT.read_bytes()).hexdigest()==observed
    assert not Path('D:/AtlasRuntime/selection/r0012.json').exists()


def test_incorrect_artifact_digest_pin_refuses_before_claiming_installed(monkeypatch):
    monkeypatch.setattr(installer,'INSTALLED_ARTIFACT_DIGEST','0'*64)
    with pytest.raises(ValueError,match='VERSION_SAFE_INSTALL_NATIVE_RECEIPT_MISMATCH'):
        installer.inspect_version_safe_code_only_status()


def test_operator_scope_remains_one_shot_and_financially_inert():
    decision=installer.require_separate_operator_approval()
    assert decision['one_shot'] is True
    assert decision['selection_allowed'] is False
    assert decision['financial_authority'] is False
    assert decision['paper_account_inception'] is False
    assert decision['provider_access'] is False
    assert decision['live_orders'] is False
    report=json.loads(REPORT.read_bytes())
    assert report['native_handles_after_close']==0
    assert report['selected_release']==installer.V7_RELEASE
    assert report['r12_absent'] is True
