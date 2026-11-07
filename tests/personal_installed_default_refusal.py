"""Installed synthetic candidate only: missing operational dependencies refuse."""
import json
import sys
from pathlib import Path

from app.services.personal_paper_runtime import compose_personal_qd
from personal_fixture_sources import fixture_source_root

from scripts.observation_runtime.personal_release_identity import (
    NativePersonalReleaseIdentity,
)


def main():
    workspace=Path(__file__).resolve().parents[1];source=fixture_source_root(workspace)
    if source==workspace:raise ValueError('EXPLICIT_INSTALLED_FIXTURE_ONLY')
    failures={}
    try:compose_personal_qd()
    except ValueError as error:failures['runtime']=str(error)
    else:raise AssertionError('Missing operational dependencies admitted')
    try:NativePersonalReleaseIdentity(receipt={'schema':'ATLAS_DISPOSABLE_NATIVE_INSTALLATION_V1'},artifact_digest='0'*64)
    except ValueError as error:failures['disposable_receipt']=str(error)
    else:raise AssertionError('Disposable receipt accepted operationally')
    print(json.dumps({'installed_candidate':str(source),'executable':sys.executable,'base_prefix':sys.base_prefix,
        'refusals':failures,'financial_actions':0,'provider_actions':0,'active_release_modified':False}))


if __name__=='__main__':main()
