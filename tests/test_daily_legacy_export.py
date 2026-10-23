"""Original V1 no-action bytes remain verifiable; new exports retain provenance."""
import hashlib
import json
from pathlib import Path

import pytest
from test_daily_afi_export import bundle, run

from scripts.observation_runtime import daily_afi_export as exporter
from scripts.observation_runtime.daily_forecast_visual import (
    render_daily_forecast_visual,
)


def legacy(root, *, request=None):
    request = bundle(root) if request is None else request
    artifacts, _, raw = exporter._plan(exporter.BundleReader(root), request)
    artifacts, name, raw = exporter._legacy_no_actions(artifacts, raw)
    for member, content in artifacts.items():
        (root/member).write_bytes(content)
    (root/name).write_bytes(raw)
    return name


def check(root, name):
    return exporter.verify_daily_export(bundle_root=root, binding_name=name,
                                        expected_binding_sha256=name[:-5])


def test_legacy_verifies_without_publishing_or_modifying_files(tmp_path, monkeypatch):
    name = legacy(tmp_path)
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    monkeypatch.setattr(exporter, 'publish_research_text', lambda *a, **k: pytest.fail('verification published'))
    assert check(tmp_path, name)['status'] == 'SYNTHETIC_DAILY_EXPORT_REPRODUCED'
    assert before == {p.name: p.read_bytes() for p in tmp_path.iterdir()}


def test_current_publisher_keeps_source_hashes_and_new_audit_fields(tmp_path):
    bundle(tmp_path)
    result = run(tmp_path)
    binding = json.loads((tmp_path/result['binding']).read_bytes())
    payload = json.loads((tmp_path/binding['artifacts']['records']).read_bytes())
    audit = json.loads((tmp_path/binding['artifacts']['audit']).read_bytes())
    assert all('source_sha256' in row for row in payload['records'])
    assert 'corporate_action_snapshots' in audit
    assert check(tmp_path, result['binding']) == result


def test_explicit_action_configuration_cannot_use_legacy_profile(tmp_path):
    request = bundle(tmp_path)
    request['action_snapshots'] = []
    artifacts, _, raw = exporter._plan(exporter.BundleReader(tmp_path), request)
    with pytest.raises(ValueError, match='Action-aware'):
        exporter._legacy_no_actions(artifacts, raw)


@pytest.mark.parametrize('fault', ['authority', 'status', 'extra', 'request', 'artifact'])
def test_rehashed_legacy_binding_cannot_bypass_exact_reconstruction(tmp_path, fault):
    name = legacy(tmp_path)
    value = json.loads((tmp_path/name).read_bytes())
    if fault == 'authority': value['startup_authorized'] = True
    if fault == 'status': value['dataset_status'] = 'APPROVED'
    if fault == 'extra': value['extra'] = True
    if fault == 'request': value['request']['symbol'] = 'AAPL'
    if fault == 'artifact': value['artifacts']['audit'] = '0'*64+'.json'
    raw = exporter._encode(value)
    name = hashlib.sha256(raw).hexdigest()+'.json'
    (tmp_path/name).write_bytes(raw)
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    with pytest.raises((ValueError, OSError)):
        check(tmp_path, name)
    assert before == {p.name: p.read_bytes() for p in tmp_path.iterdir()}


def test_old_retained_demo_reconstructs_against_original_caller_pin():
    root = Path(__file__).resolve().parents[1]/'logs/diagnostics/daily-visual-20261021/stock-etf-demo'
    name = 'ba6a5250956cd5acf9de3c98aadcfffa8daa52019210bce712b1170dc937b66e.json'
    before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in root.iterdir() if p.is_file()}
    assert check(root, name)['startup_authorized'] is False
    assert before == {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in root.iterdir() if p.is_file()}


def test_retained_visual_is_byte_identical_after_source_reconstruction():
    root = Path(__file__).resolve().parents[1]/'logs/diagnostics/daily-visual-20261021/stock-etf-demo'
    receipt = 'bcd5256c5b07b70a7cc829267e5d9c16a01a8390b6132f9dfa1b8aafc90fc7a3.json'
    raw = render_daily_forecast_visual(bundle_root=root, receipt_name=receipt,
                                      expected_receipt_sha256=receipt[:-5]).encode()
    pin = '1d5b998b2945ad677832eb9891cad61835c35556620590f3307d80d19a1d65ed'
    assert hashlib.sha256(raw).hexdigest() == pin
    assert (root/(pin+'.html')).read_bytes() == raw
