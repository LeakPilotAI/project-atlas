import pytest
from scripts.observation_runtime.personal_source_install_authority import NativePersonalSourceInstallAuthority


def test_source_installer_refuses_unbound_activation_and_clock():
    with pytest.raises(ValueError, match='SOURCE_INSTALL_NATIVE_ACTIVATION_AND_CLOCK_REQUIRED'):
        NativePersonalSourceInstallAuthority(reader=None, policy={}, release_digest='0'*64,
            accounts={}, clock=None, runtime_id='test', enrollment_digest='0'*64,
            root_id=[1,2,3], initial_image=b'genesis')


def test_source_installer_has_no_default_activation_writer():
    from scripts.observation_runtime import personal_source_install_authority as module
    assert not hasattr(module, 'publish_activation')
    assert not hasattr(module, 'create_root')


def test_install_authority_rejects_image_substitution_even_with_matching_schema():
    from scripts.observation_runtime import personal_source_install_authority as module
    from unittest.mock import patch
    from contextlib import contextmanager
    import hashlib
    class Clock:
        def require_operational(self, runtime_id): return self
        def __call__(self): return 123
    class Reader:
        def read(self): return {'activation_id': 'native'}
    with patch.object(module, 'LocalWindowsClock', Clock), \
         patch.object(module, 'NativePersonalActivationReader', Reader), \
         patch.object(module, 'current_sid', lambda: 'operator'), \
         patch.object(module, 'validate_policy', lambda p: p), \
         patch.object(module, 'validate_activation_record', lambda *a, **k: a[0]):
        authority = module.NativePersonalSourceInstallAuthority(
            reader=Reader(), policy={}, release_digest='a'*64, accounts={'QUALITY_DIPS':'b'*64},
            clock=Clock(), runtime_id='runtime', enrollment_digest='c'*64,
            root_id=[1,2,3], initial_image=b'expected-image')
        request = {'schema':'PERSONAL_COORDINATION_INSTALL_V1', 'root':[1,2,3],
                   'enrollment':'c'*64, 'image_digest':hashlib.sha256(b'wrong-image').hexdigest()}
        import pytest
        with pytest.raises(ValueError, match='SOURCE_INSTALL_IMAGE_BINDING_REFUSED'):
            with authority.lease(request): pass
        request['image_digest'] = hashlib.sha256(b'expected-image').hexdigest()
        with authority.lease(request) as lease:
            assert lease.check(request)
        assert authority.used
        with pytest.raises(ValueError, match='SOURCE_INSTALL_OPERATOR_OR_ONCE_ONLY_REFUSED'):
            with authority.lease(request): pass
