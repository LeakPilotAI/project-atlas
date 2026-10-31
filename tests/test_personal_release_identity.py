"""Release inventory syntax refuses before any native resource access."""
import pytest
from app.services.paper_financial_replay import digest

from scripts.observation_runtime.personal_release_identity import NativePersonalReleaseIdentity


@pytest.mark.parametrize('name',['../other','a/../other','a//other','C:/other','/absolute','a:stream',''])
def test_release_relative_names_cannot_escape_inventory(name):
    with pytest.raises(ValueError): NativePersonalReleaseIdentity._relative(name)


def test_release_defaults_or_wrong_artifact_refuse_before_native_access():
    with pytest.raises(ValueError): NativePersonalReleaseIdentity()
    files=[{'path':'source.py','bytes':1,'id':[1,2,3],'sha256':'a'*64}]
    receipt={'schema':'ATLAS_QD_D_RUNTIME_INSTALLATION_V1','stage':'D_RUNTIME_LAYOUT_VERIFIED',
             'source_commit':'a'*40,'release_path':'D:/foreign','files':files,
             'directories':[{'path':'.','id':[1,2,4]}]}
    with pytest.raises(ValueError): NativePersonalReleaseIdentity(receipt=receipt,artifact_digest=digest(files))


@pytest.mark.parametrize('value',[[True,2,3],[-1,2,3],[1,2],['1',2,3],None])
def test_native_identity_is_exactly_three_nonnegative_integers(value):
    with pytest.raises(ValueError): NativePersonalReleaseIdentity._native_id(value)
