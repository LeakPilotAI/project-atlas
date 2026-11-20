"""Postselection read-only native R12 proof; zero financial/selector mutation."""
import hashlib
import json
import subprocess
from pathlib import Path

import pytest

from scripts import atlas_version_safe_r12_selected_status as status
from scripts import atlas_version_safe_r12_one_shot_executor as executor


def run_installed(script,*args):
    return subprocess.run([str(status.APP/'python/python.exe'),'-I','-B','-S',
            str(Path(script)),*args],capture_output=True,text=True,timeout=100)


def test_genuine_installed_python_r12_selected_status_from_native_record_pair():
    result=run_installed(status.__file__)
    assert result.returncode==0,result.stderr
    value=json.loads(result.stdout)
    assert value['status']=='NATIVE_R12_CODE_SELECTED_NOT_FINANCIAL_PAPER'
    assert value['revision']==12
    assert value['selected_release']==status.RELEASE
    assert value['r12_head']==status.R12_HEAD
    assert value['native_record_pair_verified'] is True
    assert value['support_receipt_verified'] is True
    assert value['independent_proof_verified'] is True
    assert value['selected_clock_source_verified'] is True
    assert value['deep_application_verified'] is False
    for flag in ('financial_authority','paper_accounts_authorized',
                 'providers_authorized','orders_authorized','paper_start_authorized',
                 'live_trading_authorized'):
        assert value[flag] is False


def test_selected_application_deep_native_readback_again_matches_pinned_receipts():
    result=run_installed(status.__file__,'--deep')
    assert result.returncode==0,result.stderr
    assert json.loads(result.stdout)['deep_application_verified'] is True
    assert not result.stderr


def test_postselection_proof_and_ntfs_pair_are_exact_and_native_v7_is_preserved():
    assert hashlib.sha256(status.PROOF.read_bytes()).hexdigest()==status.PROOF_SHA
    assert hashlib.sha256((status.SEL/'r0012.json').read_bytes()).hexdigest()==status.R12_RECORD_SHA
    assert hashlib.sha256((status.SEL/'r0012.pending').read_bytes()).hexdigest()==status.R12_RECORD_SHA
    assert hashlib.sha256((status.SEL/'r0011.json').read_bytes()).hexdigest()==status.R11_RECORD_SHA
    assert hashlib.sha256(status.APP_RECEIPT.read_bytes()).hexdigest()==status.APP_SHA
    assert hashlib.sha256(status.SUPPORT.read_bytes()).hexdigest()==status.SUPPORT_SHA
    report=json.loads(status.PROOF.read_bytes())
    assert report['status']=='R12_NATIVE_SELECTED_APP_SUPPORT_CLOCK_VERIFIED'
    assert report['native_application_files']==10574
    assert report['native_support_files']==10
    assert report['paper_start_authorized'] is False
    assert report['orders_submitted'] is False


def test_postselection_no_injected_workspace_clock_or_proof_replacement(monkeypatch):
    with pytest.raises(ValueError,match='ATLAS_R12_SELECTED_STATUS_INSTALLED_PYTHON_REQUIRED'):
        status.inspect()
    with pytest.raises(ValueError,match='ATLAS_R12_SELECTED_STATUS_NATIVE_HASH_CHANGED'):
        status.pinned(status.PROOF,'0'*64,limit=4096)


def test_second_exact_selection_request_refuses_without_ntp_or_native_write():
    result=run_installed(executor.__file__,'--execute-reviewed-r12-code-only')
    assert result.returncode!=0
    assert not result.stdout
    assert ('VERSION_SAFE_SUPPORT_STATUS_V7_PREDECESSOR_REQUIRED' in result.stderr
            or 'ATLAS_R12_ALREADY_PUBLISHED_OR_PARTIAL' in result.stderr
            or 'ATLAS_R12_PUBLISHER_NATIVE_PLAN_DIVERGED' in result.stderr)
    assert 'NTP_REFRESH' not in result.stderr
    assert hashlib.sha256((status.SEL/'r0012.json').read_bytes()).hexdigest()==status.R12_RECORD_SHA
