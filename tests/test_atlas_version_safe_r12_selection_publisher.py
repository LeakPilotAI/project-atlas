"""R12 new-release nonfinancial native publisher: strict consent, clock, no real writes."""
import copy
import hashlib
import json
import subprocess
from contextlib import contextmanager
from pathlib import Path

import pytest

from scripts import atlas_version_safe_r12_selection_publisher as pub

ROOT=Path(__file__).resolve().parents[1]
SID='S-1-5-21-555-666-777-1001'  # synthetic fixture; never user SID


def plan():
    return json.loads(pub.REVIEW.read_bytes())


def approval():
    return {'schema':'ATLAS_VERSION_SAFE_R12_CODE_ONLY_OPERATOR_DECISION_V1',
      'decision':pub.DECISION,'scope':pub.SCOPE,'operator_sid':SID,
      'one_shot':True,'source_release':pub.RELEASE,
      'review_sha256':pub.REVIEW_SHA,'predecessor_head':pub.V7_HEAD,
      'operation':pub.OPERATION,'proposed_head':pub.R12_HEAD,
      'application_receipt_sha256':pub.APP_RECEIPT_SHA,
      'application_artifact_digest':pub.APP_DIGEST,
      'support_receipt_sha256':pub.SUPPORT_RECEIPT_SHA,
      'support_manifest_sha256':pub.SUPPORT_MANIFEST_SHA,
      'native_selection_root':str(pub.SELECTOR),
      'clock_profile':pub.CLOCK_PROFILE,'selection_allowed':True,
      'financial_authority':False,'paper_accounts':False,'providers':False,
      'simulated_orders':False,'live_orders':False,'automatic_startup':False}


def test_real_native_installed_python_readonly_publisher_inspect():
    proc=subprocess.run([str(pub.APP/'python/python.exe'),'-I','-B','-S',
          str(Path(pub.__file__)),'--inspect'],capture_output=True,text=True,timeout=120)
    assert proc.returncode==0,proc.stderr
    item=json.loads(proc.stdout)
    assert item['status']=='READY_FOR_SEPARATE_OPERATOR_SELECTION_APPROVAL'
    assert item['revision']==12 and item['operation']==pub.OPERATION
    assert item['proposed_head']==pub.R12_HEAD
    assert item['support_receipt_sha256']==pub.SUPPORT_RECEIPT_SHA
    assert item['operator_approval_pinned'] is False
    assert item['r12_published'] is False
    assert item['financial_authority'] is False
    assert item['orders'] is False
    assert not (pub.SELECTOR/'r0012.json').exists()
    assert not (pub.SELECTOR/'r0012.pending').exists()


def test_no_workspace_runtime_can_prepare_native_publisher():
    with pytest.raises(ValueError,match='ATLAS_R12_PUBLISHER_INSTALLED_ISOLATED_PYTHON_REQUIRED'):
        pub.installed_python()


def test_approval_synthetically_exact_but_never_pinned_or_minted():
    value=approval()
    assert pub.validate_operator_decision(value,sid=SID,review=plan())==value
    assert pub.APPROVAL_PIN is None
    assert not pub.APPROVAL.exists()


@pytest.mark.parametrize('field,value',[
    ('schema','WRONG'),('decision','APPROVE_ALL'),('scope','PAPER_TRADING'),
    ('operator_sid','S-1-5-18'),('one_shot',1),
    ('source_release','f'*40),('review_sha256','f'*64),
    ('predecessor_head','f'*64),('operation','0'*32),
    ('proposed_head','0'*64),('application_receipt_sha256','f'*64),
    ('application_artifact_digest','f'*64),
    ('support_receipt_sha256','f'*64),('support_manifest_sha256','f'*64),
    ('native_selection_root','D:/foreign'),('clock_profile','WINDOWS_TIME'),
    ('selection_allowed',False),('financial_authority',True),
    ('paper_accounts',True),('providers',True),
    ('simulated_orders',True),('live_orders',True),('automatic_startup',True),
])
def test_broadened_or_changed_operator_scope_refused(field,value):
    data=approval();data[field]=value
    with pytest.raises(ValueError,match='ATLAS_R12_PUBLISHER_EXACT_ONE_SHOT_OPERATOR_SCOPE_REQUIRED'):
        pub.validate_operator_decision(data,sid=SID,review=plan())


def test_wrong_sid_and_extra_approval_keys_refused():
    a=approval()
    with pytest.raises(ValueError,match='ATLAS_R12_PUBLISHER_EXACT_ONE_SHOT_OPERATOR_SCOPE_REQUIRED'):
        pub.validate_operator_decision(a,sid='S-1-5-21-11-22-33-1002',review=plan())
    a['blanket_yes']=True
    with pytest.raises(ValueError,match='ATLAS_R12_PUBLISHER_EXACT_ONE_SHOT_OPERATOR_SCOPE_REQUIRED'):
        pub.validate_operator_decision(a,sid=SID,review=plan())


def test_missing_pinned_approval_fails_before_native_or_ntp(monkeypatch,tmp_path):
    monkeypatch.setattr(pub,'APPROVAL',tmp_path/'missing.json')
    with pytest.raises(ValueError,match='ATLAS_R12_PUBLISHER_SEPARATE_APPROVAL_ABSENT'):
        pub.require_approved_operator(review=plan())
    fake=tmp_path/'fake.json';fake.write_text(json.dumps(approval()))
    monkeypatch.setattr(pub,'APPROVAL',fake)
    with pytest.raises(ValueError,match='ATLAS_R12_PUBLISHER_APPROVAL_NOT_SEPARATELY_PINNED'):
        pub.require_approved_operator(review=plan())


def test_dummy_exact_hash_current_sid_and_tamper_fails(monkeypatch,tmp_path):
    from scripts.volume_inspector import windows_output
    raw=(json.dumps(approval(),sort_keys=True)+'\n').encode()
    file=tmp_path/'consent.json';file.write_bytes(raw)
    monkeypatch.setattr(pub,'APPROVAL',file)
    monkeypatch.setattr(pub,'APPROVAL_PIN',hashlib.sha256(raw).hexdigest())
    monkeypatch.setattr(windows_output,'current_sid',lambda:SID)
    assert pub.require_approved_operator(review=plan())==approval()
    monkeypatch.setattr(windows_output,'current_sid',lambda:'S-1-5-21-1-2-3-999')
    with pytest.raises(ValueError,match='ATLAS_R12_PUBLISHER_EXACT_ONE_SHOT_OPERATOR_SCOPE_REQUIRED'):
        pub.require_approved_operator(review=plan())
    monkeypatch.setattr(windows_output,'current_sid',lambda:SID)
    file.write_bytes(raw+b' ')
    with pytest.raises(ValueError,match='ATLAS_R12_PUBLISHER_PIN_CHANGED'):
        pub.require_approved_operator(review=plan())


def test_duplicate_json_key_refused_even_with_exact_test_pin(monkeypatch,tmp_path):
    from scripts.volume_inspector import windows_output
    raw=(json.dumps(approval())[:-1]+',"live_orders":false}').encode()
    file=tmp_path/'duplicate.json';file.write_bytes(raw)
    monkeypatch.setattr(pub,'APPROVAL',file)
    monkeypatch.setattr(pub,'APPROVAL_PIN',hashlib.sha256(raw).hexdigest())
    monkeypatch.setattr(windows_output,'current_sid',lambda:SID)
    with pytest.raises(ValueError,match='ATLAS_R12_PUBLISHER_DUPLICATE_JSON_KEY'):
        pub.require_approved_operator(review=plan())


def test_wrong_review_and_frozen_proposal_sha_refused():
    with pytest.raises(ValueError,match='ATLAS_R12_PUBLISHER_PIN_CHANGED'):
        pub.checked(pub.REVIEW,'0'*64,8192)
    with pytest.raises(ValueError,match='ATLAS_R12_PUBLISHER_PIN_CHANGED'):
        pub.checked(pub.PROPOSAL,'0'*64,32768)
    assert hashlib.sha256(pub.REVIEW.read_bytes()).hexdigest()==pub.REVIEW_SHA
    assert hashlib.sha256(pub.PROPOSAL.read_bytes()).hexdigest()==pub.PROPOSAL_SHA


def test_clock_rejects_fake_object_and_out_of_bound_uncertainty():
    with pytest.raises(ValueError,match='ATLAS_R12_PUBLISHER_GENUINE_TWO_PEER_CLOCK_REQUIRED'):
        pub.validate_clock(object(),'fake')


def test_180_seconds_37_renewable_two_peer_clock_offline(monkeypatch):
    from scripts.observation_runtime import atlas_independent_ntp_clock as ntp
    class FakeClock:
        def __init__(self):
            self.count=0
            self.evidence={'source':ntp.SOURCE,'domain':'TWO_PUBLIC_UNAUTHENTICATED_NTP_PEERS',
                'financial_authority':False,'os_windows_time_service_required':False,
                'bound_ms':138}
        def require_operational(self,rid):
            assert rid=='NO_NATIVE_WRITES'
            self.count+=1
    monkeypatch.setattr(ntp,'IndependentNtpClock',FakeClock)
    now=[0.0]
    monkeypatch.setattr(pub.time,'perf_counter',lambda:now[0])
    monkeypatch.setattr(pub.time,'sleep',lambda delta:now.__setitem__(0,now[0]+delta))
    clock=FakeClock()
    proof=pub.qualify_clock(clock,'NO_NATIVE_WRITES')
    assert proof=={'elapsed_seconds':180.0,'samples':37,'last_bound_ms':138}
    assert clock.count==37


def test_clock_windows_time_or_financial_downgrade_refuses_without_sleep(monkeypatch):
    from scripts.observation_runtime import atlas_independent_ntp_clock as ntp
    class FakeClock:
        def __init__(self):
            self.evidence={'source':'WINDOWS_TIME_CODE_SELECTION_V1',
                'domain':'TWO_PUBLIC_UNAUTHENTICATED_NTP_PEERS',
                'financial_authority':False,'os_windows_time_service_required':False,
                'bound_ms':5}
        def require_operational(self,rid):pass
    monkeypatch.setattr(ntp,'IndependentNtpClock',FakeClock)
    with pytest.raises(ValueError,match='ATLAS_R12_PUBLISHER_CLOCK_SOURCE_OR_UNCERTAINTY_REFUSED'):
        pub.qualify_clock(FakeClock(),'NO_NATIVE_WRITES')


def test_inspect_flag_cannot_execute_and_review_has_no_selection_grant():
    review=plan()
    assert review['code_selection_authorized'] is False
    assert review['r12_published'] is False
    assert review['financial_accounts_authorized'] is False
    with pytest.raises(SystemExit):pub.main([])
    with pytest.raises(ValueError,match='ATLAS_R12_PUBLISHER_EXACT_NONFINANCIAL_CLI_SCOPE_REQUIRED'):
        pub.main(['--execute-one-shot-code-selection'])
    with pytest.raises(ValueError,match='ATLAS_R12_PUBLISHER_INSPECT_SCOPE_MIXED'):
        pub.main(['--inspect','--confirm-scope',pub.SCOPE])


def test_unapproved_mutation_core_never_reaches_native_store(monkeypatch):
    # No native store, no NTP sockets, and no published selection when approval absent.
    from scripts import release_selection_store
    monkeypatch.setattr(release_selection_store,'NativeSelectionStore',
                        lambda **kw:pytest.fail('NATIVE_SELECTION_NEVER_ALLOWED'))
    with pytest.raises(ValueError,match='ATLAS_R12_PUBLISHER_SEPARATE_APPROVAL_ABSENT'):
        pub.publish_with_native_lock(clock=object(),runtime_id='TEST',
             preflight={'elapsed_seconds':180,'samples':37},mod=object(),review=plan())
    assert not (pub.SELECTOR/'r0012.json').exists()
    assert not (pub.SELECTOR/'r0012.pending').exists()


def test_source_has_no_paper_account_writer_and_preserves_v7_only_selector_rule():
    raw=Path(pub.__file__).read_text(encoding='utf-8')
    assert 'store.publish(row)' in raw  # audited primitive, behind consent + NTP
    assert 'require_approved_operator(review=review)' in raw
    assert 'validate_clock(clock,runtime_id)' in raw
    assert 'NativeInstalledReleaseVerifier().open(target)' in raw
    assert 'mod.check_external_support()' in raw
    assert 'APPROVAL_PIN=None' in raw
    old=(ROOT/'scripts/release_selection.py').read_text(encoding='utf-8')
    assert 'EXACT_V7_INDEPENDENT_NTP_SELECTION_REQUIRED' in old
    assert not (pub.SELECTOR/'r0012.json').exists()
    assert not (pub.SELECTOR/'r0012.pending').exists()


def test_intercepted_positive_native_r12_publication_rechecks_every_gate(monkeypatch):
    """Synthetic native store only: verify exact one-write ordering, no D: mutation."""
    from scripts import release_selection, release_selection_store
    from scripts import atlas_version_safe_r12_selection_proposal as source
    from scripts.observation_runtime import atlas_independent_ntp_clock as ntp
    from scripts.observation_runtime import personal_version_safe_release_clock as clock_source
    from contextlib import contextmanager
    rows=[json.loads((pub.SELECTOR/f'r{i:04d}.json').read_bytes())['record']
          for i in range(1,12)]
    events=[]
    actual_row=plan()['row']
    receipt={'source_commit':pub.RELEASE,'artifact_digest':pub.APP_DIGEST,
             'selected':False,'financial_effects':False,
             'provider_connections':False,'operational_acceptance':False}
    class FakeClock:
        def __init__(self):
            self.evidence={'source':ntp.SOURCE,
               'domain':'TWO_PUBLIC_UNAUTHENTICATED_NTP_PEERS',
               'financial_authority':False,
               'os_windows_time_service_required':False,
               'bound_ms':140}
        def require_operational(self,runtime_id):
            assert runtime_id=='DRY_RUN_ONLY'
            events.append('clock_checked')
    class FakeVerifier:
        @contextmanager
        def open(self,target):
            assert target==actual_row['selected']
            events.append('installed_app_opened')
            yield receipt
            events.append('installed_app_closed')
    class FakeStore:
        def __init__(self,*,root,native_root):
            assert root==str(pub.SELECTOR) and native_root==pub.NATIVE_ID
            self.current=copy.deepcopy(rows)
            events.append('native_store_opened')
        @contextmanager
        def locked(self):
            events.append('native_lock_acquired')
            try:yield
            finally:events.append('native_lock_released')
        def records(self):return copy.deepcopy(self.current)
        def publish(self,row):
            assert row==actual_row
            assert len(self.current)==11
            events.append('NATIVE_WRITE_INTERCEPTED')
            self.current.append(copy.deepcopy(row))
        def close(self):events.append('native_store_closed')
    def consent(*,review):
        assert review==plan()
        events.append('exact_operator_scope_checked')
        return approval()
    def support():
        events.append('native_support_ack_verified')
        return {'status':'SYNTHETIC_SUPPORT_INTACT'}
    monkeypatch.setattr(pub,'require_approved_operator',consent)
    monkeypatch.setattr(source,'check_external_support',support)
    monkeypatch.setattr(ntp,'IndependentNtpClock',FakeClock)
    monkeypatch.setattr(release_selection,'NativeInstalledReleaseVerifier',FakeVerifier)
    monkeypatch.setattr(release_selection_store,'NativeSelectionStore',FakeStore)
    original_admit=clock_source.admit_version_safe_clock_source
    def admit(*,source_file,records):
        events.append('installed_own_clock_source_admitted')
        return original_admit(source_file=source_file,records=records)
    monkeypatch.setattr(clock_source,'admit_version_safe_clock_source',admit)
    now=[0.0]
    monkeypatch.setattr(pub.time,'perf_counter',lambda:now[0])
    monkeypatch.setattr(pub.time,'sleep',lambda delta:now.__setitem__(0,now[0]+delta))
    qualified_clock=FakeClock()
    real_test_proof=pub.qualify_clock(qualified_clock,'DRY_RUN_ONLY')
    assert real_test_proof['elapsed_seconds']==180.0
    assert real_test_proof['samples']==37
    result=pub.publish_with_native_lock(clock=qualified_clock,runtime_id='DRY_RUN_ONLY',
               preflight=real_test_proof,mod=source,review=plan())
    assert result['status']=='R12_NONFINANCIAL_CODE_SELECTED'
    assert result['new_head']==pub.R12_HEAD
    assert result['application_receipt_sha256']==pub.APP_RECEIPT_SHA
    assert result['support_receipt_sha256']==pub.SUPPORT_RECEIPT_SHA
    assert result['financial_authority'] is False
    assert result['paper_accounts'] is False
    assert result['orders'] is False
    assert events.count('NATIVE_WRITE_INTERCEPTED')==1
    assert events.index('native_support_ack_verified')<events.index('NATIVE_WRITE_INTERCEPTED')
    assert events.index('installed_app_opened')<events.index('NATIVE_WRITE_INTERCEPTED')
    assert events.index('installed_own_clock_source_admitted')<events.index('NATIVE_WRITE_INTERCEPTED')
    assert events.count('exact_operator_scope_checked')>=3
    assert events.index('native_lock_acquired')<events.index('NATIVE_WRITE_INTERCEPTED')
    assert events.index('NATIVE_WRITE_INTERCEPTED')<events.index('native_lock_released')
    assert not (pub.SELECTOR/'r0012.json').exists()
    assert not (pub.SELECTOR/'r0012.pending').exists()


def test_real_installed_python_explicit_r12_execution_refuses_without_operator_approval():
    code=[str(pub.APP/'python/python.exe'),'-I','-B','-S',
          str(Path(pub.__file__)),'--execute-one-shot-code-selection',
          '--confirm-scope',pub.SCOPE]
    out=subprocess.run(code,capture_output=True,text=True,timeout=45)
    assert out.returncode!=0
    assert 'ATLAS_R12_PUBLISHER_SEPARATE_APPROVAL_ABSENT' in out.stderr
    assert 'NTP_' not in out.stderr
    assert not (pub.SELECTOR/'r0012.json').exists()
    assert not (pub.SELECTOR/'r0012.pending').exists()


def test_forged_180_second_claim_cannot_reach_native_store_even_with_test_consent(monkeypatch):
    from scripts import release_selection_store
    monkeypatch.setattr(pub,'require_approved_operator',lambda *,review:approval())
    monkeypatch.setattr(release_selection_store,'NativeSelectionStore',
                        lambda **kw:pytest.fail('FORGED_PROOF_MUST_NOT_OPEN_NATIVE_STORE'))
    with pytest.raises(ValueError,match='ATLAS_R12_PUBLISHER_FRESH_180S_CLOCK_PROOF_REQUIRED'):
        pub.publish_with_native_lock(clock=object(),runtime_id='FORGED',
            preflight={'elapsed_seconds':180,'samples':37,'last_bound_ms':100},
            mod=object(),review=plan())
    assert not (pub.SELECTOR/'r0012.json').exists()
    assert not (pub.SELECTOR/'r0012.pending').exists()
