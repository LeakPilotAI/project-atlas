"""Version-safe profile source integration; all financial/native writes intercepted."""
import json
from contextlib import nullcontext
from pathlib import Path

import pytest

from app.services.paper_financial_replay import digest
from app.services.personal_paper_runtime import validate_policy
from scripts.observation_runtime import personal_version_safe_release_clock as v
from scripts.observation_runtime import personal_activation_commission as commission
from scripts.observation_runtime import personal_activation_publisher as publisher
from scripts.observation_runtime import personal_source_install_authority as source
from scripts.observation_runtime import personal_installation_technical as technical
from scripts.observation_runtime import personal_local_authority as authority
from scripts.observation_runtime import personal_paper_activation as assembly
from scripts.observation_runtime.personal_paper_activation import NativePersonalActivationReader
from scripts.observation_runtime.atlas_independent_ntp_clock import SOURCE
from test_personal_v7_activation_publisher_and_commission import publisher_inputs, FakeNativeV7
from test_personal_v7_installed_composition_clock import synthetic_call

FUTURE_ARTIFACT = 'd' * 64


def test_current_workspace_clock_cannot_claim_installed_financial_release(monkeypatch):
    monkeypatch.setattr(v.NativeVersionSafePaperOperatorClock, 'require_operational',
                        lambda self, runtime: None)
    clock = object.__new__(v.NativeVersionSafePaperOperatorClock)
    with pytest.raises(ValueError, match='VERSION_SAFE_CLOCK_INSTALLED_SOURCE_REQUIRED'):
        v.require_version_safe_release_digest(clock=clock,
                                              runtime_id='SYNTHETIC',
                                              release_digest=FUTURE_ARTIFACT)
    with pytest.raises(ValueError, match='VERSION_SAFE_CLOCK_EXACT_RELEASE_DIGEST_REQUIRED'):
        v.require_version_safe_release_digest(clock=object(),
                                              runtime_id='SYNTHETIC',
                                              release_digest=FUTURE_ARTIFACT)


def test_exact_native_digest_check_accepts_only_current_selected_artifact(monkeypatch):
    from scripts import release_selection_store
    release = 'a' * 40
    monkeypatch.setattr(v, '__file__', str(Path('D:/AtlasRuntime/releases') / release / v.CLOCK_RELATIVE))
    class FakeStore:
        def __init__(self, **kwargs):
            assert kwargs['root'] == r'D:\AtlasRuntime\selection'
        def locked(self): return nullcontext()
        def records(self): return ['synthetic, not native']
        def close(self): pass
    monkeypatch.setattr(release_selection_store, 'NativeSelectionStore', FakeStore)
    monkeypatch.setattr(v, 'admit_version_safe_clock_source',
                        lambda *, source_file, records: ('EXPECTED_HEAD', {'artifact_digest': FUTURE_ARTIFACT}))
    monkeypatch.setattr(v.NativeVersionSafePaperOperatorClock, 'require_operational',
                        lambda self, runtime: None)
    clock = object.__new__(v.NativeVersionSafePaperOperatorClock)
    clock._selected_head = 'EXPECTED_HEAD'
    assert v.require_version_safe_release_digest(clock=clock,
                 runtime_id='SYNTHETIC', release_digest=FUTURE_ARTIFACT) is True
    with pytest.raises(ValueError, match='VERSION_SAFE_CLOCK_ARTIFACT_OR_SELECTION_MISMATCH'):
        v.require_version_safe_release_digest(clock=clock, runtime_id='SYNTHETIC',
                                              release_digest='e' * 64)
    clock._selected_head = 'FOREIGN_HEAD'
    with pytest.raises(ValueError, match='VERSION_SAFE_CLOCK_ARTIFACT_OR_SELECTION_MISMATCH'):
        v.require_version_safe_release_digest(clock=clock, runtime_id='SYNTHETIC',
                                              release_digest=FUTURE_ARTIFACT)


def test_new_publisher_profile_checks_selected_digest_before_intercepted_native(monkeypatch):
    kw = publisher_inputs(monkeypatch)
    kw.update(release_digest=FUTURE_ARTIFACT, clock_profile=v.PROFILE)
    monkeypatch.setattr(v, 'NativeVersionSafePaperOperatorClock', FakeNativeV7)
    seen = []
    def check(**args):
        seen.append((args['clock'], args['runtime_id'], args['release_digest']))
        if args['release_digest'] != FUTURE_ARTIFACT:
            raise ValueError('WRONG_RELEASE')
        return True
    monkeypatch.setattr(v, 'require_version_safe_release_digest', check)
    with pytest.raises(RuntimeError, match='WOULD_ENTER_NATIVE_CUSTODY'):
        publisher.publish_personal_activation(**kw)
    assert seen == [(kw['clock'], kw['runtime_id'], FUTURE_ARTIFACT)]
    assert kw['clock'].checked == 1
    for bad in ('e' * 64, '0' * 64):
        with pytest.raises(publisher.PersonalActivationPublicationRefused,
                           match='Selected version-safe native release binding required'):
            publisher.publish_personal_activation(**{**kw, 'release_digest': bad})
    with pytest.raises(publisher.PersonalActivationPublicationRefused,
                       match='Exact version-safe native clock required'):
        publisher.publish_personal_activation(**{**kw, 'clock': object()})


def test_version_safe_qd_composition_preserves_existing_custody_boundary(monkeypatch):
    monkeypatch.setattr(v.NativeVersionSafePaperOperatorClock, 'require_operational',
                        lambda self, runtime: None)
    clock = object.__new__(v.NativeVersionSafePaperOperatorClock)
    with pytest.raises(ValueError, match='PERSONAL_INSTALLED_CURRENT_CUSTODY_BINDING'):
        synthetic_call(monkeypatch, clock, v.PROFILE)
    with pytest.raises(ValueError, match='PERSONAL_INSTALLED_NATIVE_DEPENDENCIES_REQUIRED'):
        synthetic_call(monkeypatch, clock, 'V8_INDEPENDENT_NTP_OPERATOR_CLOCK_V1')


def test_new_source_install_port_still_needs_exact_native_reader(monkeypatch):
    monkeypatch.setattr(v.NativeVersionSafePaperOperatorClock, 'require_operational',
                        lambda self, runtime: None)
    clock = object.__new__(v.NativeVersionSafePaperOperatorClock)
    monkeypatch.setattr(source, 'validate_policy', lambda policy: policy)
    monkeypatch.setattr(source, 'current_sid', lambda: 'SYNTHETIC')
    kw = dict(reader=object.__new__(NativePersonalActivationReader),policy={},
        release_digest=FUTURE_ARTIFACT,accounts={'QUALITY_DIPS':'a'*64},
        clock=clock,runtime_id='SYNTHETIC',enrollment_digest='b'*64,
        root_id=[1,2,3],initial_image=b'no-native-writes')
    obj = source.NativePersonalSourceInstallAuthority(**kw, clock_profile=v.PROFILE)
    assert obj.clock is clock and obj.used is False
    with pytest.raises(ValueError, match='SOURCE_INSTALL_NATIVE_ACTIVATION_AND_CLOCK_REQUIRED'):
        source.NativePersonalSourceInstallAuthority(**kw)


def test_commission_new_profile_rejects_bad_source_before_inputs():
    kw = dict(root=r'D:\AtlasCustody\PersonalPaper\synthetic',
              record_path='nonexistent', policy_path='nonexistent',
              accounts_path='nonexistent', release_digest=FUTURE_ARTIFACT,
              expected_clock_source='WRONG', runtime_id='SYNTHETIC',
              qd_enrollment_path='nonexistent', perp_enrollment_path='nonexistent',
              clock_profile=v.PROFILE)
    with pytest.raises(ValueError, match='EXACT_VERSION_SAFE_NATIVE_NTP_SOURCE_REQUIRED'):
        commission.commission(**kw)
    with pytest.raises(FileNotFoundError):
        commission.commission(**{**kw, 'expected_clock_source': SOURCE})


def test_commission_never_publishes_without_selected_digest(monkeypatch, tmp_path):
    from app.services import quality_dips_autonomous_enrollment as qe
    from app.services import perp_operational_contract as he
    qd={'account_id':'SYNTH_QD','release_digest':FUTURE_ARTIFACT}
    hl={'account_id':'SYNTH_HL','release_digest':FUTURE_ARTIFACT}
    accounts={'QUALITY_DIPS':digest(qd),'HYPERLIQUID':digest(hl)}
    policy=json.loads((Path(__file__).resolve().parents[1] /
                       'docs/ATLAS_PERSONAL_PAPER_RELEASE_POLICY.json').read_text())
    record={'accounts':accounts,'release_digest':FUTURE_ARTIFACT,
            'policy_digest':digest(validate_policy(policy)),
            'origin':'LOCAL_OPERATOR','schema':'ATLAS_PERSONAL_ACTIVATION_V1',
            'actions':['READ_ONLY']}
    paths={}
    for name, value in [('record',record),('policy',policy),('accounts',accounts),('qd',qd),('hl',hl)]:
        path=tmp_path/name
        path.write_text(json.dumps(value),encoding='utf-8')
        paths[name]=str(path)
    monkeypatch.setattr(qe,'validate_enrollment',lambda x:x)
    monkeypatch.setattr(he,'validate_enrollment',lambda x:x)
    monkeypatch.setattr(commission,'verify_enrollment_native_roots',lambda x:None)
    monkeypatch.setattr(commission,'NativeVersionSafePaperOperatorClock',FakeNativeV7)
    observed=[]
    monkeypatch.setattr(commission,'require_version_safe_release_digest',
                        lambda **kw: observed.append(kw) or (_ for _ in ()).throw(ValueError('SELECTED_ARTIFACT_REFUSED')))
    monkeypatch.setattr(commission,'publish_personal_activation',
                        lambda **kw: pytest.fail('must not reach native publisher'))
    with pytest.raises(ValueError, match='SELECTED_ARTIFACT_REFUSED'):
        commission.commission(root=r'D:\AtlasCustody\PersonalPaper\synthetic',
            record_path=paths['record'],policy_path=paths['policy'],
            accounts_path=paths['accounts'],release_digest=FUTURE_ARTIFACT,
            expected_clock_source=SOURCE,runtime_id='SYNTHETIC',
            qd_enrollment_path=paths['qd'],perp_enrollment_path=paths['hl'],
            clock_profile=v.PROFILE)
    assert len(observed)==1 and observed[0]['release_digest']==FUTURE_ARTIFACT
    assert FakeNativeV7.created[-1].revoked


def test_all_six_sources_keep_legacy_types_and_new_exact_profile():
    modules=[authority,source,technical,assembly,publisher,commission]
    for module in modules:
        text=Path(module.__file__).read_text(encoding='utf-8-sig')
        assert 'NativeVersionSafePaperOperatorClock' in text
        assert 'VERSION_SAFE_NTP_PROFILE' in text
        assert 'NativeV8PaperOperatorClock' in text
        assert 'NativeV7PaperOperatorClock' in text
        assert 'LocalWindowsClock' in text
    assert commission.main.__defaults__ is not None or 'WINDOWS_TIME_OPERATOR_CLOCK_V4' in \
        Path(commission.__file__).read_text(encoding='utf-8-sig')
