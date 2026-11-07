import pytest
from scripts.observation_runtime.personal_source_archive_installer import install_source_archive


def test_source_archive_installer_refuses_non_custody_root_before_native_access():
    with pytest.raises(ValueError, match='QD_SOURCE_EXPLICIT_CUSTODY_ROOT_REQUIRED'):
        install_source_archive(root='C:\\temp', enrollment={}, reader=None,
            policy={}, release_digest='', accounts={}, clock=None, runtime_id='')


def test_source_archive_installer_refuses_unenrolled_root_before_native_access():
    with pytest.raises(ValueError, match='EXPLICIT_QD_SOURCE_ARCHIVE_ENROLLMENT_REQUIRED'):
        install_source_archive(root='D:\\AtlasCustody\\QualityDips\\example', enrollment={},
            reader=None, policy={}, release_digest='', accounts={}, clock=None, runtime_id='')

@pytest.mark.parametrize('root', [
    'D:\\AtlasCustody\\QualityDips\\..\\PersonalPaper\\test',
    'D:\\AtlasCustody\\QualityDips\\test\\..\\another',
    'D:\\AtlasCustody\\QualityDips\\test:stream',
    'D:\\AtlasCustody\\QualityDips\\test\\',
    'D:\\AtlasCustody\\QualityDips\\test/child',
])
def test_source_archive_installer_refuses_root_alias_before_native_access(root):
    with pytest.raises(ValueError, match='QD_SOURCE_EXPLICIT_CUSTODY_ROOT_REQUIRED'):
        install_source_archive(root=root, enrollment={}, reader=None,
            policy={}, release_digest='', accounts={}, clock=None, runtime_id='')


def test_source_archive_installer_native_genesis_ack_uses_exact_raw_sha256(monkeypatch):
    import hashlib
    from contextlib import contextmanager
    from types import SimpleNamespace
    from scripts.observation_runtime import personal_source_archive_installer as module
    from scripts.observation_runtime.personal_research_archive import initial_image
    from app.services.paper_financial_replay import digest
    enrollment = {"schema":"PERSONAL_QD_SOURCE_ARCHIVE_V1", "account_id":"paper-qd",
                  "epoch":"test", "source_id":"native-qd", "release_digest":"a"*64,
                  "source_commit":"b"*40, "root_id":[1,2,3]}
    image = initial_image(enrollment)
    class Output:
        root_handle = 42
        def __enter__(self): return self
        def __exit__(self, *args): pass
    monkeypatch.setattr(module, 'native_primitives', lambda: SimpleNamespace(
        w=SimpleNamespace(WindowsOutput=lambda root: Output()),
        native=SimpleNamespace(file_identity=lambda handle: [1,2,3])))
    class Images:
        def __init__(self, **kwargs):
            assert kwargs['enrollment_digest'] == digest(enrollment)
            self.content = None
        def initialize(self, value, *, authorization): self.content = value
        @contextmanager
        def transaction(self, *, readonly):
            assert readonly
            yield SimpleNamespace(read=lambda: self.content)
        def close(self): pass
    monkeypatch.setattr(module, 'NativePersonalCoordinationImages', Images)
    monkeypatch.setattr(module, 'NativePersonalSourceInstallAuthority', lambda **kwargs: object())
    result = module.install_source_archive(root='D:\\AtlasCustody\\QualityDips\\fresh',
        enrollment=enrollment, reader=None, policy={}, release_digest='a'*64,
        accounts={}, clock=None, runtime_id='test')
    assert result['initial_image_digest'] == hashlib.sha256(image).hexdigest()
    assert result['source_publication_accepted'] is False
    assert result['financial_inception_authorized'] is False
