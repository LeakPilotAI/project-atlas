"""Pure plan refusals, no native directories, services or operational resources."""
import copy
import hashlib
import json

import pytest
from test_candidate_selected_inventory import build as selected_build

from scripts.native_install_plan import prepare_install_inputs


def arguments(tmp_path, monkeypatch):
    *_,archive,pin=selected_build(tmp_path,monkeypatch)
    with __import__('zipfile').ZipFile(archive) as z:commit=json.loads(z.read('release-manifest.json'))['head']
    names=['python/python.exe','python/python312.dll','python/Lib/os.py','python/Lib/encodings/__init__.py']
    receipt={'schema':'ATLAS_QD_D_RUNTIME_INSTALLATION_V1','stage':'D_RUNTIME_LAYOUT_VERIFIED',
        'release_path':'D:/AtlasRuntime/releases/'+'a'*40,'source_commit':'a'*40,
        'files':[{'path':n,'bytes':3,'sha256':'b'*64,'id':[1,0,i+1]} for i,n in enumerate(names)],
        'directories':[{'path':n,'id':[1,1,i+1]} for i,n in enumerate(['.','python','python/Lib','python/Lib/encodings'])]}
    return {'archive':archive,'archive_sha256':pin,'source_commit':commit,'dependency_receipt':receipt,
            'dependency_digest':dependency_pin(receipt)}


def dependency_pin(receipt):
    return hashlib.sha256(json.dumps(receipt['files'],sort_keys=True,separators=(',',':')).encode()).hexdigest()


def test_plan_freezes_inputs_and_preserves_exact_required_parent_mapping(tmp_path,monkeypatch):
    args=arguments(tmp_path,monkeypatch);before=copy.deepcopy(args['dependency_receipt'])
    p=prepare_install_inputs(**args)
    assert len(p['dependencies'])==4 and 'python/Lib' in p['old_dirs']
    args['dependency_receipt']['files'][0]['sha256']='0'*64
    assert p['dependencies']['python/python.exe']['sha256']==before['files'][0]['sha256']
    assert p['verified']['activation_approved'] is False


@pytest.mark.parametrize('fault',[
    'duplicate','case-alias','slash-alias','file-id-alias','bool-size','negative-size','hash','bool-id',
    'negative-id','wide-id','missing-dir','duplicate-dir','dir-id-alias','parent-collision','file-extra','dir-extra',
    'source-commit','dependency-commit','dependency-root','missing-root','wrong-schema','wrong-stage','pin','selection-pin',
])
def test_bad_plan_refuses_without_any_native_creation(tmp_path,monkeypatch,fault):
    args=arguments(tmp_path,monkeypatch);r=args['dependency_receipt'];f=r['files'];d=r['directories']
    if fault=='duplicate':f.append(copy.deepcopy(f[0]))
    elif fault=='case-alias':f.append({**f[0],'path':'python/PYTHON.EXE','id':[8,8,8]})
    elif fault=='slash-alias':f.append({**f[0],'path':f[0]['path'].replace('/','\\'),'id':[8,8,8]})
    elif fault=='file-id-alias':f[1]['id']=f[0]['id']
    elif fault=='bool-size':f[0]['bytes']=True
    elif fault=='negative-size':f[0]['bytes']=-1
    elif fault=='hash':f[0]['sha256']='INVALID'
    elif fault=='bool-id':f[0]['id']=[True,2,3]
    elif fault=='negative-id':f[0]['id']=[1,-1,3]
    elif fault=='wide-id':f[0]['id']=[1,2,2**32]
    elif fault=='missing-dir':d.pop()
    elif fault=='duplicate-dir':d.append(copy.deepcopy(d[1]))
    elif fault=='dir-id-alias':d[1]['id']=f[0]['id']
    elif fault=='parent-collision':f.append({'path':'python/Lib','bytes':0,'sha256':'b'*64,'id':[9,9,9]})
    elif fault=='file-extra':f[0]['unexpected']='foreign'
    elif fault=='dir-extra':d[0]['unexpected']='foreign'
    elif fault=='source-commit':args['source_commit']='../outside'
    elif fault=='dependency-commit':r['source_commit']='INVALID'
    elif fault=='dependency-root':r['release_path']='D:/unrelated'
    elif fault=='missing-root':d.pop(0)
    elif fault=='wrong-schema':r['schema']='ATLAS_DISPOSABLE_NATIVE_INSTALLATION_V1'
    elif fault=='wrong-stage':r['stage']='PENDING'
    elif fault=='selection-pin':args['inventory_digest']='0'*64
    args['dependency_digest']=dependency_pin(r) if fault!='pin' else '0'*64
    with pytest.raises(ValueError):prepare_install_inputs(**args)
