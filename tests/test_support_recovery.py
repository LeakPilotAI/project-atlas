"""Create-only recovery contracts; no operational native writes in these tests."""
import copy
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest
from scripts import build_support_deployment as builder, support_deployment as s
from scripts.release_selection import encoded


@pytest.fixture
def recovery(tmp_path,monkeypatch):
    release='c'*40;base=Path('D:/AtlasRuntime');repo=Path.cwd()
    old=s.strict((repo/'docs/QD_SELECTOR_LAUNCHER_SUPPORT_MANIFEST_V1_2026-10-30.json').read_bytes())
    receipt={'source_commit':release,'release_path':str(base/'releases'/release),'artifact_digest':'d'*64,
             'archive_sha256':'e'*64,'files':[{'path':r['path'],'sha256':'f'*64} for r in old['required_installed_application_sources']]}
    raw=encoded(receipt);path=repo/'logs/diagnostics'/('qd-unselected-release-'+release+'.json')
    real=builder.source_bytes
    monkeypatch.setattr(builder,'source_bytes',lambda root,name,**kw:raw if root/name==path else real(root,name,**kw))
    application={'release':release,'root':receipt['release_path'],'receipt':str(path),
                 'receipt_sha256':s.sha(raw),'artifact_digest':receipt['artifact_digest']}
    parents={str(base/name):[1,2,n] for n,name in enumerate(('launchers','support-installations','selection'),10)}
    package=builder.build(output=tmp_path/'package',historical_manifest=repo/'docs/QD_SELECTOR_LAUNCHER_SUPPORT_MANIFEST_V1_2026-10-30.json',
                          application=application,accepted_parents=parents)
    return SimpleNamespace(**locals())


def test_recovery_package_binds_new_verified_application_without_changing_v1(recovery):
    x=recovery;m,files=s.prepare(x.package['manifest'],x.package['archive'],x.package['manifest_sha256'])
    assert m['schema']=='QD_SUPPORT_DEPLOYMENT_V2' and m['application']==x.application
    assert m['accepted_parents']==x.parents and m['runtime']['providers'] is m['runtime']['financial_writers'] is False
    p=s.strict(files['support-manifest.json']);assert p['application_release']==x.release
    assert all(r['sha256']=='f'*64 for r in p['required_installed_application_sources'])
    with pytest.raises(ValueError):s.validate_manifest({k:v for k,v in m.items() if k!='accepted_parents'})


@pytest.mark.parametrize('damage',['missing','extra','alias','bool','negative','root','receipt','version','limit','provider'])
def test_recovery_parent_and_release_scope_fail_closed(recovery,damage):
    m=copy.deepcopy(recovery.package['manifest']);parents=m['accepted_parents'];first=next(iter(parents))
    if damage=='missing':parents.pop(first)
    elif damage=='extra':parents['D:\\elsewhere']=[1,2,30]
    elif damage=='alias':parents[first]=list(parents.values())[1]
    elif damage=='bool':parents[first]=[True,2,3]
    elif damage=='negative':parents[first]=[-1,2,3]
    elif damage=='root':m['application']['root']='D:\\foreign'
    elif damage=='receipt':m['application']['receipt']='D:\\private'
    elif damage=='version':m['schema']='QD_SUPPORT_DEPLOYMENT_V1'
    elif damage=='limit':m['limits']['seconds']=601
    else:m['runtime']['providers']=True
    with pytest.raises(ValueError):s.validate_manifest(m)


@pytest.mark.parametrize('fault',['','parent','interrupted','history','readback','admission'])
def test_recovery_creates_only_new_children_and_preserves_locked_history(recovery,monkeypatch,fault):
    from scripts.volume_inspector import windows_output as w
    import scripts.release_selection_store as stores
    m,files=s.prepare(recovery.package['manifest'],recovery.package['archive'],recovery.package['manifest_sha256'])
    base=Path(m['selection']).parent;ids={str(base):[1,2,3],**m['accepted_parents']}
    created=[];handles=set();written={};history=[{'immutable':'original revision 6'}];reads=[0]
    class Output:
        def __init__(self,path):
            self.path=path;self.root_handle=path;self.handles=[path];self.sid='INJECTED';handles.add(path)
        @classmethod
        def create_root(cls,path):
            assert path not in ids and not path in m['accepted_parents']
            ids[path]=[1,3,len(created)+1];created.append(path);return cls(path)
        def write_bound(self,name,data):written[(self.path,name)]=data;return {'bytes':len(data)}
    class Store:
        def __init__(self,*,root,native_root):assert root==m['selection'] and native_root==ids[root]
        @contextmanager
        def locked(self):yield
        def records(self):
            reads[0]+=1
            return history if fault!='history' or reads[0]<2 else history+[{'unexpected':'concurrent change'}]
        def close(self):pass
    monkeypatch.setattr(w,'WindowsOutput',Output)
    monkeypatch.setattr(w,'close_handle',lambda h:(handles.discard(h) or True))
    monkeypatch.setattr(s,'identity',lambda w,h:[9,9,9] if fault=='parent' and h==m['selection'] else ids[h])
    monkeypatch.setattr(stores,'NativeSelectionStore',Store)
    expected_new={Path(m['destination']),Path(m['control'])}
    monkeypatch.setattr(s,'_no_existing',lambda paths:pytest.fail('parent recreation') if set(paths)!=expected_new else None)
    monkeypatch.setattr(s,'inventory',lambda *a,**kw:{'files':[],'directories':[]})
    def readback(*a,**kw):
        if fault=='readback':raise ValueError('independent readback failed')
        return {'verified':True,'injected':True}
    monkeypatch.setattr(s,'independent_readback',readback)
    monkeypatch.setattr(s,'verify_deployment',lambda *a,**kw:None)
    args=dict(parent_identity=[1,2,3],admission=lambda:fault!='admission',interrupt_after=1 if fault=='interrupted' else None)
    if fault:
        with pytest.raises((ValueError,OSError)):s._install(m,files,**args)
        assert not any(name=='ack.json' for _,name in written)
    else:
        result=s._install(m,files,**args)
        assert result['receipt']['selection_id']==m['accepted_parents'][m['selection']]
        assert (m['control'],'ack.json') in written and result['handles_after_close']==0
    assert history==[{'immutable':'original revision 6'}] and not handles
    assert not set(created)&set(m['accepted_parents'])
