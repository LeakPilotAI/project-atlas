"""Release inventory syntax refuses before any native resource access."""
import pytest
from app.services.paper_financial_replay import digest

from scripts.observation_runtime.personal_release_identity import NativePersonalReleaseIdentity


@pytest.mark.parametrize('startup,live',[(0,True),(0,False),(1,False)])
def test_release_requires_bytecode_protection_from_startup_before_native_access(monkeypatch,startup,live):
    from types import SimpleNamespace
    import scripts.observation_runtime.personal_release_identity as release
    files=[{'path':'source.py','bytes':1,'id':[1,2,3],'sha256':'a'*64}]
    receipt={'schema':'ATLAS_QD_D_RUNTIME_INSTALLATION_V1','stage':'D_RUNTIME_LAYOUT_VERIFIED',
             'source_commit':'a'*40,'release_path':str(release.Path('D:/AtlasRuntime/releases')/('a'*40)),
             'files':files,'directories':[{'path':'.','id':[1,2,4]}]}
    monkeypatch.setattr(release,'native_primitives',lambda:pytest.fail('native access before startup admission'))
    with monkeypatch.context() as patch:
        patch.setattr(release.sys,'flags',SimpleNamespace(dont_write_bytecode=startup))
        patch.setattr(release.sys,'dont_write_bytecode',live)
        with pytest.raises(ValueError,match='BYTECODE_WRITES_NOT_DISABLED_AT_STARTUP'):
            NativePersonalReleaseIdentity(receipt=receipt,artifact_digest=digest(files))


def test_release_rechecks_bytecode_setting_before_every_native_verify(monkeypatch):
    import scripts.observation_runtime.personal_release_identity as release
    instance=object.__new__(NativePersonalReleaseIdentity)
    with monkeypatch.context() as patch:
        patch.setattr(release.sys,'dont_write_bytecode',False)
        with pytest.raises(ValueError,match='BYTECODE_WRITES_NOT_DISABLED_AT_STARTUP'):
            instance.verify(release_digest='a'*64)


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
