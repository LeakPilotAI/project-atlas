"""Clean isolated archive builds a packet page pinned to its comparison toolchain."""
import hashlib
import json
import subprocess
import zipfile
from pathlib import Path

from test_offline_candidate_packaging import candidate, fixture_root


def test_clean_candidate_packet_viewer_pins_match_exported_packet(tmp_path, monkeypatch):
    source, _ = fixture_root(tmp_path, monkeypatch)
    repo = Path(__file__).resolve().parents[1]
    files = ['frontend/offline/forecast-accountability/packet-build.mjs',
             'frontend/offline/forecast-accountability/packet-mount.cjs',
             'frontend/offline/forecast-accountability/vintage-export.mjs',
             'frontend/offline/forecast-accountability/view.cjs',
             'frontend/offline/forecast-accountability/view.css',
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
    output = clean / 'packet.html'
    result = subprocess.run(['C:/Program Files/nodejs/node.exe', str(clean / files[0]), str(output)],
                            cwd=clean, capture_output=True, text=True, timeout=20, check=False)
    assert result.returncode == 0, result.stdout+result.stderr
    receipt = json.loads(result.stdout)
    assert receipt['sha256'] == hashlib.sha256(output.read_bytes()).hexdigest()
    assert receipt['production_approved'] is False
    assert receipt['native_browser_acceptance'] == 'NOT_ESTABLISHED'
    reports = json.loads((repo / 'tests/fixtures/afi-report-vintages-v1/reports.json').read_bytes())
    for name, report in [('left.json', reports[1]), ('right.json', reports[2])]:
        text = json.dumps(report, sort_keys=True)
        (clean / name).write_text(json.dumps({'schema': 'AFI_BROWSER_REPORT_V1', 'report_json': text,
                                            'payload_sha256': hashlib.sha256(text.encode()).hexdigest()}), encoding='utf8')
    packet = clean / 'packet.json'
    result = subprocess.run(['C:/Program Files/nodejs/node.exe', str(clean / files[2]), '--export',
                             str(clean / 'left.json'), str(clean / 'right.json'), str(packet)],
                            cwd=clean, capture_output=True, text=True, timeout=20, check=False)
    assert result.returncode == 0, result.stdout+result.stderr
    value = json.loads(packet.read_bytes())
    assert all(value[key] == pin for key, pin in receipt['source_pins'].items())
    html = output.read_text(encoding='utf8')
    assert "connect-src 'none'" in html
    assert 'packet-file' in html and 'packet-results' in html
    assert "connect-src 'none'" in html
    namespace = 'http://www.w3.org/2000/svg'
    remaining = html.replace(namespace, '')
    assert 'http://' not in remaining and 'https://' not in remaining
