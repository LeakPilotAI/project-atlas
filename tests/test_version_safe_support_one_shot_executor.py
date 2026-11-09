"""Pinned, private-SID, nonfinancial support executor; no real copy from tests."""
import hashlib
import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import atlas_version_safe_support_install_executor as e


def test_executor_binds_unchanged_frozen_bootstrap_and_source_review():
    assert hashlib.sha256(e.REVIEW.read_bytes()).hexdigest()==e.REVIEW_SHA
    assert hashlib.sha256(e.BOOTSTRAP.read_bytes().replace(b'\r\n',b'\n')).hexdigest()==e.BOOTSTRAP_SHA
    assert e.REVIEW_SHA=='e58cc6eaecf276ab69f6f4a5c793f65d4f2c1eb02ce5481ca57ca13b209e4766'
    assert e.APPROVAL_PIN=='a3c669d1b4003e1c748b0225cec3b920513f1019a1eb6a113e661783e2c95029'


def test_readonly_installed_python_executor_inspects_without_native_install():
    result=subprocess.run([str(e.APP/'python/python.exe'),'-I','-B','-S',
        str(Path(e.__file__)),'--inspect'],capture_output=True,text=True,timeout=90)
    assert result.returncode==0,result.stderr
    item=json.loads(result.stdout)
    assert item['status']=='VERSION_SAFE_NTP_SUPPORT_NATIVE_BOOTSTRAP_REVIEW_PASS'
    assert item['execution_approved'] is True
    assert item['native_support_installed'] is False
    assert item['financial_authority'] is False
    assert item['selected'] is False
    assert not result.stderr


def test_workspace_python_cannot_use_executor():
    with pytest.raises(ValueError,match='ATLAS_SUPPORT_EXECUTOR_INSTALLED_PYTHON_ONLY'):
        e.load_bootstrap()


def test_wrong_bootstrap_and_source_review_pins_refuse_before_code_execution():
    with pytest.raises(ValueError,match='ATLAS_SUPPORT_EXECUTOR_REVIEWED_SOURCE_PIN_CHANGED'):
        e.pinned_bytes(e.REVIEW,'0'*64,limit=4096)
    assert hashlib.sha256(e.BOOTSTRAP.read_bytes().replace(b'\r\n',b'\n')).hexdigest()==e.BOOTSTRAP_SHA


def test_exact_private_approval_readback_under_installed_python_without_sid_display():
    # The only output is a Boolean; actual Windows SID is not exported.
    code=("import importlib.util,pathlib,json;"
          "p=pathlib.Path(r'D:\\Work\\Project Atlas\\scripts\\atlas_version_safe_support_install_executor.py');"
          "s=importlib.util.spec_from_file_location('vse',p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);"
          "b=m.load_bootstrap();b.APPROVAL_PIN=m.APPROVAL_PIN;"
          "b.require_installed_interpreter();x=b.require_install_approval();"
          "print(json.dumps({'approval_valid':True,'nonfinancial':not x['financial_authority'],"
          "'no_selection':not x['selection_allowed'],'one_shot':x['one_shot']}))")
    out=subprocess.run([str(e.APP/'python/python.exe'),'-I','-B','-S','-c',code],
                       capture_output=True,text=True,timeout=60)
    assert out.returncode==0,out.stderr
    assert json.loads(out.stdout)=={'approval_valid':True,'nonfinancial':True,
                                    'no_selection':True,'one_shot':True}
    assert 'S-1-' not in out.stdout


def test_executor_only_calls_guarded_native_copy_once_after_private_pin(monkeypatch):
    events=[]
    class Fake:
        APPROVAL_PIN=None
        def require_installed_interpreter(self):events.append('native_interpreter_prepared')
        def require_install_approval(self):events.append('operator_verified')
        def inspect(self):events.append('native_plan_verified')
        def install_code_only(self):
            events.append('single_verified_copy_intercepted')
            return {'status':'SYNTHETIC_NONFINANCIAL_NO_NATIVE_WRITE'}
        def main(self,*a,**kw):pytest.fail('FROZEN_CLI_FALLTHROUGH_NOT_ALLOWED')
    fake=Fake()
    monkeypatch.setattr(e,'load_bootstrap',lambda:fake)
    result=e.execute()
    assert result['status']=='SYNTHETIC_NONFINANCIAL_NO_NATIVE_WRITE'
    assert fake.APPROVAL_PIN==e.APPROVAL_PIN
    assert events==['native_interpreter_prepared','operator_verified',
                    'native_plan_verified','single_verified_copy_intercepted']


def test_executor_explicit_flag_required_and_no_generic_permission(monkeypatch):
    with pytest.raises(SystemExit):e.main([])
    with pytest.raises(SystemExit):e.main(['--do-all'])
    monkeypatch.setattr(e,'APPROVAL_PIN',None)
    class Fake:
        APPROVAL_PIN=None
    monkeypatch.setattr(e,'load_bootstrap',lambda:Fake())
    with pytest.raises(ValueError,match='ATLAS_SUPPORT_EXECUTOR_ONE_SHOT_PRIVATE_APPROVAL_NOT_PINNED'):
        e.execute()
