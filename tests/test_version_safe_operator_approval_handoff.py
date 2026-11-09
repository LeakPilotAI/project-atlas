"""Source-only operator decision and explicit invocation, never actual native effect."""
import hashlib
import json
from pathlib import Path

import pytest

from scripts import install_version_safe_candidate as installer

SID='S-1-5-21-111-222-333-1001'  # disposable synthetic test value


def decision():
    return {
        'schema':installer.APPROVAL_SCHEMA,
        'decision':installer.APPROVAL_DECISION,
        'scope':installer.APPROVAL_SCOPE,
        'operator_sid':SID,
        'source_commit':installer.SOURCE,
        'archive_sha256':installer.ARCHIVE,
        'inventory_sha256':installer.INVENTORY,
        'dependency_sha256':installer.DEPENDENCY,
        'review_sha256':installer.REVIEW_SHA,
        'predecessor_head':installer.V7_HEAD,
        'destination':str(Path('D:/AtlasRuntime/releases')/installer.SOURCE),
        'receipt_path':str(installer.ROOT/'logs/diagnostics'/(
            'qd-unselected-release-'+installer.SOURCE+'.json')),
        'confirmation':installer.APPROVAL_CONFIRMATION,
        'one_shot':True,
        'selection_allowed':False,
        'financial_authority':False,
        'paper_account_inception':False,
        'provider_access':False,
        'live_orders':False,
    }


def test_pure_approved_scope_synthetically_validates_without_grant():
    d=decision()
    assert installer.validate_operator_decision(d,operator_sid=SID) is d
    assert installer.APPROVAL_PIN is None
    assert not installer.APPROVAL.exists()


@pytest.mark.parametrize('change,value',[
    ('schema','WRONG'),('decision','GENERIC_APPROVE'),
    ('scope','ALL_ATLAS_ACTIONS'),('operator_sid','S-1-5-18'),
    ('source_commit','0'*40),('archive_sha256','0'*64),
    ('inventory_sha256','0'*64),('dependency_sha256','0'*64),
    ('review_sha256','0'*64),('predecessor_head','0'*64),
    ('destination','D:/AtlasRuntime/releases/unreviewed'),
    ('receipt_path','D:/unreviewed.json'),('confirmation','YES'),
    ('one_shot',1),('selection_allowed',True),
    ('financial_authority',1),('paper_account_inception',True),
    ('provider_access',True),('live_orders',True),
])
def test_wrong_operator_scope_identity_or_flags_refused(change,value):
    d=decision();d[change]=value
    with pytest.raises(ValueError,match='VERSION_SAFE_INSTALL_EXACT_OPERATOR_DECISION_REQUIRED'):
        installer.validate_operator_decision(d,operator_sid=SID)


def test_approval_rejects_extra_fields_and_foreign_windows_sid():
    d=decision();d['is_admin']=True
    with pytest.raises(ValueError):installer.validate_operator_decision(d,operator_sid=SID)
    d.pop('is_admin')
    with pytest.raises(ValueError):
        installer.validate_operator_decision(d,operator_sid='S-1-5-21-444-555-666-1002')
    with pytest.raises(ValueError):
        installer.validate_operator_decision(d,operator_sid='')


def test_manually_forged_unpinned_file_cannot_grant_approval(monkeypatch,tmp_path):
    path=tmp_path/'approval.json'
    path.write_text(json.dumps(decision()),encoding='utf-8')
    monkeypatch.setattr(installer,'APPROVAL',path)
    assert installer.APPROVAL_PIN is None
    with pytest.raises(ValueError,match='VERSION_SAFE_INSTALL_APPROVAL_NOT_YET_REVIEWED'):
        installer.require_separate_operator_approval()


def test_disposable_exact_pinned_operator_record_requires_matching_native_sid(monkeypatch,tmp_path):
    from scripts.volume_inspector import windows_output
    path=tmp_path/'approved.json'
    raw=(json.dumps(decision(),sort_keys=True,separators=(',',':'))+'\n').encode()
    path.write_bytes(raw)
    monkeypatch.setattr(installer,'APPROVAL',path)
    monkeypatch.setattr(installer,'APPROVAL_PIN',hashlib.sha256(raw).hexdigest())
    monkeypatch.setattr(windows_output,'current_sid',lambda:SID)
    assert installer.require_separate_operator_approval()==decision()
    monkeypatch.setattr(windows_output,'current_sid',lambda:'S-1-5-21-444-555-666-1002')
    with pytest.raises(ValueError,match='VERSION_SAFE_INSTALL_EXACT_OPERATOR_DECISION_REQUIRED'):
        installer.require_separate_operator_approval()
    monkeypatch.setattr(windows_output,'current_sid',lambda:SID)
    path.write_text(json.dumps({**decision(),'live_orders':True}),encoding='utf-8')
    with pytest.raises(ValueError,match='VERSION_SAFE_INSTALL_PIN_CHANGED'):
        installer.require_separate_operator_approval()


def test_double_key_duplicate_approval_refused_even_with_matching_test_pin(monkeypatch,tmp_path):
    from scripts.volume_inspector import windows_output
    raw=(json.dumps(decision(),sort_keys=True)[:-1]+', "live_orders": false}').encode()
    path=tmp_path/'duplicate.json';path.write_bytes(raw)
    monkeypatch.setattr(installer,'APPROVAL',path)
    monkeypatch.setattr(installer,'APPROVAL_PIN',hashlib.sha256(raw).hexdigest())
    monkeypatch.setattr(windows_output,'current_sid',lambda:SID)
    with pytest.raises(ValueError,match='VERSION_SAFE_INSTALL_DUPLICATE_JSON_KEY'):
        installer.require_separate_operator_approval()


def test_readonly_inspect_reports_pinned_plan_but_no_install():
    result=installer.main(['--inspect'])
    assert result['status']=='SOURCE_AND_NATIVE_PLAN_VALIDATED_NOT_APPROVED'
    assert result['source_files']==1008 and result['python_files']==9566
    assert result['target_files']==10574 and result['target_bytes']==265175432
    assert result['approval_pinned'] is False
    assert result['install_attempted'] is False
    assert result['financial_authority'] is False
    assert result['release_selection'] is False
    assert not (Path('D:/AtlasRuntime/releases')/installer.SOURCE).exists()


def test_explicit_cli_execution_refuses_before_ntp_or_native_when_no_approval(monkeypatch):
    from scripts.observation_runtime import atlas_independent_ntp_clock
    monkeypatch.setattr(atlas_independent_ntp_clock,'IndependentNtpClock',
                        lambda **kwargs:pytest.fail('NETWORK_BEFORE_APPROVAL'))
    monkeypatch.setattr(installer,'_copy_prepared_code',
                        lambda **kwargs:pytest.fail('NATIVE_COPY_BEFORE_APPROVAL'))
    with pytest.raises(ValueError,match='VERSION_SAFE_INSTALL_EXACT_CLI_CONFIRMATION_REQUIRED'):
        installer.main(['--execute-reviewed-code-only'])
    with pytest.raises(ValueError,match='VERSION_SAFE_INSTALL_SEPARATE_OPERATOR_APPROVAL_ABSENT'):
        installer.main(['--execute-reviewed-code-only','--confirm-scope',
                        installer.APPROVAL_CONFIRMATION])
    with pytest.raises(ValueError,match='VERSION_SAFE_INSTALL_INSPECT_NO_EXECUTION_FLAG'):
        installer.main(['--inspect','--confirm-scope',installer.APPROVAL_CONFIRMATION])


def test_cli_still_has_no_implicit_os_startup_or_native_grant():
    source=(installer.ROOT/'scripts/install_version_safe_candidate.py').read_text(encoding='utf-8')
    assert 'APPROVAL_PIN = None' in source
    assert 'require_separate_operator_approval()  # before any external NTP access' in source
    assert 'finally:\n        clock.revoke()' in source
    assert 'from scripts.release_selection_store import NativeSelectionStore' in source
    assert 'selection_allowed' in source and 'financial_authority' in source
    assert not Path('D:/AtlasRuntime/selection/r0012.json').exists()


def test_simulated_separately_pinned_cli_proves_exact_invocation_and_revoke(monkeypatch,tmp_path):
    from scripts.volume_inspector import windows_output
    from scripts.observation_runtime import atlas_independent_ntp_clock as ntp
    raw=(json.dumps(decision(),sort_keys=True)+'\n').encode()
    path=tmp_path/'operator.json';path.write_bytes(raw)
    monkeypatch.setattr(installer,'APPROVAL',path)
    monkeypatch.setattr(installer,'APPROVAL_PIN',hashlib.sha256(raw).hexdigest())
    monkeypatch.setattr(windows_output,'current_sid',lambda:SID)
    events=[]
    class FakeClock:
        def __init__(self,*,runtime_id):
            self.runtime_id=runtime_id
            events.append(('new_clock',runtime_id))
        def require_operational(self,runtime_id):
            assert runtime_id==self.runtime_id
            events.append(('operational',runtime_id))
        def revoke(self):
            events.append(('revoke',None))
    monkeypatch.setattr(ntp,'IndependentNtpClock',FakeClock)
    ready={'status':'TEST_ONLY_READONLY_REVIEW'}
    monkeypatch.setattr(installer,'prepare_reviewed_code',lambda:ready)
    monkeypatch.setattr(installer,'_qualify_native_clock_180s',
        lambda clock,rid: events.append(('synthetic_180s',rid)) or
           {'elapsed_seconds':180.0,'samples':37,'bound_ms':130})
    monkeypatch.setattr(installer,'require_v7_predecessor',lambda:True)
    def native_intercept(*,prepared_review,clock,preflight):
        assert prepared_review is ready
        assert type(clock) is FakeClock
        assert preflight['samples']==37
        events.append(('NATIVE_INTERCEPTED_NO_WRITE',clock.runtime_id))
        return {'status':'TEST_ONLY_ZERO_NATIVE_EFFECT'}
    monkeypatch.setattr(installer,'_native_copy_only_after_approval',native_intercept)
    result=installer.main(['--execute-reviewed-code-only',
          '--confirm-scope',installer.APPROVAL_CONFIRMATION])
    assert result['status']=='TEST_ONLY_ZERO_NATIVE_EFFECT'
    assert [row[0] for row in events]==[
        'new_clock','operational','synthetic_180s','NATIVE_INTERCEPTED_NO_WRITE','revoke']
    assert not (Path('D:/AtlasRuntime/releases')/installer.SOURCE).exists()
