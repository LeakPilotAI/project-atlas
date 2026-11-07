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
