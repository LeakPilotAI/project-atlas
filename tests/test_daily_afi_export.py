"""Explicit bundle export cannot grant source, startup or trading authority."""
import hashlib
import json

import pytest
from test_daily_afi_bridge import POLICY, chart, encode, universe

from scripts.observation_runtime import daily_afi_export as exporter


def bundle(root):
    raw = encode(chart(['2026-10-19', '2026-10-20']))
    pin = hashlib.sha256(raw).hexdigest()
    (root/(pin+'.json')).write_bytes(raw)
    request = {'schema': 'ATLAS_SYNTHETIC_DAILY_EXPORT_REQUEST_V1',
               'snapshots': [{'file': pin+'.json', 'sha256': pin, 'received_at': '2026-10-20T21:00:00+00:00'}],
               'symbol': 'SPY', 'asset_class': 'US_ETF', 'universe': universe(),
               'dataset_id': 'daily-export', 'version': 'v1', 'asof': '2026-10-20T22:00:00+00:00', **POLICY}
    (root/'request.json').write_bytes(encode(request))
    return request


def run(root):
    return exporter.export_daily_dataset(bundle_root=root, request_name='request.json', output_root=root)


def test_reproduce_idempotently(tmp_path):
    bundle(tmp_path)
    result = run(tmp_path)
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    assert run(tmp_path) == result
    assert before == {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    assert result['startup_authorized'] is False
    assert result['trading_authorized'] is False
    assert exporter.verify_daily_export(bundle_root=tmp_path, binding_name=result['binding'],
                                        expected_binding_sha256=result['binding'][:-5]) == result


def test_action_receipts_are_pinned_and_reconstructed(tmp_path):
    request = bundle(tmp_path)
    raw = encode({'schema': 'ATLAS_SYNTHETIC_CORPORATE_ACTIONS_V1', 'asset_id': 'ETF:SPY',
                  'actions': [{'action_id': 'split-1', 'kind': 'SPLIT',
                               'effective_at': '2026-10-20T21:00:00+00:00', 'amount': 2,
                               'economic_unit': 'NEW_SHARES_PER_OLD_SHARE'}]})
    pin = hashlib.sha256(raw).hexdigest()
    (tmp_path/(pin+'.json')).write_bytes(raw)
    request['action_snapshots'] = [{'file': pin+'.json', 'sha256': pin,
                                    'received_at': '2026-10-20T22:00:00+00:00',
                                    'source_id': 'fixture-actions'}]
    request['asof'] = '2026-10-20T23:00:00+00:00'
    (tmp_path/'request.json').write_bytes(encode(request))
    result = run(tmp_path)
    binding = json.loads((tmp_path/result['binding']).read_bytes())
    audit = json.loads((tmp_path/binding['artifacts']['audit']).read_bytes())
    assert binding['request']['action_snapshots'] == request['action_snapshots']
    assert audit['corporate_action_provenance'][0]['source_id'] == 'fixture-actions'
    assert exporter.verify_daily_export(bundle_root=tmp_path, binding_name=result['binding'],
                                        expected_binding_sha256=result['binding'][:-5]) == result
    (tmp_path/(pin+'.json')).write_bytes(b'{}')
    with pytest.raises(ValueError):
        exporter.verify_daily_export(bundle_root=tmp_path, binding_name=result['binding'],
                                     expected_binding_sha256=result['binding'][:-5])


@pytest.mark.parametrize('kind', ['pin', 'path', 'policy', 'missing', 'extra'])
def test_bad_request_no_publication(tmp_path, kind):
    request = bundle(tmp_path)
    if kind == 'pin':
        request['snapshots'][0]['sha256'] = '0'*64
    elif kind == 'path':
        request['snapshots'][0]['file'] = '../escape.json'
    elif kind == 'policy':
        request['fixture_mode'] = 'LIVE'
    elif kind == 'missing':
        del request['universe']
    else:
        request['startup_authorized'] = True
    (tmp_path/'request.json').write_bytes(encode(request))
    before = set(tmp_path.iterdir())
    with pytest.raises(ValueError):
        run(tmp_path)
    assert before == set(tmp_path.iterdir())


def test_partial_failure_retained_then_retry(tmp_path, monkeypatch):
    bundle(tmp_path)
    original = exporter.publish_research_text
    calls = []

    def fail(root, text, **kwargs):
        calls.append(text)
        if len(calls) == 2:
            raise OSError('synthetic storage failure')
        return original(root, text, **kwargs)

    monkeypatch.setattr(exporter, 'publish_research_text', fail)
    with pytest.raises(OSError, match='storage'):
        run(tmp_path)
    assert len(list(tmp_path.iterdir())) == 3
    monkeypatch.setattr(exporter, 'publish_research_text', original)
    assert run(tmp_path)['status'] == 'SYNTHETIC_DAILY_EXPORT_REPRODUCED'


def test_tampered_output_refused(tmp_path):
    bundle(tmp_path)
    result = run(tmp_path)
    binding = json.loads((tmp_path/result['binding']).read_bytes())
    (tmp_path/binding['artifacts']['records']).write_bytes(b'{}')
    with pytest.raises(ValueError):
        exporter.verify_daily_export(bundle_root=tmp_path, binding_name=result['binding'],
                                     expected_binding_sha256=result['binding'][:-5])


def test_output_root_must_retain_inputs(tmp_path):
    bundle(tmp_path)
    out = tmp_path/'out'
    out.mkdir()
    with pytest.raises(ValueError):
        exporter.export_daily_dataset(bundle_root=tmp_path, request_name='request.json', output_root=out)
    assert not list(out.iterdir())


def test_cli_requires_explicit_mode_and_root():
    with pytest.raises(SystemExit) as exc:
        exporter.main([])
    assert exc.value.code == 2


def test_cli_roundtrip_and_missing_source_refusal(tmp_path, capsys):
    request = bundle(tmp_path)
    assert exporter.main(['--bundle-root', str(tmp_path), '--request', 'request.json',
                          '--output-root', str(tmp_path)]) == 0
    result = json.loads(capsys.readouterr().out)
    args = ['--bundle-root', str(tmp_path), '--verify-binding', result['binding'],
            '--expected-binding-sha256', result['binding'][:-5]]
    assert exporter.main(args) == 0
    capsys.readouterr()
    # Retain the original source as failure evidence while making its expected
    # identity unavailable; no missing source can be inferred as harmless.
    source = tmp_path/request['snapshots'][0]['file']
    source.rename(tmp_path/'retained-source.json')
    with pytest.raises(SystemExit) as exc:
        exporter.main(args)
    assert exc.value.code == 2
    assert 'refused' in capsys.readouterr().err
    assert (tmp_path/result['binding']).is_file()


@pytest.mark.parametrize('args', [
    ['--request', 'request.json'],
    ['--verify-binding', '0.json', '--output-root', 'unused'],
])
def test_cli_ambiguous_arguments_refused(tmp_path, args):
    with pytest.raises(SystemExit) as exc:
        exporter.main(['--bundle-root', str(tmp_path), *args])
    assert exc.value.code == 2
