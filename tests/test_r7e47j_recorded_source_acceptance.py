"""Replay actual J read-only projections: never production proof or fresh reads."""
import importlib.util
import json
import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT/'tests/fixtures/r7e47j'
pytestmark = pytest.mark.skipif(os.name != 'nt', reason='Native Windows required')
spec = importlib.util.spec_from_file_location('j_source', ROOT/'scripts/volume_inspector/docker_proof_source.py')
m = importlib.util.module_from_spec(spec)
if os.name == 'nt':
    spec.loader.exec_module(m)


def read(name):
    return json.loads((EVIDENCE/(name+'.json')).read_text())


def test_actual_engine_context_and_observation_bounds():
    before, after = read('engine-before'), read('engine-after')
    assert before['payload'] == after['payload']
    assert before['payload']['OSType'] == 'linux'
    assert read('context-desktop-linux')['payload']['DockerHost'] == 'npipe:////./pipe/dockerDesktopLinuxEngine'
    for name in ('engine-before', 'helper-before', 'image-pinned', 'helper-after', 'engine-after'):
        record = read(name)
        assert record['exit_code'] == 0 and not record['timeout']
        assert record['within_output_bound'] and record['elapsed_seconds'] < 2


def test_retained_helper_is_stable_but_not_production_inspection():
    helper = read('helper-before')['payload']
    assert helper == read('helper-after')['payload']
    assert helper['State']['Status'] == 'exited'
    assert helper['State']['Running'] is False and helper['State']['Pid'] == 0
    assert helper['Labels']['org.atlas.synthetic.operation'] == 'r7e46z-c5d18d33a88e42cc'
    assert 'atlas.inspection.instance' not in helper['Labels']


def test_actual_pinned_image_mapping():
    image = read('image-pinned')['payload']
    lock = json.loads((ROOT/'scripts/volume_inspector/helper-image-lock.json').read_text())
    assert image['Id'] == image['Descriptor']['digest'] == lock['proposed_manifest_digest']
    assert image['Id'] == read('helper-before')['payload']['Image']


@pytest.fixture
def plan(tmp_path):
    output = m.r.s.w.WindowsOutput.create_root(str(tmp_path/'recorded-audit'))
    # Explicitly synthetic expected plan. Actual records below are never relabeled.
    helper = read('helper-before')['payload']
    expected = {'id': helper['Id'], 'image': helper['Image'],
                'manifest': read('image-pinned')['payload']['Descriptor']['digest'],
                'labels': {'atlas.project': 'projectatlas', 'atlas.inspection.instance': '11111111-1111-1111-1111-111111111111',
                           'atlas.inspection.operation': 'synthetic-j-replay-only'}}
    daemon = {'id': 'a'*64, 'epoch': 'b'*64, 'endpoint': 'npipe:////./pipe/dockerDesktopLinuxEngine'}
    try:
        yield output, expected, daemon
    finally:
        output.close()


def test_actual_engine_has_no_trusted_generation_and_adapter_refuses(plan):
    output, helper, daemon = plan
    reader = m.SyntheticReader(read('engine-before')['payload'], read('helper-before')['payload'], read('image-pinned')['payload'])
    adapter = m.DockerProofAdapter(reader, {'daemon': daemon, 'helper': helper}, output, m.r.Clock())
    proof = adapter.collect()
    assert proof['source'] == 'SYNTHETIC_READ_ONLY'  # Recorded replay, never live authority.
    assert proof['status'] == 'UNKNOWN' and proof['fingerprint'] is None
    assert len(reader.calls) == 1
    assert list(Path(output.root).glob('source-audit-*.json'))


def test_actual_helper_cannot_substitute_for_production_ownership(plan):
    output, helper, _daemon = plan
    raw = read('image-pinned')['payload']
    image = {'Id': raw['Id'], 'Manifest': raw['Descriptor']['digest']}
    collector = m.r.ExitCollector(m.r.MockDocker(read('helper-before')['payload'], image), helper, output, m.r.Clock())
    proof = collector.collect()
    assert proof['status'] == 'REPLACED' and proof['fingerprint'] is None


@pytest.mark.parametrize('key', ['id', 'epoch'])
def test_actual_source_fields_cannot_be_used_as_generation_pin(plan, key):
    output, helper, daemon = plan
    daemon[key] = read('engine-before')['payload'].get('ID') if key == 'id' else None
    reader = m.SyntheticReader({}, None, None)
    with pytest.raises(m.Refused):
        m.DockerProofAdapter(reader, {'daemon': daemon, 'helper': helper}, output, m.r.Clock())


def test_no_unreviewed_live_reader_or_production_recovery(plan):
    output, helper, daemon = plan
    with pytest.raises(m.Refused):
        m.DockerProofAdapter(object(), {'daemon': daemon, 'helper': helper}, output, m.r.Clock())
    adapter = m.DockerProofAdapter(m.SyntheticReader({}, None, None), {'daemon': daemon, 'helper': helper}, output, m.r.Clock())
    with pytest.raises(m.Refused):
        adapter.production_recovery()
