"""Offline loaded-image tests; no native store, service or installed launch."""
from importlib.machinery import ModuleSpec
from types import ModuleType, SimpleNamespace

import pytest
from app.services.paper_financial_replay import body

import scripts.observation_runtime.personal_release_identity as release


def verifier(tmp_path,monkeypatch):
    root=tmp_path/'accepted-release'
    instance=object.__new__(release.NativePersonalReleaseIdentity)
    instance.root,instance.receipt,instance.artifact_digest=root,{},'a'*64
    instance.source_commit='b'*40;instance.closed=False;instance.native=object()
    calls=[]
    instance.outputs={'.':SimpleNamespace(_verify=lambda:calls.append('.'))}
    instance.handles={};instance.files={}
    instance._ports=instance.native,tuple(instance.outputs.items()),tuple(instance.handles.items())
    instance._config=body(instance.receipt),root,instance.artifact_digest
    instance._process={'pid':123,'creation_filetime':456}
    monkeypatch.setattr(release,'observe_self',lambda:dict(instance._process))
    monkeypatch.setattr(release,'__file__',str(root/'source/scripts/observation_runtime/personal_release_identity.py'))
    monkeypatch.setattr(release.sys,'executable',str(root/'python/python.exe'))
    return instance,calls


def module(name,path):
    item=ModuleType(name);item.__file__=str(path);item.__spec__=ModuleSpec(name,loader=None,origin=str(path))
    return item


def test_mixed_workspace_module_cannot_pass_an_accepted_release_identity(tmp_path,monkeypatch):
    instance,_=verifier(tmp_path,monkeypatch)
    foreign=module('app.atlas_mixed_source_probe',tmp_path/'workspace'/'engine.py')
    monkeypatch.setitem(release.sys.modules,foreign.__name__,foreign)
    with pytest.raises(ValueError,match='PERSONAL_RELEASE_MODULE'):
        instance.verify(release_digest=instance.artifact_digest)


def loaded(instance,monkeypatch,*,namespace=False):
    relative='source/backend/app/accepted.py';path=instance.root/relative
    item=module('app.accepted',path)
    parent=str(release.Path(relative).parent).casefold()
    instance.files={str(release.Path(relative)).casefold():{'path':relative}}
    instance.handles={str(release.Path(relative)).casefold():object()}
    checked=[];instance.outputs[parent]=SimpleNamespace(_verify=lambda:checked.append(parent))
    locations=(str(path.parent),) if namespace else None
    if namespace:item.__path__=list(locations)
    snapshot=(('app.accepted',item,str(path),str(path),locations),)
    monkeypatch.setattr(release,'_atlas_modules',lambda:snapshot)
    return item,path,parent,checked,snapshot


@pytest.mark.parametrize('namespace',[False,True])
def test_only_pinned_modules_and_verified_parent_namespace_pass(tmp_path,monkeypatch,namespace):
    instance,_=verifier(tmp_path,monkeypatch)
    _,_,parent,checked,_=loaded(instance,monkeypatch,namespace=namespace)
    assert instance._verify_module_inventory()==1 and checked==[parent]


def test_complete_release_verify_uses_module_inventory_guard(tmp_path,monkeypatch):
    instance,root_checks=verifier(tmp_path,monkeypatch)
    _,_,parent,checked,_=loaded(instance,monkeypatch)
    instance._ports=instance.native,tuple(instance.outputs.items()),tuple(instance.handles.items())
    result=instance.verify(release_digest=instance.artifact_digest)
    assert result['source_commit']==instance.source_commit
    assert checked==[parent] and root_checks==['.']


@pytest.mark.parametrize('damage',['origin','unlisted','missing_handle','filename','parent','namespace','empty','changed'])
def test_missing_conflicting_or_changed_module_evidence_refuses(tmp_path,monkeypatch,damage):
    instance,_=verifier(tmp_path,monkeypatch)
    item,path,parent,_,snapshot=loaded(instance,monkeypatch)
    if damage=='origin':snapshot=(('app.accepted',item,str(path),str(tmp_path/'other.py'),None),)
    elif damage=='unlisted':instance.files={}
    elif damage=='missing_handle':instance.handles={}
    elif damage=='filename':snapshot=(('app.accepted',item,None,None,None),)
    elif damage=='parent':instance.outputs.pop(parent)
    elif damage=='namespace':snapshot=(('app.accepted',item,str(path),str(path),(str(tmp_path/'foreign'),)),)
    elif damage=='empty':snapshot=()
    if damage=='changed':
        calls=[]
        def change():
            calls.append(1)
            return snapshot if len(calls)==1 else ()
        monkeypatch.setattr(release,'_atlas_modules',change)
    else:monkeypatch.setattr(release,'_atlas_modules',lambda:snapshot)
    with pytest.raises(ValueError,match='PERSONAL_RELEASE_MODULE'):instance._verify_module_inventory()


def test_substituted_parent_namespace_refuses_without_repair(tmp_path,monkeypatch):
    instance,_=verifier(tmp_path,monkeypatch)
    _,_,parent,_,_=loaded(instance,monkeypatch)
    def refuse():raise ValueError('SYNTHETIC_NATIVE_PARENT_SUBSTITUTED')
    instance.outputs[parent]._verify=refuse
    with pytest.raises(ValueError,match='PARENT_SUBSTITUTED'):instance._verify_module_inventory()


def test_namespace_package_requires_every_search_location_in_inventory(tmp_path,monkeypatch):
    instance,_=verifier(tmp_path,monkeypatch)
    _,path,parent,checked,_=loaded(instance,monkeypatch)
    package=ModuleType('app.namespace')
    snapshot=(('app.namespace',package,None,None,(str(path.parent),)),)
    monkeypatch.setattr(release,'_atlas_modules',lambda:snapshot)
    assert instance._verify_module_inventory()==1 and checked==[parent]


@pytest.mark.parametrize('damage',['module_object','too_many_locations','empty_locations'])
def test_real_snapshot_rejects_bad_atlas_module_metadata(monkeypatch,damage):
    name='app.atlas_snapshot_probe'
    item=ModuleType(name)
    if damage=='module_object':item=object()
    elif damage=='too_many_locations':item.__path__=['D:/synthetic']*9
    else:item.__path__=[]
    monkeypatch.setitem(release.sys.modules,name,item)
    with pytest.raises(ValueError,match='PERSONAL_RELEASE_MODULE'):release._atlas_modules()
