"""Offline source packaging retains inert viewers and their native Node tests."""
import hashlib
import importlib.util
import json
import subprocess
import zipfile
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location('atlas_candidate', Path(__file__).resolve().parents[1] / 'scripts/build_release_candidate.py')
candidate = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(candidate)


def fixture_root(tmp_path, monkeypatch):
    root = tmp_path / 'source'
    files = {
        'backend/app/example.py': b'VALUE = 1\n',
        'frontend/offline/research/view.cjs': b"module.exports = {value: 7};\n",
        'frontend/offline/research/view.test.mjs': b"import {createRequire} from 'node:module'; const require=createRequire(import.meta.url); if(require('./view.cjs').value!==7) throw Error('missing source');\n",
        'frontend/offline/research/style.css': b'body { color: white; }\n',
        'frontend/offline/research/README.md': b'Synthetic only.\n',
        'frontend/offline/research/.env': b'NEVER_PACKAGE=fixture\n',
        'frontend/offline/research/output.bin': b'fixture',
        'frontend/.next/private.js': b'not an offline source',
        'backend/app/static/vendor/lightweight-charts.LICENSE': b'fixture license',
        'scripts/build_release_candidate.py': b'# fixture packager\n',
    }
    for name, content in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    tracked = ['backend/app/example.py']
    untracked = [p for p in files if p not in tracked]
    def git(*args):
        if args[:2] == ('branch', '--show-current'):
            return ['fixture-branch']
        if args[:2] == ('rev-parse', 'HEAD'):
            return ['fixture-head']
        if '--others' in args:
            roots = [x + '/' for x in args[3:]]
            return [p for p in untracked if p.startswith(tuple(roots))]
        return tracked
    monkeypatch.setattr(candidate, 'ROOT', root)
    monkeypatch.setattr(candidate, 'git', git)
    monkeypatch.setattr(candidate.importlib.metadata, 'distributions', list)
    return root, tracked


def test_offline_viewer_and_native_tests_survive_clean_extraction(tmp_path, monkeypatch):
    fixture_root(tmp_path, monkeypatch)
    destination = tmp_path / 'candidate'
    digest = candidate.build(destination)
    archive = destination / 'atlas-source.zip'
    assert hashlib.sha256(archive.read_bytes()).hexdigest() == digest
    with zipfile.ZipFile(archive) as bundle:
        names = set(bundle.namelist())
        assert 'frontend/offline/research/view.cjs' in names
        assert 'frontend/offline/research/view.test.mjs' in names
        assert 'frontend/offline/research/style.css' in names
        assert not any('.env' in p or '.next' in p or p.endswith('.bin') for p in names)
        extracted = tmp_path / 'extracted'
        bundle.extractall(extracted)
    manifest = json.loads((extracted / 'release-manifest.json').read_text(encoding='utf-8'))
    assert manifest['activation_approved'] is False
    for entry in manifest['files']:
        raw = (extracted / entry['path']).read_bytes()
        assert len(raw) == entry['bytes']
        assert hashlib.sha256(raw).hexdigest() == entry['sha256']
    result = subprocess.run(['C:/Program Files/nodejs/node.exe', '--test', str(extracted / 'frontend/offline/research/view.test.mjs')], capture_output=True, text=True, timeout=20, check=False)
    assert result.returncode == 0, result.stdout + result.stderr


def test_same_inputs_produce_identical_source_archives(tmp_path, monkeypatch):
    fixture_root(tmp_path, monkeypatch)
    assert candidate.build(tmp_path / 'first') == candidate.build(tmp_path / 'second')


def test_existing_destination_never_overwritten(tmp_path, monkeypatch):
    fixture_root(tmp_path, monkeypatch)
    destination = tmp_path / 'candidate'
    destination.mkdir()
    marker = destination / 'preserve.txt'
    marker.write_bytes(b'original')
    with pytest.raises(FileExistsError):
        candidate.build(destination)
    assert marker.read_bytes() == b'original'


@pytest.mark.parametrize('name', ['data/records.json', 'backend/app/.env', 'backend/app/__pycache__/state.py'])
def test_unsafe_tracked_input_refuses(tmp_path, monkeypatch, name):
    root, tracked = fixture_root(tmp_path, monkeypatch)
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b'synthetic unsafe input')
    tracked.append(name)
    with pytest.raises(ValueError, match='Unsafe release input'):
        candidate.build(tmp_path / 'candidate')

def test_actual_paired_viewer_builds_and_tests_from_extracted_candidate(tmp_path, monkeypatch):
    root, _ = fixture_root(tmp_path, monkeypatch)
    repo = Path(__file__).resolve().parents[1]
    selected = [
        'frontend/offline/forecast-accountability/view.cjs',
        'frontend/offline/forecast-accountability/view.css',
        'frontend/offline/forecast-accountability/build.cjs',
        'frontend/offline/forecast-accountability/paired-log-loss.test.mjs',
        'tests/fixtures/afi-log-loss-v1/corrected-browser.json',
        'tests/fixtures/afi-log-loss-v2/corrected-browser.json',
    ]
    for name in selected:
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((repo / name).read_bytes())
    previous = candidate.git
    monkeypatch.setattr(candidate, 'git', lambda *args: previous(*args) + selected if '--others' in args else previous(*args))
    destination = tmp_path / 'candidate'
    candidate.build(destination)
    extracted = tmp_path / 'clean'
    with zipfile.ZipFile(destination / 'atlas-source.zip') as bundle:
        bundle.extractall(extracted)
    viewer = extracted / 'frontend/offline/forecast-accountability'
    node = 'C:/Program Files/nodejs/node.exe'
    result = subprocess.run([node, '--test', str(viewer / 'paired-log-loss.test.mjs')], capture_output=True, text=True, timeout=30, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'pass 23' in result.stdout
    output = extracted / 'research-viewer.html'
    result = subprocess.run([node, str(viewer / 'build.cjs'), str(output)], capture_output=True, text=True, timeout=20, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
    html = output.read_text(encoding='utf-8')
    assert "connect-src 'none'" in html
    assert 'Matched-case logarithmic loss' in html

def test_extracted_python_companion_recomputes_pinned_v2_without_checkout_imports(tmp_path, monkeypatch):
    import os
    import sys

    root, _ = fixture_root(tmp_path, monkeypatch)
    repo = Path(__file__).resolve().parents[1]
    selected = ['backend/app/__init__.py', 'tests/fixtures/afi-log-loss-v2/corrected-browser.json']
    for directory in ['backend/app/backtest', 'scripts/observation_runtime']:
        selected.extend(str(p.relative_to(repo)).replace('\\', '/') for p in sorted((repo / directory).glob('*.py')))
    for name in selected:
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((repo / name).read_bytes())
    previous = candidate.git
    monkeypatch.setattr(candidate, 'git', lambda *args: previous(*args) + selected if '--others' in args else previous(*args))
    destination = tmp_path / 'candidate'
    candidate.build(destination)
    extracted = tmp_path / 'clean'
    with zipfile.ZipFile(destination / 'atlas-source.zip') as bundle:
        bundle.extractall(extracted)
    code = '''
import sys,json,pathlib
from datetime import datetime
root=pathlib.Path.cwd()
def guard(event,args):
    if event=='socket.connect':raise PermissionError('offline extracted acceptance')
sys.addaudithook(guard)
import scripts.observation_runtime.forecast_paired_log_loss as module
assert pathlib.Path(module.__file__).resolve().is_relative_to(root)
value=json.loads((root/'tests/fixtures/afi-log-loss-v2/corrected-browser.json').read_text(encoding='utf-8'))
report=json.loads(value['source_report_json']);expected=json.loads(value['diagnostics_json'])
actual=module.with_paired_log_loss(report['rows'],asof=datetime.fromisoformat(report['asof']),model_pairs=value['model_pairs'],minimum_samples=expected['minimum_samples'])
assert actual==expected
print('EXTRACTED_V2_EXACT_RECOMPUTATION_PASS')
'''
    environment = dict(os.environ)
    environment['PYTHONPATH'] = str(extracted / 'backend') + os.pathsep + str(extracted)
    environment['PYTHONDONTWRITEBYTECODE'] = '1'
    result = subprocess.run([sys.executable, '-c', code], cwd=extracted, env=environment, capture_output=True, text=True, timeout=30, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'EXTRACTED_V2_EXACT_RECOMPUTATION_PASS' in result.stdout
