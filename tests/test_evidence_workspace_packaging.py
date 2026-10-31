"""Offline workspace packaging includes both viewers and shared publication helper."""
import json
import subprocess
import zipfile
from pathlib import Path

from test_offline_candidate_packaging import candidate, fixture_root


def test_clean_candidate_builds_and_verifies_the_complete_static_workspace(tmp_path,monkeypatch):
    source,_=fixture_root(tmp_path,monkeypatch)
    repo=Path(__file__).resolve().parents[1]
    files=['frontend/offline/workspace/build.mjs','frontend/offline/market-replay/build.mjs',
           'frontend/offline/market-replay/artifact-io.mjs','frontend/offline/market-replay/view.cjs','frontend/offline/market-replay/mount.cjs',
           'frontend/offline/forecast-accountability/build.cjs','frontend/offline/forecast-accountability/view.cjs','frontend/offline/forecast-accountability/view.css']
    for name in files:
        target=source/name
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes((repo/name).read_bytes())
    previous=candidate.git
    monkeypatch.setattr(candidate,'git',lambda *args:previous(*args)+files if '--others' in args else previous(*args))
    candidate.build(tmp_path/'candidate')
    clean=tmp_path/'clean'
    with zipfile.ZipFile(tmp_path/'candidate/atlas-source.zip') as archive:
        archive.extractall(clean)
    output=clean/'workspace'
    script=clean/'frontend/offline/workspace/build.mjs'
    result=subprocess.run(['C:/Program Files/nodejs/node.exe',str(script),str(output)],cwd=clean,capture_output=True,text=True,timeout=20,check=False)
    assert result.returncode==0,result.stdout+result.stderr
    receipt=json.loads(result.stdout)
    assert receipt['production_approved'] is False
    verify=subprocess.run(['C:/Program Files/nodejs/node.exe',str(script),'--verify',str(output),'--expected-manifest-sha256',receipt['manifest_sha256']],cwd=clean,capture_output=True,text=True,timeout=20,check=False)
    assert verify.returncode==0,verify.stdout+verify.stderr
    assert json.loads(verify.stdout)['supplied_bytes_consistent'] is True
    assert json.loads(verify.stdout)['native_browser_acceptance']=='NOT_ESTABLISHED'
    assert {p.name for p in output.iterdir()}=={'index.html','market.html','forecast.html','manifest.json','README.txt'}
