"""Installed fixture-origin binding only; no native publication or child launch."""
import copy
import hashlib
import json

import pytest
from personal_fixture_sources import fixture_source_root, validate_scope


def example(tmp_path):
    root=tmp_path/'logs/diagnostics/qd-native-install-fixture/candidate'
    value={'schema':'PINNED_SYNTHETIC_INSTALL_V1','root':str(root),'source_commit':'a'*40,
        'files':[{'path':'backend/app/a.py','bytes':0,'sha256':hashlib.sha256(b'').hexdigest(),'id':[1,2,3]}]}
    return root,value


def validate(tmp_path,value,*,pin=None,exe=None,prefix=None):
    data=json.dumps(value).encode();root=example(tmp_path)[0]
    return validate_scope(tmp_path,data,pin or hashlib.sha256(data).hexdigest(),exe or root/'python/python.exe',prefix or root/'python')


def test_explicit_test_scope_separates_installed_source_from_workspace(tmp_path):
    root,value=example(tmp_path);before=copy.deepcopy(value)
    source,rows=validate(tmp_path,value)
    assert source==root and set(rows)=={'backend/app/a.py'} and value==before
    assert not root.exists()  # Pure scope validation is not native acceptance.


@pytest.mark.parametrize('fault',['pin','schema','commit','root','exe','prefix','duplicate','traversal','sha','id','malformed'])
def test_bad_installed_fixture_scope_refuses_before_any_file_access(tmp_path,fault):
    root,value=example(tmp_path);args={}
    if fault=='pin':args['pin']='0'*64
    elif fault=='schema':value['schema']='OPERATIONAL'
    elif fault=='commit':value['source_commit']='not-a-release'
    elif fault=='root':value['root']=str(root.parent/'active')
    elif fault=='exe':args['exe']=tmp_path/'python.exe'
    elif fault=='prefix':args['prefix']=tmp_path/'python'
    elif fault=='duplicate':value['files']*=2
    elif fault=='traversal':value['files'][0]['path']='../outside.py'
    elif fault=='sha':value['files'][0]['sha256']='0'
    elif fault=='id':value['files'][0]['id']=[True,2,3]
    elif fault=='malformed':value['files'][0]={}
    with pytest.raises(ValueError):validate(tmp_path,value,**args)
    assert not root.exists()


def test_workspace_fixture_default_is_unchanged(tmp_path,monkeypatch):
    monkeypatch.delenv('ATLAS_SYNTHETIC_INSTALL_SCOPE',raising=False)
    monkeypatch.delenv('ATLAS_SYNTHETIC_INSTALL_SCOPE_SHA256',raising=False)
    assert fixture_source_root(tmp_path)==tmp_path


@pytest.mark.parametrize('name',['ATLAS_SYNTHETIC_INSTALL_SCOPE','ATLAS_SYNTHETIC_INSTALL_SCOPE_SHA256'])
def test_incomplete_scope_cannot_silently_fall_back_to_workspace(tmp_path,monkeypatch,name):
    monkeypatch.delenv('ATLAS_SYNTHETIC_INSTALL_SCOPE',raising=False)
    monkeypatch.delenv('ATLAS_SYNTHETIC_INSTALL_SCOPE_SHA256',raising=False)
    monkeypatch.setenv(name,'MISSING')
    with pytest.raises(ValueError,match='COMPLETE_SYNTHETIC'):fixture_source_root(tmp_path)
