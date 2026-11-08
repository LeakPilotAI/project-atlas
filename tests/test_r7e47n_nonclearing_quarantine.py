"""Disposable native host records; no real helper or production resources."""
import copy
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.skipif(os.name != 'nt', reason='Native Windows required')
spec = importlib.util.spec_from_file_location('nonclearing_test', ROOT/'scripts/volume_inspector/nonclearing_quarantine.py')
m = importlib.util.module_from_spec(spec)
if os.name == 'nt': spec.loader.exec_module(m)


def tree(root):
    return {str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in Path(root).rglob('*') if p.is_file()}


@pytest.fixture
def fixture(tmp_path):
    store = m.s.SnapshotStore.provision_synthetic(str(tmp_path/'state'), str(tmp_path/'witness'))
    handoff = m.h.Handoff.provision_synthetic(store, str(tmp_path/'handoff'), m.h.ManualFixtureAuthority())
    handoff.inspect_synthetic('inspection-one','c'*64,approved=True)
    pin = copy.deepcopy(store.pin)
    resources = {}
    for role, output, leaf in [('snapshot', store.output, 'snapshot-00000001.json'),
                              ('witness', store.witness, 'commit-00000001.json'),
                              ('handoff', handoff.output, 'ack-00000001.json')]:
        _, file = m.s.read_bound(output, leaf)
        resources[role] = {'root':output.root, 'root_id':m.s.native.file_identity(output.root_handle), 'leaf':leaf,'file':file}
    output = m.w.WindowsOutput.create_root(str(tmp_path/'separate-evidence'))
    scope = m.SyntheticScope(pin, resources, 1)
    operation = m.NonClearing(scope, output)
    try: yield operation, handoff, scope
    finally:
        output.close()
        handoff.close()


@pytest.mark.parametrize('helper', ['EXITED','RUNNING','MISSING','REPLACED','STALE','UNAVAILABLE','UNKNOWN'])
def test_advisory_helper_never_grants_permission_or_changes_source(fixture, helper):
    op, handoff, scope = fixture
    before = {role:tree(Path(v['root'])) for role,v in scope.resources.items()}
    record = op.observe_and_record('quarantine-one', helper)
    assert not record['startup_permission'] and not record['recovery_authorized'] and not record['helper_exit_proven']
    assert before == {role:tree(Path(v['root'])) for role,v in scope.resources.items()}
    assert op.read_record('quarantine-one') == record
    assert handoff.store.snapshot()['inspection']['phase'] == 'UNCERTAIN'
    with pytest.raises(m.Refused): op.startup()
    with pytest.raises(m.Refused): op.recover()


def test_locked_writer_denied_but_new_file_not_excluded(fixture, monkeypatch):
    op, _handoff, scope = fixture
    def competing():
        source = scope.resources['snapshot']
        with pytest.raises(OSError): (Path(source['root'])/source['leaf']).open('r+b')
        with m.w.WindowsOutput(source['root']) as root:
            root._write(root.root_handle,'beside.json',b'{"test":true}')
    monkeypatch.setattr(op,'_locked',competing)
    result = op.observe_and_record('quarantine-one')
    assert not result['external_writer_exclusion']
    assert (Path(scope.resources['snapshot']['root'])/'beside.json').exists()


def test_existing_writer_refuses_without_publishing(fixture):
    op, _handoff, scope = fixture
    source = scope.resources['snapshot']
    with (Path(source['root'])/source['leaf']).open('r+b'), pytest.raises(OSError):
        op.observe_and_record('quarantine-one')
    assert not (Path(op.output.root)/'quarantine-one.commit').exists()


@pytest.mark.parametrize('role', ['snapshot','witness','handoff'])
def test_corruption_refuses_without_source_repair_or_poison(fixture, role):
    op, _handoff, scope = fixture
    v = scope.resources[role]
    (Path(v['root'])/v['leaf']).write_bytes(b'{}')
    before = {key:tree(Path(x['root'])) for key,x in scope.resources.items()}
    with pytest.raises(m.Refused): op.observe_and_record('quarantine-one')
    assert before == {key:tree(Path(x['root'])) for key,x in scope.resources.items()}


def test_replaced_source_refused(fixture):
    op, _handoff, scope = fixture
    v = scope.resources['snapshot']
    with m.w.WindowsOutput(v['root']) as root:
        root._write(root.root_handle,'replacement.json',(Path(v['root'])/v['leaf']).read_bytes())
    os.replace(Path(v['root'])/'replacement.json', Path(v['root'])/v['leaf'])
    with pytest.raises(m.Refused): op.observe_and_record('quarantine-one')


def test_stale_pin_and_known_newer_intent_refuse(fixture):
    op, _handoff, scope = fixture
    with m.w.WindowsOutput(scope.resources['witness']['root']) as root:
        root._write(root.root_handle,'intent-00000002.json',b'{"synthetic":"unresolved"}')
    with pytest.raises(m.Refused): op.observe_and_record('quarantine-one')
    assert not (Path(op.output.root)/'quarantine-one.commit').exists()


def test_replay_does_not_replace_record(fixture):
    op, _handoff, _scope = fixture
    op.observe_and_record('quarantine-one')
    before = tree(Path(op.output.root))
    with pytest.raises(FileExistsError): op.observe_and_record('quarantine-one')
    assert tree(Path(op.output.root)) == before


def test_wrong_revision_refuses(fixture):
    op, _handoff, _scope = fixture
    op.scope.pin['revision'] += 1
    with pytest.raises(m.Refused): op.observe_and_record('quarantine-one')


def test_record_does_not_validate_against_new_revision(fixture):
    op, _handoff, _scope = fixture
    op.observe_and_record('quarantine-one')
    op.scope.pin['revision'] += 1
    with pytest.raises(m.Refused): op.read_record('quarantine-one')


@pytest.mark.parametrize('stage', ['audit','commit'])
def test_partial_quarantine_not_complete_and_no_replay(fixture, monkeypatch, stage):
    op, _handoff, scope = fixture
    before = {key:tree(Path(x['root'])) for key,x in scope.resources.items()}
    original = op.output._write
    def interrupt(handle,name,data):
        if name.endswith('.'+stage): raise OSError('Synthetic publication interruption')
        return original(handle,name,data)
    monkeypatch.setattr(op.output,'_write',interrupt)
    with pytest.raises(OSError): op.observe_and_record('quarantine-one')
    monkeypatch.setattr(op.output,'_write',original)
    with pytest.raises((OSError,m.Refused)): op.read_record('quarantine-one')
    with pytest.raises(FileExistsError): op.observe_and_record('quarantine-one')
    assert before == {key:tree(Path(x['root'])) for key,x in scope.resources.items()}


def test_incomplete_audit_or_tampering_refused(fixture):
    op, _handoff, _scope = fixture
    op.observe_and_record('quarantine-one')
    (Path(op.output.root)/'quarantine-one.audit').write_bytes(b'{}')
    with pytest.raises(m.Refused): op.read_record('quarantine-one')


def test_start_after_quarantine_still_refused(fixture):
    op, handoff, _scope = fixture
    op.observe_and_record('quarantine-one')
    with pytest.raises(m.Refused):
        handoff.start_synthetic('start-one',{'pid':1,'created':1,'exe':'a'*64,'command':'b'*64})
    assert handoff.store.snapshot()['startup'] is None


def test_output_overlap_rejected(fixture):
    _op, handoff, scope = fixture
    with pytest.raises(m.Refused): m.NonClearing(scope, handoff.output)


def test_output_permission_verification_failure_refuses(fixture, monkeypatch):
    op, _handoff, scope = fixture
    before = {key:tree(Path(x['root'])) for key,x in scope.resources.items()}
    def denied(): raise PermissionError('Synthetic output permission failure')
    monkeypatch.setattr(op.output,'_verify',denied)
    with pytest.raises(PermissionError): op.observe_and_record('quarantine-one')
    assert not (Path(op.output.root)/'quarantine-one.commit').exists()
    assert before == {key:tree(Path(x['root'])) for key,x in scope.resources.items()}


@pytest.mark.parametrize('role', ['parent','worker'])
def test_fixture_crash_retains_uncertainty_and_partial_record(fixture, tmp_path, role):
    op, _handoff, scope = fixture
    argsfile = tmp_path/'fixture-input.json'
    argsfile.write_text(json.dumps({'pin':scope.pin,'resources':scope.resources,'sequence':scope.sequence,'output':op.output.root}))
    code = "import importlib.util,json,os,sys; s=importlib.util.spec_from_file_location('child_nonclear',sys.argv[1]); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); a=json.load(open(sys.argv[2])); o=m.w.WindowsOutput(a['output']); old=o._write; o._write=lambda h,n,d: os._exit(23) if n.endswith('.audit') else old(h,n,d); x=m.NonClearing(m.SyntheticScope(a['pin'],a['resources'],a['sequence']),o); x.observe_and_record('quarantine-one')"
    before = {key:tree(Path(x['root'])) for key,x in scope.resources.items()}
    run = subprocess.run([sys.executable,'-c',code,str(ROOT/'scripts/volume_inspector/nonclearing_quarantine.py'),str(argsfile)],capture_output=True,timeout=8,check=False)
    assert run.returncode == 23, (role,run.stderr)
    with pytest.raises((OSError,m.Refused)): op.read_record('quarantine-one')
    assert before == {key:tree(Path(x['root'])) for key,x in scope.resources.items()}
