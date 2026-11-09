"""New unselected support bootstrap, exact native/clock/read-only refusal tests."""
import copy
import hashlib
import json
import subprocess
from pathlib import Path

import pytest

from scripts import atlas_version_safe_support_bootstrap as b

SID='S-1-5-21-11-22-33-1001'  # synthetic, never the user's SID


def proposal():
    m=json.loads(b.MANIFEST.read_bytes())
    return dict(schema='ATLAS_VERSION_SAFE_SUPPORT_CODE_ONLY_APPROVAL_V1',
        decision='APPROVE_ONE_NATIVE_SUPPORT_COPY_ONLY',scope=b.CONFIRM,
        operator_sid=SID,target_release=b.NEW,
        application_receipt_sha256=b.APP_SHA,artifact_digest=b.ARTIFACT,
        manifest_sha256=b.MANIFEST_SHA,archive_sha256=b.ARCHIVE_SHA,
        support_manifest_sha256=b.SUPPORT_SHA,selected_v7_head=b.HEAD,
        destination=m['destination'],control=m['control'],one_shot=True,
        selection_allowed=False,provider_access=False,
        financial_authority=False,paper_accounts=False,orders=False)


def test_existing_verified_install_and_support_are_not_selected():
    assert b.APP.is_dir()
    assert b.APPROVAL_PIN is None and not b.APPROVAL_FILE.exists()
    assert b.MANIFEST.is_file() and b.ARCHIVE.is_file()
    assert b.sha(b.MANIFEST.read_bytes())==b.MANIFEST_SHA
    assert b.sha(b.ARCHIVE.read_bytes())==b.ARCHIVE_SHA
    from scripts.release_selection import digest
    r=json.loads(Path('D:/AtlasRuntime/selection/r0011.json').read_bytes())['record']
    assert digest(r)==b.HEAD
    assert r['selected']['release']==b.V7
    assert not Path('D:/AtlasRuntime/selection/r0012.json').exists()


def test_genuine_installed_python_read_only_bootstrap_success():
    command=[str(b.APP/'python/python.exe'),'-I','-B','-S',str(Path(b.__file__)), '--inspect']
    output=subprocess.run(command,capture_output=True,text=True,timeout=90)
    assert output.returncode==0,output.stderr
    status=json.loads(output.stdout)
    assert status['status']=='VERSION_SAFE_NTP_SUPPORT_NATIVE_BOOTSTRAP_REVIEW_PASS'
    assert status['support_files']==10
    assert status['native_application_dependencies']==24
    assert status['native_support_installed'] is False
    assert status['financial_authority'] is False
    assert status['providers'] is False
    assert status['selected'] is False
    assert status['operator_approval_pinned'] is False
    assert not output.stderr


def test_running_bootstrap_on_workspace_python_refuses():
    with pytest.raises(ValueError,match='SUPPORT_VSAFE_EXACT_INSTALLED_ISOLATED_PYTHON_REQUIRED'):
        b.require_installed_interpreter()


def test_real_install_cli_refuses_without_approval_before_any_clock(monkeypatch):
    monkeypatch.setattr(b,'inspect',lambda:pytest.fail('INSPECT_NOT_BEFORE_APPROVAL'))
    with pytest.raises(ValueError,match='SUPPORT_VSAFE_SEPARATE_INSTALL_APPROVAL_ABSENT'):
        b.main(['--execute-reviewed-code-only','--confirm-scope',b.CONFIRM])
    with pytest.raises(ValueError,match='SUPPORT_VSAFE_EXACT_NONFINANCIAL_SCOPE_REQUIRED'):
        b.main(['--execute-reviewed-code-only'])
    with pytest.raises(ValueError,match='SUPPORT_VSAFE_INSPECT_NO_EXECUTION_FLAG'):
        b.main(['--inspect','--confirm-scope',b.CONFIRM])


def test_fake_unpinned_approval_cannot_grant_install(monkeypatch,tmp_path):
    f=tmp_path/'approval.json';f.write_text(json.dumps(proposal()))
    monkeypatch.setattr(b,'APPROVAL_FILE',f)
    with pytest.raises(ValueError,match='SUPPORT_VSAFE_APPROVAL_NOT_INDEPENDENTLY_PINNED'):
        b.require_install_approval()


def test_exact_pure_nonfinancial_operator_decision():
    p=proposal()
    m=json.loads(b.MANIFEST.read_bytes())
    assert b.validate_operator_decision(p,sid=SID,manifest=m) is p
    assert p['one_shot'] is True
    assert not any(p[k] for k in ('selection_allowed','provider_access',
                                'financial_authority','paper_accounts','orders'))


@pytest.mark.parametrize('field,bad',(
    ('schema','FORGED'),('decision','APPROVE_ANYTHING'),('scope','FULL_PAPER'),
    ('operator_sid','S-1-5-18'),('target_release','a'*40),
    ('application_receipt_sha256','f'*64),('artifact_digest','f'*64),
    ('manifest_sha256','f'*64),('archive_sha256','f'*64),
    ('support_manifest_sha256','f'*64),('selected_v7_head','f'*64),
    ('destination','D:/foreign'),('control','D:/foreign'),
    ('one_shot',1),('selection_allowed',True),('provider_access',True),
    ('financial_authority',True),('paper_accounts',True),('orders',True),
))
def test_all_broadened_consent_fields_refused(field,bad):
    p=proposal();p[field]=bad
    with pytest.raises(ValueError,match='SUPPORT_VSAFE_EXACT_OPERATOR_DECISION_REQUIRED'):
        b.validate_operator_decision(p,sid=SID,manifest=json.loads(b.MANIFEST.read_bytes()))


def test_foreign_sid_and_extra_fields_refused():
    p=proposal();m=json.loads(b.MANIFEST.read_bytes())
    with pytest.raises(ValueError,match='SUPPORT_VSAFE_EXACT_OPERATOR_DECISION_REQUIRED'):
        b.validate_operator_decision(p,sid='S-1-5-21-4-5-6-1002',manifest=m)
    p['extra']='yes'
    with pytest.raises(ValueError,match='SUPPORT_VSAFE_EXACT_OPERATOR_DECISION_REQUIRED'):
        b.validate_operator_decision(p,sid=SID,manifest=m)


def test_pinned_synthetic_private_approval_sid_and_duplicate_key(monkeypatch,tmp_path):
    from scripts.volume_inspector import windows_output
    p=proposal();f=tmp_path/'approval.json'
    raw=(json.dumps(p,sort_keys=True)+'\n').encode()
    f.write_bytes(raw)
    monkeypatch.setattr(b,'APPROVAL_FILE',f)
    monkeypatch.setattr(b,'APPROVAL_PIN',hashlib.sha256(raw).hexdigest())
    monkeypatch.setattr(windows_output,'current_sid',lambda:SID)
    assert b.require_install_approval()==p
    monkeypatch.setattr(windows_output,'current_sid',lambda:'S-1-5-18')
    with pytest.raises(ValueError,match='SUPPORT_VSAFE_EXACT_OPERATOR_DECISION_REQUIRED'):
        b.require_install_approval()
    monkeypatch.setattr(windows_output,'current_sid',lambda:SID)
    bad=(json.dumps(p)[:-1]+',"orders":false}').encode()
    f.write_bytes(bad)
    monkeypatch.setattr(b,'APPROVAL_PIN',hashlib.sha256(bad).hexdigest())
    with pytest.raises(ValueError,match='SUPPORT_VSAFE_DUPLICATE_APPROVAL_KEY'):
        b.require_install_approval()


def test_two_peer_180s_37_samples_synthetically_without_network(monkeypatch):
    from scripts.observation_runtime import atlas_independent_ntp_clock as ntp
    class FakeClock:
        def __init__(self):
            self.count=0
            self.evidence={'source':ntp.SOURCE,'domain':'TWO_PUBLIC_UNAUTHENTICATED_NTP_PEERS',
                          'financial_authority':False,'bound_ms':145}
        def require_operational(self,rid):
            assert rid=='TEST_SUPPORT_CLOCK'
            self.count+=1
    monkeypatch.setattr(ntp,'IndependentNtpClock',FakeClock)
    fake=FakeClock();moment=[0.0]
    monkeypatch.setattr(b.time,'perf_counter',lambda:moment[0])
    monkeypatch.setattr(b.time,'sleep',lambda duration:moment.__setitem__(0,moment[0]+duration))
    result=b.qualify_independent_clock(fake,'TEST_SUPPORT_CLOCK')
    assert result=={'samples':37,'elapsed_seconds':180.0,'uncertainty_ms':145}
    assert fake.count==37


def test_clock_downgrade_refuses_after_second_sample(monkeypatch):
    from scripts.observation_runtime import atlas_independent_ntp_clock as ntp
    class FakeClock:
        def __init__(self):
            self.count=0
            self.evidence={'source':ntp.SOURCE,'domain':'TWO_PUBLIC_UNAUTHENTICATED_NTP_PEERS',
                           'financial_authority':False,'bound_ms':100}
        def require_operational(self,rid):
            self.count+=1
            if self.count==2:self.evidence['source']='WINDOWS_TIME'
    monkeypatch.setattr(ntp,'IndependentNtpClock',FakeClock)
    moment=[0.0]
    monkeypatch.setattr(b.time,'perf_counter',lambda:moment[0])
    monkeypatch.setattr(b.time,'sleep',lambda duration:moment.__setitem__(0,moment[0]+duration))
    with pytest.raises(ValueError,match='SUPPORT_VSAFE_TWO_PEER_CLOCK_CONTINUITY_REFUSED'):
        b.qualify_independent_clock(FakeClock(),'TEST_SUPPORT_CLOCK')


def test_source_has_no_release_selection_writer_or_financial_effect():
    raw=Path(b.__file__).read_text(encoding='utf-8')
    assert 'NativeInstalledReleaseVerifier().open(reference)' in raw
    assert 'support._install(' in raw
    assert 'APPROVAL_PIN = None' in raw
    assert 'require_install_approval()' in raw
    assert 'clock.revoke()' in raw
    assert 'select_release(' not in raw
    assert 'allow_live_order' not in raw
    assert not b.APPROVAL_FILE.exists()


def test_synthetic_successful_support_copy_handoff_has_no_native_effect(monkeypatch):
    from contextlib import contextmanager
    from scripts import release_selection
    from scripts.observation_runtime import atlas_independent_ntp_clock as ntp
    events=[]
    m=json.loads(b.MANIFEST.read_bytes())
    wanted=[{'path':'scripts/observation_runtime/atlas_independent_ntp_clock.py',
             'sha256':b.NTP_SHA}]
    class FakeClock:
        def __init__(self,*,runtime_id):
            self.runtime_id=runtime_id
            self.evidence={'source':ntp.SOURCE,'domain':'TWO_PUBLIC_UNAUTHENTICATED_NTP_PEERS',
                           'financial_authority':False,'bound_ms':125}
            events.append('create_ntp')
        def require_operational(self,rid):
            assert rid==self.runtime_id
            events.append('ntp_check')
        def revoke(self):events.append('clock_revoked')
    class FakeSupport:
        def prepare(self, manifest,archive,pin):
            assert pin==b.MANIFEST_SHA
            events.append('archive_reopened')
            return manifest,{'synthetic':'no_files'}
        def _install(self, manifest,files,*,parent_identity,admission):
            assert parent_identity==b.BASE_ID
            assert files=={'synthetic':'no_files'}
            admission()
            events.append('native_copy_intercepted')
            return {'handles_after_close':0,'receipt':{'selected':False,'financial_actions':0},
                    'receipt_sha256':'f'*64}
    class FakeVerifier:
        @contextmanager
        def open(self, reference):
            assert reference['release']==b.NEW
            events.append('native_app_intercepted')
            yield {'files':wanted}
    fake=FakeSupport()
    monkeypatch.setattr(b,'require_install_approval',
        lambda *,manifest=None:events.append('consent_rechecked'))
    monkeypatch.setattr(b,'inspect',
        lambda:events.append('native_manifest_checked') or (fake,m,
                 {'required_installed_application_sources':wanted}))
    monkeypatch.setattr(b,'qualify_independent_clock',
        lambda clock,rid:events.append('synthetic_180s') or
                 {'samples':37,'elapsed_seconds':180.0,'uncertainty_ms':125})
    monkeypatch.setattr(b,'require_v7_native_parents',
                        lambda support:events.append('selector_preserved'))
    monkeypatch.setattr(ntp,'IndependentNtpClock',FakeClock)
    monkeypatch.setattr(release_selection,'NativeInstalledReleaseVerifier',FakeVerifier)
    result=b.install_code_only()
    assert result['status']=='VERSION_SAFE_NONFINANCIAL_SUPPORT_INSTALLED_UNSELECTED'
    assert result['selected'] is False
    assert result['financial_authority'] is False
    assert events==[
        'consent_rechecked','native_manifest_checked','create_ntp',
        'synthetic_180s','consent_rechecked','native_manifest_checked',
        'ntp_check','native_app_intercepted','archive_reopened','ntp_check',
        'native_copy_intercepted','selector_preserved','clock_revoked']
    assert not Path(m['destination']).exists()
    assert not Path(m['control']).exists()


def test_fake_ntp_runtime_refuses_before_native_copy(monkeypatch):
    from scripts.observation_runtime import atlas_independent_ntp_clock as ntp
    class FakeClock:
        def __init__(self):
            self.evidence={'source':ntp.SOURCE,'domain':'WINDOWS_TIME',
                           'financial_authority':False,'bound_ms':1}
        def require_operational(self,rid):pass
    monkeypatch.setattr(ntp,'IndependentNtpClock',FakeClock)
    clock=FakeClock()
    t=[0.0]
    monkeypatch.setattr(b.time,'perf_counter',lambda:t[0])
    monkeypatch.setattr(b.time,'sleep',lambda delta:t.__setitem__(0,t[0]+delta))
    with pytest.raises(ValueError,match='SUPPORT_VSAFE_TWO_PEER_CLOCK_CONTINUITY_REFUSED'):
        b.qualify_independent_clock(clock,'TEST')
    assert t[0]==0.0


def test_independently_frozen_bootstrap_source_review_and_no_financial_grant():
    path=b.REPO/'docs/ATLAS_VERSION_SAFE_SUPPORT_BOOTSTRAP_SOURCE_REVIEW_R1_2026-11-09.json'
    raw=path.read_bytes()
    assert hashlib.sha256(raw).hexdigest()==(
        'e58cc6eaecf276ab69f6f4a5c793f65d4f2c1eb02ce5481ca57ca13b209e4766')
    row=json.loads(raw)
    assert row['status']=='SOURCE_VERIFIED_NOT_OPERATOR_PERMISSION'
    assert row['bootstrap_normalized_sha256']==b.sha(b.normalized(Path(b.__file__).read_bytes()))
    assert row['bootstrap_normalized_sha256']==(
        '995958f4b6fd8f132f8ccb24a869e2ea0d676fbe5f836f0b2a2094600430d90d')
    assert row['support_manifest_sha256']==b.MANIFEST_SHA
    assert row['archive_sha256']==b.ARCHIVE_SHA
    assert row['required_installed_app_sources']==24
    assert row['support_files']==10
    for field in ('support_install_authorized','release_selection_authorized',
                  'financial_accounts_authorized','providers_authorized',
                  'simulated_orders_authorized','live_orders_authorized',
                  'operator_approval_record_present'):
        assert row[field] is False


def test_fresh_source_review_cannot_be_treated_as_operator_consent():
    m=json.loads(b.MANIFEST.read_bytes())
    src=json.loads((b.REPO/'docs/ATLAS_VERSION_SAFE_SUPPORT_BOOTSTRAP_SOURCE_REVIEW_R1_2026-11-09.json').read_bytes())
    with pytest.raises(ValueError,match='SUPPORT_VSAFE_EXACT_OPERATOR_DECISION_REQUIRED'):
        b.validate_operator_decision(src,sid=SID,manifest=m)
    assert b.APPROVAL_PIN is None
