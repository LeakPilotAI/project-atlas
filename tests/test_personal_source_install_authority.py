import pytest
from scripts.observation_runtime.personal_source_install_authority import NativePersonalSourceInstallAuthority


def test_source_installer_refuses_unbound_activation_and_clock():
    with pytest.raises(ValueError, match='SOURCE_INSTALL_NATIVE_ACTIVATION_AND_CLOCK_REQUIRED'):
        NativePersonalSourceInstallAuthority(reader=None, policy={}, release_digest='0'*64,
            accounts={}, clock=None, runtime_id='test', enrollment_digest='0'*64,
            root_id=[1,2,3])


def test_source_installer_has_no_default_activation_writer():
    from scripts.observation_runtime import personal_source_install_authority as module
    assert not hasattr(module, 'publish_activation')
    assert not hasattr(module, 'create_root')
