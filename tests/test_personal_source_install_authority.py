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


def test_version_safe_source_install_binds_exact_selected_release_before_native_access(monkeypatch):
    from scripts.observation_runtime import personal_source_install_authority as module
    selected = 'a' * 64
    observed = []
    class SelectedClock:
        def require_operational(self, rid):
            assert rid == 'exact-native-runtime'
            observed.append('clock')
            return self
    class BoundReader:
        def read(self):
            raise AssertionError('NO_ACTIVATION_READ_DURING_CONSTRUCTION')

    def check_release(*, clock, runtime_id, release_digest):
        observed.append(('release', release_digest))
        assert type(clock) is SelectedClock and runtime_id == 'exact-native-runtime'
        return release_digest == selected

    monkeypatch.setattr(module, 'NativeVersionSafePaperOperatorClock', SelectedClock)
    monkeypatch.setattr(module, 'NativePersonalActivationReader', BoundReader)
    monkeypatch.setattr(module, 'require_version_safe_release_digest', check_release)
    monkeypatch.setattr(module, 'current_sid', lambda: 'SYNTHETIC_OPERATOR')
    monkeypatch.setattr(module, 'validate_policy', lambda p: p)
    def construct(release):
        return module.NativePersonalSourceInstallAuthority(
            reader=BoundReader(), policy={}, release_digest=release,
            accounts={'QUALITY_DIPS': 'c'*64, 'HYPERLIQUID': 'd'*64},
            clock=SelectedClock(), runtime_id='exact-native-runtime',
            enrollment_digest='e'*64, root_id=[1,2,3], initial_image=b'expected',
            clock_profile=module.VERSION_SAFE_NTP_PROFILE)
    with pytest.raises(ValueError, match='SOURCE_INSTALL_SELECTED_RELEASE_REQUIRED'):
        construct('b' * 64)
    assert observed == [('release', 'b'*64)]
    good = construct(selected)
    assert good.release == selected and not good.used
    assert observed == [('release', 'b'*64), ('release', selected), 'clock']
    assert good.clock_profile == module.VERSION_SAFE_NTP_PROFILE


def test_version_safe_source_install_release_proof_exception_refuses(monkeypatch):
    from scripts.observation_runtime import personal_source_install_authority as module
    class FakeClock:
        def require_operational(self, rid):
            pytest.fail('CLOCK_SHOULD_NOT_RUN_AFTER_RELEASE_PROOF_FAILURE')
    class FakeReader:
        pass
    monkeypatch.setattr(module, 'NativeVersionSafePaperOperatorClock', FakeClock)
    monkeypatch.setattr(module, 'NativePersonalActivationReader', FakeReader)
    def refuse(**kwargs):
        raise ValueError('VERSION_SAFE_CLOCK_ARTIFACT_OR_SELECTION_MISMATCH')
    monkeypatch.setattr(module, 'require_version_safe_release_digest', refuse)
    with pytest.raises(ValueError, match='VERSION_SAFE_CLOCK_ARTIFACT_OR_SELECTION_MISMATCH'):
        module.NativePersonalSourceInstallAuthority(
            reader=FakeReader(), policy={}, release_digest='a'*64,
            accounts={}, clock=FakeClock(), runtime_id='test', enrollment_digest='e'*64,
            root_id=[1,2,3], initial_image=b'image',
            clock_profile=module.VERSION_SAFE_NTP_PROFILE)
