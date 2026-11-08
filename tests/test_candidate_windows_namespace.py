"""Windows namespace attacks remain ZIP bytes only; no reserved path is opened."""
import hashlib
import json
import zipfile

import pytest
from test_candidate_verifier import built
from test_offline_candidate_packaging import candidate


@pytest.mark.parametrize('fault',['case_alias','reserved','trailing_dot','trailing_space','control','file_directory'])
def test_rehashed_candidate_cannot_claim_windows_incompatible_namespace(tmp_path,monkeypatch,fault):
    archive,_=built(tmp_path,monkeypatch)
    with zipfile.ZipFile(archive) as source:contents={n:source.read(n) for n in source.namelist()}
    manifest=json.loads(contents['release-manifest.json']);original=manifest['files'][0]
    names={'case_alias':original['path'].upper(),'reserved':'backend/app/CON.py','trailing_dot':'backend/app/extra.py.',
        'trailing_space':'backend/app/extra.py ','control':'backend/app/extra?.py','file_directory':original['path']+'/extra.py'}
    name=names[fault];data=b'SYNTHETIC=1\n';contents[name]=data
    manifest['files'].append({'path':name,'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data),'git_status':'tracked','role':'runtime'})
    contents['release-manifest.json']=json.dumps(manifest).encode()
    altered=tmp_path/'windows-incompatible.zip'
    with zipfile.ZipFile(altered,'x') as target:
        for n,value in contents.items():target.writestr(n,value)
    with pytest.raises(ValueError):candidate.verify_candidate(altered,expected_sha256=hashlib.sha256(altered.read_bytes()).hexdigest())
