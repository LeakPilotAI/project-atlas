"""Disposable installer refusals occur before native directory creation."""
import hashlib
import json

import pytest
from test_candidate_verifier import built

from scripts import native_install_candidate as installer
from scripts.volume_inspector import windows_output as native


@pytest.mark.parametrize('fault',['existing','foreign_parent','wrong_name','wrong_commit','missing_receipt',
    'wrong_dependency_pin','missing_runtime','bad_interruption','bad_observer'])
def test_disposable_installation_preflight_refuses_without_native_creation(tmp_path,monkeypatch,fault):
    archive,pin=built(tmp_path,monkeypatch)
    repo=tmp_path/'repo';parent=repo/'logs/diagnostics/qd-native-install-fixture';parent.mkdir(parents=True)
    monkeypatch.setattr(installer,'__file__',str(repo/'scripts/native_install_candidate.py'))
    destination=parent/'candidate'
    receipt={'schema':'ATLAS_QD_D_RUNTIME_INSTALLATION_V1','stage':'D_RUNTIME_LAYOUT_VERIFIED',
        'files':[],'directories':[],'source_commit':'a'*40,'release_path':'D:/AtlasRuntime/releases/'+'a'*40}
    digest=hashlib.sha256(json.dumps(receipt['files'],sort_keys=True,separators=(',',':')).encode()).hexdigest()
    with __import__('zipfile').ZipFile(archive) as z:commit=json.loads(z.read('release-manifest.json'))['head']
    args={'destination':destination,'archive':archive,'archive_sha256':pin,'source_commit':commit,
        'dependency_receipt':receipt,'dependency_digest':digest}
    if fault=='existing':destination.mkdir()
    elif fault=='foreign_parent':args['destination']=tmp_path/'foreign/candidate'
    elif fault=='wrong_name':args['destination']=parent/'active'
    elif fault=='wrong_commit':args['source_commit']='b'*40
    elif fault=='missing_receipt':args['dependency_receipt']={}
    elif fault=='wrong_dependency_pin':args['dependency_digest']='0'*64
    elif fault=='bad_interruption':args['interrupt_after']=True
    elif fault=='bad_observer':args['observer']=True
    calls=[]
    def forbidden(*args,**kwargs):calls.append(1);raise AssertionError('No native creation on preflight refusal')
    monkeypatch.setattr(native.WindowsOutput,'create_root',forbidden)
    before=set(parent.iterdir())
    with pytest.raises(ValueError):installer.install_synthetic_candidate(**args)
    assert calls==[] and set(parent.iterdir())==before


@pytest.mark.parametrize('fault',[None,'extra_file','extra_directory','missing','type_conflict'])
def test_native_candidate_exact_namespace_is_required_without_repair(tmp_path,fault):
    root=tmp_path/'candidate';(root/'backend').mkdir(parents=True)
    source=root/'backend/a.py';source.write_bytes(b'SYNTHETIC')
    if fault=='extra_file':(root/'unlisted.py').write_bytes(b'x')
    elif fault=='extra_directory':(root/'unlisted').mkdir()
    elif fault=='missing':source.unlink()
    elif fault=='type_conflict':source.unlink();source.mkdir()
    before={str(p.relative_to(root)):p.is_dir() for p in root.rglob('*')}
    if fault is None:installer._verify_namespace(root,{'backend/a.py'},{'.','backend'},lambda:None)
    else:
        with pytest.raises(ValueError):installer._verify_namespace(root,{'backend/a.py'},{'.','backend'},lambda:None)
    assert {str(p.relative_to(root)):p.is_dir() for p in root.rglob('*')}==before
