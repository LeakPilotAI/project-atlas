"""Postinstallation nonfinancial status, ACK, exact native no-repeat refusal."""
import hashlib
import json
import subprocess
from pathlib import Path

import pytest

from scripts import atlas_version_safe_support_status as status
from scripts import atlas_version_safe_support_install_executor as executor


def test_real_installed_python_can_reverify_native_support_receipt_ack_and_selector():
    cmd=[str(status.APP/'python/python.exe'),'-I','-B','-S',str(Path(status.__file__))]
    result=subprocess.run(cmd,capture_output=True,text=True,timeout=90)
    assert result.returncode==0,result.stderr
    value=json.loads(result.stdout)
    assert value['status']=='INSTALLED_SUPPORT_RECEIPT_AND_ACK_VERIFIED_UNSELECTED'
    assert value['receipt_sha256']==status.RECEIPT_SHA
    assert value['support_files']==10
    assert value['support_directories']==3
    assert value['native_ack_verified'] is True
    assert value['r12_absent'] is True
    assert value['financial_authority'] is False
    assert value['paper_accounts'] is False
    assert value['provider_connections'] is False
    assert value['orders'] is False


def test_postinstall_reader_refuses_workspace_interpreter_and_tampered_receipt():
    with pytest.raises(ValueError,match='VERSION_SAFE_SUPPORT_STATUS_INSTALLED_PYTHON_REQUIRED'):
        status.inspect()
    m=json.loads(status.MANIFEST.read_bytes())
    receipt=Path(m['control'])/'receipt.json'
    digest=hashlib.sha256(receipt.read_bytes()).hexdigest()
    assert digest==status.RECEIPT_SHA
    with pytest.raises(ValueError,match='VERSION_SAFE_SUPPORT_STATUS_PIN_MISMATCH'):
        status.checked(receipt,'f'*64,65536)
    assert hashlib.sha256(receipt.read_bytes()).hexdigest()==digest


def test_explicit_second_support_install_refuses_before_ntp_and_preserves_receipt():
    cmd=[str(executor.APP/'python/python.exe'),'-I','-B','-S',
         str(Path(executor.__file__)),'--execute-one-shot-nonfinancial-support']
    m=json.loads(status.MANIFEST.read_bytes())
    receipt=Path(m['control'])/'receipt.json'
    old=hashlib.sha256(receipt.read_bytes()).hexdigest()
    result=subprocess.run(cmd,capture_output=True,text=True,timeout=60)
    assert result.returncode!=0
    assert 'SUPPORT_VSAFE_NATIVE_ALREADY_INSTALLED_OR_PARTIAL_NO_RETRY' in result.stderr
    assert 'NTP_REFRESH_FAILED' not in result.stderr
    assert hashlib.sha256(receipt.read_bytes()).hexdigest()==old
    assert not Path('D:/AtlasRuntime/selection/r0012.json').exists()


def test_unselected_native_support_and_v8_receipt_both_untouched_by_status_readback():
    m=json.loads(status.MANIFEST.read_bytes())
    assert Path(m['destination']).is_dir()
    assert Path(m['control']).is_dir()
    old=Path('D:/AtlasRuntime/support-installations/03122857979ccbc97572acda7a63d98640bb081c868de13929dcedd556883a26/receipt.json')
    assert hashlib.sha256(old.read_bytes()).hexdigest()==(
      '85bd24430576a8cfde7735c8412263da4ca6aea8459c55ec3d70c1f6a0c62d60')
    assert not Path('D:/AtlasRuntime/selection/r0012.json').exists()
