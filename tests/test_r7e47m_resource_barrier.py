"""Native disposable-file exclusion and explicit scope counterexamples."""
import copy
import importlib.util
import json
import mmap
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.skipif(os.name != 'nt', reason='Native Windows required')
spec = importlib.util.spec_from_file_location('barrier_test', ROOT/'scripts/volume_inspector/resource_barrier.py')
m = importlib.util.module_from_spec(spec)
if os.name == 'nt': spec.loader.exec_module(m)
FACTS = {'source':'SYNTHETIC', 'helper':'EXITED', 'identity':'MATCH', 'docker':'AVAILABLE', 'external_writer':'NONE'}


@pytest.fixture
def resource(tmp_path):
    root = str(tmp_path/'scope')
    with m.w.WindowsOutput.create_root(root) as output:
        output._write(output.root_handle, 'resource.json', b'{"fixture":true}')
        _, file = m.s.read_bound(output, 'resource.json')
        pin = {'root_id': m.s.native.file_identity(output.root_handle), 'file': file}
    return root, pin


@pytest.mark.parametrize('phase', ['INSPECTION', 'RECOVERY'])
def test_ordinary_writes_and_replacement_denied_while_held(resource, phase):
    root, pin = resource
    lease = m.FileLease(root, pin, phase, FACTS)
    try:
        target = Path(root)/'resource.json'
        with pytest.raises(OSError): target.open('r+b')
        replacement = Path(root)/'replacement.json'
        replacement.write_bytes(b'{}')
        with pytest.raises(OSError): os.replace(replacement, target)
        assert lease.assert_held(lease.token)['production_recovery'] is False
        with pytest.raises(m.Refused): lease.production_recovery()
    finally: lease.close()


def test_concurrent_admission_single_winner(resource):
    root, pin = resource
    def acquire(_):
        try: return m.FileLease(root, pin, 'INSPECTION', FACTS)
        except (OSError, m.Refused): return None
    with ThreadPoolExecutor(max_workers=4) as pool:
        leases = list(pool.map(acquire, range(4)))
    try: assert sum(x is not None for x in leases) == 1
    finally:
        for lease in leases:
            if lease: lease.close()


@pytest.mark.parametrize('field,value', [('helper','RUNNING'), ('helper','MISSING'), ('helper','UNKNOWN'),
    ('identity','REPLACED'), ('docker','UNAVAILABLE'), ('external_writer','UNKNOWN'), ('external_writer','ACTIVE')])
def test_uncertainty_refuses(resource, field, value):
    root, pin = resource
    with pytest.raises(m.Refused): m.FileLease(root, pin, 'INSPECTION', {**FACTS, field:value})
    assert not (Path(root)/'barrier-intent.json').exists()


def test_release_stale_token_and_replay(resource):
    root, pin = resource
    lease = m.FileLease(root, pin, 'RECOVERY', FACTS)
    try:
        bad = {**copy.deepcopy(lease.token), 'nonce':'f'*32}
        with pytest.raises(m.Refused): lease.release(bad)
        lease.release(lease.token)
        with pytest.raises(m.Refused): lease.release(lease.token)
        with pytest.raises(FileExistsError): m.FileLease(root, pin, 'RECOVERY', FACTS)
        # Kernel lease ended; durable admission intent still prevents cooperative reuse.
        with (Path(root)/'resource.json').open('r+b') as stream: stream.write(b'{')
    finally: lease.close()


def test_existing_writer_interrupts_acquisition_and_preserves_fence(resource):
    root, pin = resource
    with (Path(root)/'resource.json').open('r+b'), pytest.raises(OSError):
        m.FileLease(root, pin, 'INSPECTION', FACTS)
    assert (Path(root)/'barrier-intent.json').exists()
    with pytest.raises(FileExistsError): m.FileLease(root, pin, 'INSPECTION', FACTS)


def test_interrupted_release_keeps_refusal(resource, monkeypatch):
    root, pin = resource
    lease = m.FileLease(root, pin, 'RECOVERY', FACTS)
    def fail(*_args): raise OSError('Synthetic release interruption')
    monkeypatch.setattr(lease.output, '_write', fail)
    try:
        with pytest.raises(OSError): lease.release(lease.token)
        with pytest.raises(OSError): (Path(root)/'resource.json').open('r+b')
    finally: lease.close()
    with pytest.raises(FileExistsError): m.FileLease(root, pin, 'RECOVERY', FACTS)


def test_other_files_not_excluded(resource):
    root, pin = resource
    lease = m.FileLease(root, pin, 'INSPECTION', FACTS)
    try:
        with m.w.WindowsOutput(root) as other:
            other._write(other.root_handle, 'uncovered.json', b'{"counterexample":true}')
        assert (Path(root)/'uncovered.json').exists()
    finally: lease.close()


def test_preexisting_mapping_is_not_claimed_excluded(resource):
    root, pin = resource
    with (Path(root)/'resource.json').open('r+b') as stream:
        view = mmap.mmap(stream.fileno(), 0, access=mmap.ACCESS_WRITE)
    lease = None
    try:
        try: lease = m.FileLease(root, pin, 'INSPECTION', FACTS)
        except OSError:
            (Path(root).parent/'mapping-result.json').write_text('{"result":"KERNEL_REFUSED_LEASE"}')
            return  # Kernel refused; no false quiescence inference.
        view[0:1] = b'['
        view.flush()
        with pytest.raises(m.Refused): lease.assert_held(lease.token)
        (Path(root).parent/'mapping-result.json').write_text('{"result":"EXISTING_MAPPING_CHANGED_HELD_FILE"}')
    finally:
        if lease: lease.close()
        view.close()


@pytest.mark.parametrize('role', ['parent', 'worker'])
def test_synthetic_process_crash_releases_kernel_handle_not_durable_fence(resource, tmp_path, role):
    root, pin = resource
    argsfile = tmp_path/'input.json'
    argsfile.write_text(json.dumps({'root': root, 'pin': pin, 'facts': FACTS}))
    code = "import importlib.util,json,os,sys; s=importlib.util.spec_from_file_location('child_barrier',sys.argv[1]); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); a=json.load(open(sys.argv[2])); x=m.FileLease(a['root'],a['pin'],'INSPECTION',a['facts']); os._exit(23)"
    run = subprocess.run([sys.executable, '-c', code, str(ROOT/'scripts/volume_inspector/resource_barrier.py'), str(argsfile)], capture_output=True, timeout=8, check=False)
    assert run.returncode == 23, (role, run.stderr)
    with (Path(root)/'resource.json').open('r+b'): pass
    with pytest.raises(FileExistsError): m.FileLease(root, pin, 'INSPECTION', FACTS)


def test_file_replaced_before_acquisition_refused(resource):
    root, pin = resource
    target = Path(root)/'resource.json'
    replacement = Path(root)/'alternate.json'
    with m.w.WindowsOutput(root) as output:
        output._write(output.root_handle, 'alternate.json', target.read_bytes())
    os.replace(replacement, target)
    with pytest.raises(m.Refused): m.FileLease(root, pin, 'RECOVERY', FACTS)
