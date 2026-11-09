"""Offline new-version installer: read-only exact admissions, all native effects blocked."""
import hashlib
import json
from pathlib import Path

import pytest

from scripts import install_version_safe_candidate as next_install
from scripts import install_verified_release as old_install

ROOT = Path(__file__).resolve().parents[1]
FUTURE = '2d4879878bf58bea5a3ed0a986b809791f638fec'


def test_new_installer_exact_review_and_old_install_source_unchanged():
    p = next_install.read_exact_review()
    assert p['candidate']['source_commit'] == FUTURE
    assert p['candidate']['archive_sha256'] == next_install.ARCHIVE
    assert p['candidate']['inventory_sha256'] == next_install.INVENTORY
    assert p['dependencies']['full_source_inventory_sha256'] == next_install.DEPENDENCY
    assert p['native_plan']['files'] == 10574
    assert p['status'] == 'DESIGN_NOT_PERMISSION'
    assert hashlib.sha256((ROOT/'scripts/install_verified_release.py').read_bytes()).hexdigest() == (
        'bcaea829d5466a293486624a95f689cf02d60e4893ef92a92ce00202c4a78571'
    )
    assert old_install.INDEPENDENT_NTP_CODE_INSTALL_V8_SOURCE_COMMIT != FUTURE
    assert old_install.INDEPENDENT_NTP_CODE_INSTALL_SOURCE_COMMIT != FUTURE


def test_actual_guarded_native_plan_never_installs_or_selects():
    # A verified completed one-time installation MUST refuse re-preparation.
    with pytest.raises(ValueError, match='INSTALLATION_ALREADY_EXISTS_PRESERVE_NO_RETRY'):
        next_install.prepare_reviewed_code()
    assert (Path('D:/AtlasRuntime/releases')/FUTURE).is_dir()
    receipt=ROOT/'logs/diagnostics'/('qd-unselected-release-'+FUTURE+'.json')
    assert receipt.is_file()
    assert hashlib.sha256(receipt.read_bytes()).hexdigest()==next_install.INSTALLED_RECEIPT_SHA
    assert not Path('D:/AtlasRuntime/selection/r0012.json').exists()


@pytest.mark.parametrize('kind,pattern',[
    ('unapproved','VERSION_SAFE_INSTALL_EXPLICIT_EXECUTION_REQUIRED'),
    ('unapproved_true','VERSION_SAFE_INSTALL_SEPARATE_OPERATOR_APPROVAL_ABSENT'),
    ('private_direct','VERSION_SAFE_INSTALL_SEPARATE_OPERATOR_APPROVAL_ABSENT'),
    ('cli','VERSION_SAFE_INSTALL_NO_APPROVED_EXECUTION_ENTRYPOINT'),
])
def test_native_effects_are_not_reachable_from_any_public_or_private_entrypoint(monkeypatch,kind,pattern,tmp_path):
    monkeypatch.setattr(next_install,'APPROVAL',tmp_path/'missing.json')
    monkeypatch.setattr(next_install, '_copy_prepared_code',
        lambda **kwargs: pytest.fail('NATIVE_COPY_MUST_NOT_RUN'))
    monkeypatch.setattr(next_install, 'write_new_json',
        lambda *args, **kwargs: pytest.fail('NATIVE_JOURNAL_MUST_NOT_WRITE'))
    monkeypatch.setattr(next_install, 'installed_readback',
        lambda *args, **kwargs: pytest.fail('INSTALL_CHILD_MUST_NOT_RUN'))
    monkeypatch.setattr(next_install, 'prepare_install_inputs',
        lambda *args, **kwargs: pytest.fail('NOT_AUTHORIZED_FOR_INSTALL'))
    if kind=='unapproved':
        with pytest.raises(ValueError,match=pattern):
            next_install.install_unselected()
    elif kind=='unapproved_true':
        with pytest.raises(ValueError,match=pattern):
            next_install.install_unselected(approved_execution=True)
    elif kind=='private_direct':
        with pytest.raises(ValueError,match=pattern):
            next_install._native_copy_only_after_approval(prepared_review={}, clock=object(),
                 preflight={'elapsed_seconds':180,'samples':37,'bound_ms':100})
    else:
        with pytest.raises(SystemExit,match=pattern):next_install.main([])


def test_even_forced_local_unreviewed_approval_is_refused(monkeypatch,tmp_path):
    fake = tmp_path / 'approval.json'
    fake.write_text(json.dumps({'approved':True,'scope':'CODE_ONLY'}),encoding='utf-8')
    monkeypatch.setattr(next_install, 'APPROVAL', fake)
    monkeypatch.setattr(next_install, 'APPROVAL_PIN', None)
    with pytest.raises(ValueError,match='VERSION_SAFE_INSTALL_APPROVAL_NOT_YET_REVIEWED'):
        next_install.install_unselected(approved_execution=True)


@pytest.mark.parametrize('field', ['archive_sha256','inventory_sha256','source_commit'])
def test_changed_review_identity_refused_before_plan(monkeypatch,field):
    original = next_install.strict
    def corrupt(raw):
        parsed = original(raw)
        parsed['candidate'][field] = 'f'* (40 if field=='source_commit' else 64)
        return parsed
    monkeypatch.setattr(next_install,'strict',corrupt)
    monkeypatch.setattr(next_install,'prepare_install_inputs',
        lambda **kwargs:pytest.fail('FORGED_REVIEW_CANNOT_REACH_PLAN'))
    with pytest.raises(ValueError,match='VERSION_SAFE_INSTALL_REVIEW_IDENTITY_MISMATCH'):
        next_install.prepare_reviewed_code()


def test_wrong_review_hash_refused_before_native(monkeypatch):
    monkeypatch.setattr(next_install,'REVIEW_SHA','0'*64)
    with pytest.raises(ValueError,match='VERSION_SAFE_INSTALL_PIN_CHANGED'):
        next_install.read_exact_review()


def test_no_synthetic_ntp_clock_can_pretend_to_be_real():
    with pytest.raises(ValueError,match='VERSION_SAFE_INSTALL_REAL_TWO_PEER_CLOCK_REQUIRED'):
        next_install._qualify_native_clock_180s(object(),'SYNTHETIC')


def test_no_earlier_sel_or_financial_grant():
    src=(ROOT/'scripts/install_version_safe_candidate.py').read_text(encoding='utf-8')
    assert 'require_separate_operator_approval()' in src
    assert 'selection_allowed' in src and 'financial_authority' in src
    assert 'provider_connections' in src and 'operational_acceptance' in src
    assert 'os.path.lexists' in src and 'FAILED_PRESERVE_PARTIAL_NO_RETRY_OR_SELECTION' in src
    assert 'def _qualify_native_clock_180s(' in src
    assert 'def _native_copy_only_after_approval(' in src
    assert not Path('D:/AtlasRuntime/selection/r0012.json').exists()


def test_180_second_single_clock_qualification_uses_37_samples_without_network(monkeypatch):
    from scripts.observation_runtime import atlas_independent_ntp_clock as ntp
    class FakeNtp:
        def __init__(self):
            self.count=0
            self.evidence={'source':ntp.SOURCE,
                           'domain':'TWO_PUBLIC_UNAUTHENTICATED_NTP_PEERS',
                           'financial_authority':False,'bound_ms':140}
        def require_operational(self,runtime_id):
            assert runtime_id=='SYNTHETIC_NONFINANCIAL'
            self.count+=1
    monkeypatch.setattr(ntp,'IndependentNtpClock',FakeNtp)
    clock=FakeNtp(); t=[0.0]
    monkeypatch.setattr(next_install.time,'perf_counter',lambda:t[0])
    monkeypatch.setattr(next_install.time,'sleep',lambda delta:t.__setitem__(0,t[0]+delta))
    proof=next_install._qualify_native_clock_180s(clock,'SYNTHETIC_NONFINANCIAL')
    assert proof=={'elapsed_seconds':180.0,'samples':37,'bound_ms':140}
    assert clock.count==37


def test_180_second_clock_source_change_refuses_without_native_writes(monkeypatch):
    from scripts.observation_runtime import atlas_independent_ntp_clock as ntp
    class FakeNtp:
        def __init__(self):
            self.count=0
            self.evidence={'source':ntp.SOURCE,
                           'domain':'TWO_PUBLIC_UNAUTHENTICATED_NTP_PEERS',
                           'financial_authority':False,'bound_ms':120}
        def require_operational(self,runtime_id):
            self.count+=1
            if self.count==3:self.evidence['financial_authority']=True
    monkeypatch.setattr(ntp,'IndependentNtpClock',FakeNtp)
    clock=FakeNtp();t=[0.0]
    monkeypatch.setattr(next_install.time,'perf_counter',lambda:t[0])
    monkeypatch.setattr(next_install.time,'sleep',lambda delta:t.__setitem__(0,t[0]+delta))
    with pytest.raises(ValueError,match='VERSION_SAFE_INSTALL_NTP_CONTINUITY_REFUSED'):
        next_install._qualify_native_clock_180s(clock,'SYNTHETIC_NONFINANCIAL')
    assert clock.count==3 and t[0]==10.0
