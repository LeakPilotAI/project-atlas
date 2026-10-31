"""Archive/extract the explicit offline report-vintage exporter and dependencies."""
import hashlib
import json
import subprocess
import zipfile
from pathlib import Path

from test_offline_candidate_packaging import candidate, fixture_root


def test_clean_candidate_exports_and_reproduces_vintage_packet(tmp_path, monkeypatch):
    source, _ = fixture_root(tmp_path, monkeypatch)
    repo = Path(__file__).resolve().parents[1]
    files = ['frontend/offline/forecast-accountability/vintage-export.mjs',
             'frontend/offline/forecast-accountability/view.cjs',
             'frontend/offline/market-replay/artifact-io.mjs']
    for name in files:
        target = source / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((repo / name).read_bytes())
    previous = candidate.git
    monkeypatch.setattr(candidate, 'git', lambda *args: previous(*args)+files if '--others' in args else previous(*args))
    candidate.build(tmp_path / 'candidate')
    clean = tmp_path / 'clean'
    with zipfile.ZipFile(tmp_path / 'candidate/atlas-source.zip') as archive:
        archive.extractall(clean)
    reports = json.loads((repo / 'tests/fixtures/afi-report-vintages-v1/reports.json').read_bytes())
    for name, report in [('left.json', reports[1]), ('right.json', reports[2])]:
        text = json.dumps(report, sort_keys=True)
        (clean / name).write_text(json.dumps({'schema': 'AFI_BROWSER_REPORT_V1', 'report_json': text,
                                            'payload_sha256': hashlib.sha256(text.encode()).hexdigest()}), encoding='utf8')
    script = clean / files[0]
    output = clean / 'comparison.json'
    result = subprocess.run(['C:/Program Files/nodejs/node.exe', str(script), '--export',
                             str(clean / 'left.json'), str(clean / 'right.json'), str(output)],
                            cwd=clean, capture_output=True, text=True, timeout=20, check=False)
    assert result.returncode == 0, result.stdout+result.stderr
    receipt = json.loads(result.stdout)
    assert receipt['sha256'] == hashlib.sha256(output.read_bytes()).hexdigest()
    assert receipt['production_approved'] is False
    verify = subprocess.run(['C:/Program Files/nodejs/node.exe', str(script), '--verify', str(output)],
                            cwd=clean, capture_output=True, text=True, timeout=20, check=False)
    assert verify.returncode == 0, verify.stdout+verify.stderr
    value = json.loads(verify.stdout)
    assert value['status'] == 'VERIFIED_SUPPLIED_BYTES'
    assert value['union_forecast_n'] == 1
    assert value['source_authenticated'] is value['production_approved'] is False
