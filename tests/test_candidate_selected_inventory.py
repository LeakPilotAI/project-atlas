"""Explicit source selection and disposable staging, never runtime installation."""
import hashlib
import json
import zipfile

import pytest
from test_offline_candidate_packaging import candidate, fixture_root


def selection_for(root,names,*,commit='a'*40):
    rows=[]
    for name in sorted(names):
        data=(root/name).read_bytes();rows.append({'path':name,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()})
    digest=hashlib.sha256(json.dumps(rows,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    return {'schema':'ATLAS_SOURCE_SELECTION_V1','source_commit':commit,'inventory_digest':digest,'files':rows}


def setup(tmp_path,monkeypatch):
    root,tracked=fixture_root(tmp_path,monkeypatch);old=candidate.git;flags={'dirty':False,'head':'a'*40}
    def git(*args):
        if args==('rev-parse','HEAD'):return [flags['head']]
        if args[:2]==('diff','--name-only'):return ['backend/app/example.py'] if flags['dirty'] else []
        return old(*args)
    monkeypatch.setattr(candidate,'git',git)
    return root,tracked,flags,selection_for(root,tracked)


def build(tmp_path,monkeypatch):
    root,tracked,flags,selection=setup(tmp_path,monkeypatch);dest=tmp_path/'candidate'
    pin=candidate.build_selected(dest,selection=selection,expected_inventory_sha256=selection['inventory_digest'])
    return root,tracked,flags,selection,dest/'atlas-source.zip',pin


def copy_fixture(archive,pin,stage,*,interrupt_after=None):
    candidate.verify_candidate(archive,expected_sha256=pin)
    stage.mkdir()
    with zipfile.ZipFile(archive) as bundle:
        for i,name in enumerate(bundle.namelist()):
            target=candidate.source_path(stage,name);target.parent.mkdir(parents=True,exist_ok=True)
            with target.open('xb') as stream:stream.write(bundle.read(name))
            if interrupt_after==i+1:raise OSError('SYNTHETIC_INTERRUPTED_SOURCE_COPY')


def tree(root):
    return {p.relative_to(root).as_posix():p.read_bytes() for p in root.rglob('*') if p.is_file()}


def test_selected_build_excludes_untracked_and_is_deterministic(tmp_path,monkeypatch):
    root,_,_,selection,archive,pin=build(tmp_path,monkeypatch)
    untouched=tree(root)
    with zipfile.ZipFile(archive) as bundle:
        assert set(bundle.namelist())=={'backend/app/example.py','release-manifest.json','requirements-observed.txt'}
        manifest=json.loads(bundle.read('release-manifest.json'))
        assert manifest['head']=='a'*40 and manifest['activation_approved'] is False
        assert all(row['git_status']=='tracked' for row in manifest['files'])
    assert candidate.build_selected(tmp_path/'again',selection=selection,expected_inventory_sha256=selection['inventory_digest'])==pin
    assert tree(root)==untouched


@pytest.mark.parametrize('fault',['schema','pin','head','dirty','untracked','duplicate','bad_size','changed_content','selection_digest'])
def test_invalid_selection_refuses_before_destination_creation(tmp_path,monkeypatch,fault):
    root,tracked,flags,selection=setup(tmp_path,monkeypatch);expected=selection['inventory_digest']
    if fault=='schema':selection['schema']='UNKNOWN'
    elif fault=='pin':expected='0'*64
    elif fault=='head':flags['head']='b'*40
    elif fault=='dirty':flags['dirty']=True
    elif fault=='untracked':tracked.clear()
    elif fault=='duplicate':selection['files']*=2
    elif fault=='bad_size':selection['files'][0]['bytes']=True
    elif fault=='changed_content':(root/'backend/app/example.py').write_bytes(b'changed')
    elif fault=='selection_digest':selection['inventory_digest']='0'*64
    if fault in ('duplicate','bad_size'):
        expected=hashlib.sha256(json.dumps(selection['files'],sort_keys=True,separators=(',',':')).encode()).hexdigest()
        selection['inventory_digest']=expected
    before=tree(root);dest=tmp_path/'refused'
    with pytest.raises(ValueError):candidate.build_selected(dest,selection=selection,expected_inventory_sha256=expected)
    assert not dest.exists() and tree(root)==before


def test_selected_cli_uses_explicit_inventory_pin(tmp_path,monkeypatch,capsys):
    _,_,_,selection=setup(tmp_path,monkeypatch);path=tmp_path/'selection.json';path.write_text(json.dumps(selection))
    dest=tmp_path/'selected'
    assert candidate.main([str(dest),'--selection',str(path),'--expected-inventory-sha256',selection['inventory_digest']])==0
    pin=capsys.readouterr().out.strip()
    assert candidate.verify_candidate(dest/'atlas-source.zip',expected_sha256=pin)['activation_approved'] is False


@pytest.mark.parametrize('args',[['--selection','s.json'],['--expected-inventory-sha256','0'*64],
    ['--selection','s.json','--expected-inventory-sha256','A'*64]])
def test_incomplete_selected_cli_refuses_before_io(tmp_path,capsys,args):
    with pytest.raises(SystemExit):candidate.main([str(tmp_path/'absent'),*args])
    assert not (tmp_path/'absent').exists() and capsys.readouterr().out==''


def test_caller_selection_cannot_mutate_the_frozen_archive_manifest(tmp_path,monkeypatch):
    _,_,_,selection=setup(tmp_path,monkeypatch);pin=selection['inventory_digest'];original=candidate.source_bytes
    def change(*args,**kwargs):
        raw=original(*args,**kwargs);selection['files'][0]['sha256']='0'*64
        return raw
    monkeypatch.setattr(candidate,'source_bytes',change)
    dest=tmp_path/'frozen';archive_pin=candidate.build_selected(dest,selection=selection,expected_inventory_sha256=pin)
    assert candidate.verify_candidate(dest/'atlas-source.zip',expected_sha256=archive_pin)['supplied_bytes_consistent']


def test_complete_stage_and_repeat_refusal_preserve_both_source_and_stage(tmp_path,monkeypatch):
    root,_,_,_,archive,pin=build(tmp_path,monkeypatch);stage=tmp_path/'stage'
    copy_fixture(archive,pin,stage);before=tree(stage);original=tree(root)
    result=candidate.verify_staged_candidate(stage,archive,expected_sha256=pin)
    assert result['source_stage_consistent'] is True and result['native_identity_acl_verified'] is False
    assert result['installation_verified'] is False and result['activation_approved'] is False
    with pytest.raises(FileExistsError):copy_fixture(archive,pin,stage)
    assert tree(stage)==before and tree(root)==original


def test_verified_source_package_cannot_substitute_for_native_installation(tmp_path,monkeypatch):
    from scripts.observation_runtime import personal_release_identity as native
    _,_,_,_,archive,pin=build(tmp_path,monkeypatch)
    with zipfile.ZipFile(archive) as bundle:manifest=json.loads(bundle.read('release-manifest.json'))
    def forbid():raise AssertionError('Source manifest must refuse before native access')
    monkeypatch.setattr(native,'native_primitives',forbid)
    with pytest.raises(ValueError,match='INVENTORY_REQUIRED'):
        native.NativePersonalReleaseIdentity(receipt=manifest,artifact_digest=pin)


def test_interrupted_new_version_cannot_change_previous_release_or_selection(tmp_path,monkeypatch):
    _,_,_,_,archive,pin=build(tmp_path,monkeypatch)
    previous=tmp_path/'version-a';copy_fixture(archive,pin,previous);before=tree(previous)
    selected=tmp_path/'active-selection.json';selected.write_bytes(b'{"SYNTHETIC":"version-a","financial":false}')
    selection_before=selected.read_bytes();partial=tmp_path/'version-b'
    with pytest.raises(OSError,match='INTERRUPTED'):copy_fixture(archive,pin,partial,interrupt_after=1)
    partial_before=tree(partial)
    with pytest.raises(ValueError,match='Incomplete'):candidate.verify_staged_candidate(partial,archive,expected_sha256=pin)
    assert tree(partial)==partial_before and tree(previous)==before and selected.read_bytes()==selection_before
    assert candidate.verify_staged_candidate(previous,archive,expected_sha256=pin)['source_stage_consistent']


@pytest.mark.parametrize('fault',['missing','changed','extra_file','extra_directory'])
def test_stage_corruption_or_unknown_namespace_refuses_without_repair(tmp_path,monkeypatch,fault):
    _,_,_,_,archive,pin=build(tmp_path,monkeypatch);stage=tmp_path/'stage';copy_fixture(archive,pin,stage)
    path=stage/'backend/app/example.py'
    if fault=='missing':path.unlink()
    elif fault=='changed':path.write_bytes(b'VALUE = 2\n')
    elif fault=='extra_file':(stage/'unlisted.py').write_bytes(b'x')
    else:(stage/'unlisted').mkdir()
    before=tree(stage)
    with pytest.raises(ValueError):candidate.verify_staged_candidate(stage,archive,expected_sha256=pin)
    assert tree(stage)==before
