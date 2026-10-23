"""Portable market viewer builds from clean source-candidate extraction."""
import json
import subprocess
import zipfile
from pathlib import Path

from test_offline_candidate_packaging import candidate, fixture_root


def test_actual_market_viewer_dependencies_survive_source_packaging(tmp_path,monkeypatch):
    source,_=fixture_root(tmp_path,monkeypatch)
    repo=Path(__file__).resolve().parents[1]
    files=['frontend/offline/market-replay/view.cjs','frontend/offline/market-replay/mount.cjs',
           'frontend/offline/market-replay/build.mjs','frontend/offline/market-replay/artifact-io.mjs',
           'frontend/offline/forecast-accountability/view.css']
    for name in files:
        target=source/name
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes((repo/name).read_bytes())
    original=candidate.git
    monkeypatch.setattr(candidate,'git',lambda *args:original(*args)+files if '--others' in args else original(*args))
    output=tmp_path/'candidate'
    candidate.build(output)
    extracted=tmp_path/'clean'
    with zipfile.ZipFile(output/'atlas-source.zip') as archive:
        archive.extractall(extracted)
    html=extracted/'viewer.html'
    result=subprocess.run(['C:/Program Files/nodejs/node.exe',str(extracted/'frontend/offline/market-replay/build.mjs'),str(html)],cwd=extracted,capture_output=True,text=True,timeout=20,check=False)
    assert result.returncode==0,result.stdout+result.stderr
    receipt=json.loads(result.stdout)
    assert receipt['production_approved'] is False
    assert html.is_file()
    content=html.read_text(encoding='utf-8')
    assert 'Market evidence, offline.' in content
    assert "connect-src 'none'" in content
    assert 'market-file' in content and 'Production NO-GO' in content
