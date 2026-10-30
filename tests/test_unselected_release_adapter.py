"""Mocked code-install lifecycle. Fake inventories cannot enroll real resources."""
import copy
import hashlib
import io
import json
import runpy
import time
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import install_verified_release as adapter
from scripts import native_install_candidate as copier
from scripts.observation_runtime import personal_windows_clock as clocks


@pytest.mark.parametrize('flag',[False,None,1,'true'])
def test_default_or_untyped_invocation_refuses_without_read_or_effect(flag,monkeypatch):
    monkeypatch.setattr(adapter,'prepare_install_inputs',lambda **k:pytest.fail('No input access'))
    with pytest.raises(ValueError,match='AUTHORIZATION_REQUIRED'):
        adapter.install_unselected_release(approved_execution=flag)


def test_fixture_clock_is_not_an_operational_install_clock():
    with pytest.raises(ValueError,match='GENUINE_INSTALL_CLOCK_REQUIRED'):
        adapter.install_unselected_release(approved_execution=True,clock=SimpleNamespace(require_operational=lambda x:True))


def test_module_entry_is_source_only_and_never_an_implicit_installer():
    with pytest.raises(SystemExit,match='REFUSED: source-only adapter'):
        runpy.run_path(adapter.__file__,run_name='__main__')


def test_target_rejects_path_like_commit_before_any_filesystem_work():
    with pytest.raises(ValueError,match='EXACT_SOURCE_COMMIT_REQUIRED'):
        adapter.installation_target('../outside','SYNTHETIC')


def fixture(tmp_path,monkeypatch,fault=None):
    destination=tmp_path/'unselected-code';audit=tmp_path/'receipt.json';events=[]
    prepared={'started':time.monotonic(),'selected_digest':'a'*64}
    class SyntheticClock:
        def require_operational(self,runtime):
            events.append('clock')
            if fault=='clock':raise ValueError('SYNTHETIC_CLOCK_REFUSED')
    monkeypatch.setattr(clocks,'LocalWindowsClock',SyntheticClock)
    monkeypatch.setattr(adapter,'prepare_install_inputs',lambda **k:copy.deepcopy(prepared))
    monkeypatch.setattr(adapter,'installation_target',lambda *a:(destination,audit))
    def copy_code(**kw):
        assert kw['admission']() is True
        events.append('copy');destination.mkdir();(destination/'SYNTHETIC.txt').write_text('NO_FINANCIAL_STATE')
        if fault=='copy':raise OSError('SYNTHETIC_INTERRUPTED_COPY')
        return {'files':[{'path':'SYNTHETIC.txt','bytes':18,'sha256':'b'*64,'id':[1,2,3]}],
                'directories':[{'path':'.','id':[4,5,6]}]}
    monkeypatch.setattr(adapter,'_copy_prepared_code',copy_code)
    def readback(*a,**k):
        events.append('readback')
        if fault=='layout':raise ValueError('SYNTHETIC_LAYOUT_REFUSED')
        return {'layout':{'SYNTHETIC':'NOT_OPERATIONAL_AUTHORITY'}}
    monkeypatch.setattr(adapter,'installed_readback',readback)
    return SimpleNamespace(destination=destination,audit=audit,events=events,clock=SyntheticClock())


@pytest.mark.parametrize('fault',['clock','copy','layout',None])
def test_interrupted_install_preserves_previous_marker_and_never_retries(tmp_path,monkeypatch,fault):
    selected=tmp_path/'selected.json';selected.write_bytes(b'SYNTHETIC_OLD_RELEASE')
    old=tmp_path/'old';old.mkdir();(old/'code').write_bytes(b'OLD')
    s=fixture(tmp_path,monkeypatch,fault)
    args={'approved_execution':True,'source_commit':'a'*40,'inventory_digest':'a'*64,'receipt_path':s.audit,'clock':s.clock}
    if fault:
        with pytest.raises((ValueError,OSError)):adapter.install_unselected_release(**args)
        assert not s.audit.exists()
        if fault!='clock':assert s.audit.with_suffix('.pending.jsonl').exists() and s.destination.exists()
    else:
        value=adapter.install_unselected_release(**args)
        assert value['selected'] is value['operational_acceptance'] is value['financial_effects'] is False
        assert s.audit.exists()
        before=s.audit.read_bytes();events=list(s.events)
        with pytest.raises(FileExistsError):adapter.install_unselected_release(**args)
        assert s.audit.read_bytes()==before and s.events==events+['clock']
    assert selected.read_bytes()==b'SYNTHETIC_OLD_RELEASE' and (old/'code').read_bytes()==b'OLD'


def test_observer_cannot_mutate_copy_result_or_relabel_domain(tmp_path,monkeypatch):
    from scripts.volume_inspector import windows_output as w
    closed=[]
    class Root:
        root_handle=1
        def __init__(self):self.handles=[1]
        def __enter__(self):return self
        def __exit__(self,*a):closed.append(True)
    monkeypatch.setattr(w.WindowsOutput,'create_root',lambda *a:Root())
    monkeypatch.setattr(w,'close_handle',lambda h:closed.append(True) or True)
    monkeypatch.setattr(w,'info',lambda *a:SimpleNamespace(volume=1,index_hi=2,index_lo=3))
    monkeypatch.setattr(copier,'_verify_namespace',lambda *a:None)
    raw=io.BytesIO()
    with zipfile.ZipFile(raw,'w'):pass
    prepared={'source':tmp_path,'dependencies':{},'runtime':{},'names':[],'directories':[],'old_dirs':{},'verified':{},
              'raw':raw.getvalue(),'started':time.monotonic()}
    def observer(value):value['schema']='FOREIGN';value['files'].append({'path':'outside'})
    result=copier._copy_prepared_code(destination=tmp_path,archive_sha256='a'*64,source_commit='b'*40,
        prepared=prepared,observer=observer)
    assert result['schema']=='ATLAS_NATIVE_CODE_COPY_V1' and result['files']==[] and closed==[True]


def test_public_fixture_observer_retains_its_original_test_schema(tmp_path,monkeypatch):
    import scripts.native_install_plan as planner
    repo=tmp_path/'repo';parent=repo/'logs/diagnostics/qd-native-install-fixture';parent.mkdir(parents=True)
    monkeypatch.setattr(copier,'__file__',str(repo/'scripts/native_install_candidate.py'))
    monkeypatch.setattr(planner,'prepare_install_inputs',lambda **k:{})
    def copy(**kwargs):
        result={'schema':'ATLAS_NATIVE_CODE_COPY_V1','status':'NATIVE_COPY_ACL_IDENTITY_HASH_VERIFIED_UNSELECTED'}
        kwargs['observer'](dict(result));return result
    monkeypatch.setattr(copier,'_copy_prepared_code',copy)
    snapshots=[]
    result=copier.install_synthetic_candidate(destination=parent/'candidate',archive=None,archive_sha256='a'*64,
        source_commit='b'*40,dependency_receipt=None,dependency_digest='c'*64,observer=lambda v:snapshots.append(v))
    assert snapshots[-1]==result
    assert result['schema']=='ATLAS_DISPOSABLE_NATIVE_INSTALLATION_V1'


def test_lost_admission_refuses_before_first_creation(tmp_path,monkeypatch):
    from scripts.volume_inspector import windows_output as w
    monkeypatch.setattr(w.WindowsOutput,'create_root',lambda *a:pytest.fail('Native effects before admission'))
    raw=io.BytesIO()
    with zipfile.ZipFile(raw,'w'):pass
    plan={'source':tmp_path,'dependencies':{},'runtime':{},'names':[],'directories':[],'old_dirs':{},'verified':{},
          'raw':raw.getvalue(),'started':time.monotonic()}
    with pytest.raises(ValueError,match='ADMISSION_LOST'):
        copier._copy_prepared_code(destination=tmp_path,archive_sha256='a'*64,source_commit='b'*40,
            prepared=plan,admission=lambda:False)


def test_failed_native_close_never_reports_zero_retained_handles(tmp_path,monkeypatch):
    from scripts.volume_inspector import windows_output as w
    snapshots=[]
    root=SimpleNamespace(root_handle=1,handles=[1])
    monkeypatch.setattr(w.WindowsOutput,'create_root',lambda *a:root)
    monkeypatch.setattr(w,'info',lambda *a:SimpleNamespace(volume=1,index_hi=2,index_lo=3))
    monkeypatch.setattr(w,'close_handle',lambda h:False)
    monkeypatch.setattr(copier,'_verify_namespace',lambda *a:None)
    raw=io.BytesIO()
    with zipfile.ZipFile(raw,'w'):pass
    plan={'source':tmp_path,'dependencies':{},'runtime':{},'names':[],'directories':[],'old_dirs':{},'verified':{},
          'raw':raw.getvalue(),'started':time.monotonic()}
    with pytest.raises(OSError,match='CLOSE_UNCONFIRMED'):
        copier._copy_prepared_code(destination=tmp_path,archive_sha256='a'*64,source_commit='b'*40,
            prepared=plan,observer=lambda row:snapshots.append(row))
    assert snapshots[-1]['retained_handles_after_close']==1
    assert snapshots[-1]['status']=='REFUSED_PRESERVE_PARTIAL' and root.handles==[1]


@pytest.mark.parametrize('damage',[
    None,'source','digest','files','directories','pid','creation','image','handles','boolean-count','schema',
    'foreign-layout','relative-layout','version','bits','mixed-prefix',
])
def test_independent_runtime_readback_must_match_exact_native_process_and_layout(damage):
    root=Path('D:/AtlasRuntime/releases')/('a'*40)
    receipt={'source_commit':'a'*40,'files':[{}],'directories':[{}]}
    identity={'pid':123,'created':456,'image':str(root/'python/python.exe').casefold()}
    result={'handles_after_close':0,'native_proof':{'source_commit':'a'*40,'artifact_digest':'b'*64,
        'files':1,'directories':1,'process':{'pid':123,'creation_filetime':456,'image':str(root/'python/python.exe')}},
        'layout':{'executable':str(root/'python/python.exe'),'base':str(root/'python/python.exe'),
            'prefix':str(root/'python'),'base_prefix':str(root/'python'),'stdlib':str(root/'python/Lib'),'bits':64,'version':[3,12]}}
    p=result['native_proof'];l=result['layout']
    if damage=='source':p['source_commit']='c'*40
    elif damage=='digest':p['artifact_digest']='c'*64
    elif damage=='files':p['files']=2
    elif damage=='directories':p['directories']=2
    elif damage=='pid':p['process']['pid']=124
    elif damage=='creation':p['process']['creation_filetime']=457
    elif damage=='image':p['process']['image']='FOREIGN'
    elif damage=='handles':result['handles_after_close']=1
    elif damage=='boolean-count':p['files']=True
    elif damage=='schema':result['extra']='FOREIGN'
    elif damage=='foreign-layout':l['stdlib']='C:/Foreign/Lib'
    elif damage=='relative-layout':l['stdlib']='python/Lib'
    elif damage=='version':l['version']=[3,11]
    elif damage=='bits':l['bits']=32
    elif damage=='mixed-prefix':l['prefix']=str(root/'other')
    if damage:
        with pytest.raises(ValueError):adapter.validate_installed_readback(result,root,receipt,'b'*64,identity)
    else:assert adapter.validate_installed_readback(result,root,receipt,'b'*64,identity)==result


@pytest.mark.parametrize('damage',[None,'promotion','selected','provider','financial','paper','limits','destination',
                                 'source','pin','extra','status','dependency','archive'])
def test_reviewed_proposal_cannot_expand_into_activation_or_foreign_paths(damage):
    root=Path(__file__).resolve().parents[1]
    value=json.loads((root/'docs/QD_UNSELECTED_CODE_INSTALL_PROPOSAL_V1_2026-10-30.json').read_bytes())
    if damage in ('promotion','selected'):value[damage]=True
    elif damage=='provider':value['provider_activation']=True
    elif damage=='financial':value['financial_enrollment']=True
    elif damage=='paper':value['paper_startup']=True
    elif damage=='limits':value['limits']['bytes']+=1
    elif damage=='destination':value['destination']='C:/AtlasRuntime/foreign'
    elif damage=='source':value['source_commit']='../outside'
    elif damage=='pin':value['archive_sha256']='INVALID'
    elif damage=='extra':value['activate_broker']=True
    elif damage=='status':value['status']='APPROVED_BY_FIXTURE'
    elif damage=='dependency':value['dependency_receipt']='D:/Unrelated/private.json'
    elif damage=='archive':value['archive']='C:/Unrelated/private.zip'
    if damage:
        with pytest.raises(ValueError):adapter.validate_proposal(value)
    else:assert adapter.validate_proposal(value)==value


def test_review_proposal_pins_exact_three_adapter_sources():
    root=Path(__file__).resolve().parents[1]
    value=json.loads((root/'docs/QD_UNSELECTED_CODE_INSTALL_PROPOSAL_V1_2026-10-30.json').read_bytes())
    assert set(value['adapter_source_sha256'])=={'scripts/install_verified_release.py','scripts/native_install_plan.py',
                                               'scripts/native_install_candidate.py'}
    for name,pin in value['adapter_source_sha256'].items():
        assert hashlib.sha256((root/name).read_bytes().replace(b'\r\n',b'\n')).hexdigest()==pin
