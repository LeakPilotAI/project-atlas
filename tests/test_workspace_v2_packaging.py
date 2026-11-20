"""Clean V2 workspace packaging retains V1 dependencies and includes the packet toolchain."""
import json
import subprocess
import zipfile
from pathlib import Path

from test_offline_candidate_packaging import candidate, fixture_root


def test_clean_candidate_builds_and_verifies_workspace_v2(tmp_path, monkeypatch):
    source, _ = fixture_root(tmp_path, monkeypatch)
    repo = Path(__file__).resolve().parents[1]
    files = ['frontend/offline/workspace/build-v2.mjs', 'frontend/offline/workspace/build.mjs',
             'frontend/offline/market-replay/build.mjs', 'frontend/offline/market-replay/view.cjs',
             'frontend/offline/market-replay/mount.cjs', 'frontend/offline/market-replay/artifact-io.mjs',
             'frontend/offline/forecast-accountability/build.cjs', 'frontend/offline/forecast-accountability/view.cjs',
             'frontend/offline/forecast-accountability/view.css', 'frontend/offline/forecast-accountability/packet-build.mjs',
             'frontend/offline/forecast-accountability/packet-mount.cjs', 'frontend/offline/forecast-accountability/vintage-export.mjs']
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
    output = clean / 'workspace-v2'
    result = subprocess.run(['C:/Program Files/nodejs/node.exe', str(clean / files[0]), str(output)],
                            cwd=clean, capture_output=True, text=True, timeout=20, check=False)
    assert result.returncode == 0, result.stdout+result.stderr
    receipt = json.loads(result.stdout)
    assert receipt['schema'] == 'ATLAS_OFFLINE_EVIDENCE_WORKSPACE_V2'
    assert receipt['production_approved'] is False
    verify = subprocess.run(['C:/Program Files/nodejs/node.exe', str(clean / files[1]), '--verify', str(output),
                             '--expected-manifest-sha256', receipt['manifest_sha256']],
                            cwd=clean, capture_output=True, text=True, timeout=20, check=False)
    assert verify.returncode == 0, verify.stdout+verify.stderr
    value = json.loads(verify.stdout)
    assert value['schema'] == 'ATLAS_OFFLINE_EVIDENCE_WORKSPACE_VERIFIED_V2'
    assert value['files'] == 5 and value['supplied_bytes_consistent'] is True
    assert value['native_browser_acceptance'] == 'NOT_ESTABLISHED'
    assert {file.name for file in output.iterdir()} == {'index.html', 'market.html', 'forecast.html', 'comparison.html', 'README.txt', 'manifest.json'}
    comparison = (output / 'comparison.html').read_text(encoding='utf8')
    assert all(pin in comparison for pin in receipt['comparison_source_pins'].values())
    assert not list(output.glob('*.db'))
    assert 'comparison.html' in (output / 'index.html').read_text(encoding='utf8')

    forecast = (output / 'forecast.html').read_text(encoding='utf8')
    assert 'id="plot-cohort"' in forecast and 'id="forecast-plot"' in forecast
    assert 'Exact plotted cases in chart order' in forecast
    assert "connect-src 'none'" in forecast
    assert 'forecast.html' in (output / 'index.html').read_text(encoding='utf8')

    guide = (output / 'README.txt').read_text(encoding='utf8')
    for term in ('browser_export', 'main report', 'prior report', '--preview', '--request', 'expected heads'):
        assert term in guide
    assert 'href="README.txt"' in (output / 'index.html').read_text(encoding='utf8')
