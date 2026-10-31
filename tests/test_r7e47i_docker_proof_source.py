"""Synthetic source interleavings and recorded Engine-unavailable acceptance."""
import copy
import importlib.util
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.skipif(os.name != 'nt', reason='Native Windows required')
spec = importlib.util.spec_from_file_location('source_fixture', ROOT/'scripts/volume_inspector/docker_proof_source.py')
m = importlib.util.module_from_spec(spec)
if os.name == 'nt': spec.loader.exec_module(m)


@pytest.fixture
def adapter(tmp_path):
    out = m.r.s.w.WindowsOutput.create_root(str(tmp_path/'source-evidence'))
    clock = m.r.FixtureClock()
    iso = lambda t: datetime.fromtimestamp(t, timezone.utc).isoformat()
    labels = {'atlas.project': 'projectatlas', 'atlas.inspection.instance': '11111111-1111-1111-1111-111111111111', 'atlas.inspection.operation': 'inspection-one'}
    helper = {'id':'c'*64, 'image':'sha256:'+'d'*64, 'manifest':'sha256:2ec3306c7d7e5714f49db15ea0db636622e01d061e87ceac27d0ec2bbd1b2574', 'labels':labels}
    daemon = {'id':'a'*64,'epoch':'b'*64,'endpoint':'npipe:////./pipe/dockerDesktopLinuxEngine'}
    container = {'Id':helper['id'],'Image':helper['image'],'Labels':labels,'Created':iso(900),
                 'State':{'Status':'exited','Running':False,'Pid':0,'StartedAt':iso(910),'FinishedAt':iso(990)}}
    image = {'Id':helper['image'],'Manifest':helper['manifest']}
    reader = m.SyntheticReader(daemon, container, image)
    value = m.DockerProofAdapter(reader, {'daemon':daemon,'helper':helper}, out, clock)
    try: yield value
    finally: out.close()


def test_exact_exit_with_stable_source(adapter):
    proof = adapter.collect()
    assert proof['status'] == 'EXITED' and proof['source'] == 'SYNTHETIC_READ_ONLY'
    assert [k for k,_ in adapter.reader.calls] == ['daemon','container','image','container','daemon']
    assert all(k in {'daemon','container','image'} for k,_ in adapter.reader.calls)
    with pytest.raises(m.Refused): adapter.production_recovery()


@pytest.mark.parametrize('case,status', [('running','RUNNING'),('missing','MISSING'),('image','REPLACED'),('labels','REPLACED'),
                                      ('replacement','REPLACED'),('contradiction','UNKNOWN'),('pid-bool','UNKNOWN'),('cached','UNKNOWN'),
                                      ('slow','UNKNOWN'),('disconnect','UNKNOWN'),('epoch-change','UNKNOWN'),('unknown-epoch','UNKNOWN'),
                                      ('daemon-change','UNKNOWN'),('remote','UNKNOWN'),('future','UNKNOWN')])
def test_fail_closed_source_conditions(adapter, case, status):
    reader = adapter.reader
    if case == 'running': reader.container['State'].update(Status='running', Running=True, Pid=123)
    elif case == 'missing': reader.container = None
    elif case == 'image': reader.image['Manifest'] = 'sha256:'+'f'*64
    elif case == 'labels': reader.container['Labels'] = {}
    elif case == 'replacement': reader.replacements[4] = {**copy.deepcopy(reader.container), 'Id':'f'*64}
    elif case == 'contradiction': reader.container['State']['Running'] = True
    elif case == 'pid-bool': reader.container['State']['Pid'] = False
    elif case == 'cached': reader.cached = True
    elif case == 'slow': reader.delay = 3
    elif case == 'disconnect': reader.available = False
    elif case == 'epoch-change': reader.replacements[5] = {**reader.daemon,'epoch':'f'*64}
    elif case == 'unknown-epoch': reader.daemon = {k:v for k,v in reader.daemon.items() if k != 'epoch'}
    elif case == 'daemon-change': reader.replacements[5] = {**reader.daemon,'id':'f'*64}
    elif case == 'remote': reader.daemon = {**reader.daemon,'endpoint':'tcp://remote:2375'}
    else: reader.container['State']['FinishedAt'] = '2999-01-01T00:00:00+00:00'
    assert adapter.collect()['status'] == status


def test_recorded_real_unavailability_is_not_exit(adapter):
    record = json.loads((ROOT/'tests/fixtures/r7e47i/docker-unavailable.json').read_text(encoding='utf-8-sig'))
    assert record['available'] is False
    source = m.RecordedUnavailableReader(record)
    value = m.DockerProofAdapter(source, adapter.expected, adapter.output, adapter.clock)
    result = value.collect()
    assert result['status'] == 'UNKNOWN' and result['reason'] == 'ENGINE_UNAVAILABLE'
    assert result['source'] == 'RECORDED_UNAVAILABLE' and len(source.calls) == 1


@pytest.mark.parametrize('case', ['oversized','malformed','wrong-nonce','wrong-type'])
def test_bounded_reader_rejection(adapter, monkeypatch, case):
    def read(*_args):
        if case == 'oversized': return b'x'*65537
        if case == 'malformed': return b'{'
        if case == 'wrong-nonce': return b'{"request":"cached","payload":{}}'
        return '{}'
    monkeypatch.setattr(m.SyntheticReader, 'read', read)
    assert adapter.collect()['status'] == 'UNKNOWN'


def test_persist_failure_cannot_return_proof(adapter, monkeypatch):
    def fail(*_args): raise OSError('Synthetic audit persistence unavailable')
    monkeypatch.setattr(adapter.output, '_write', fail)
    with pytest.raises(OSError): adapter.collect()


def test_manifest_and_daemon_identity_required(adapter):
    expected = copy.deepcopy(adapter.expected)
    expected['helper']['manifest'] = 'sha256:'+'f'*64
    with pytest.raises(m.Refused): m.DockerProofAdapter(adapter.reader, expected, adapter.output, adapter.clock)
    with pytest.raises(m.Refused): m.DockerProofAdapter(object(), adapter.expected, adapter.output, adapter.clock)
