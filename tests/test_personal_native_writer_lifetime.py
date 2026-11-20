"""Native writer liveness admission used before actual personal PAPER activation.

An exited PID, changed creation FILETIME or foreign executable cannot pass
from enrollment JSON directly into once-only activation publication.
"""
import copy
import os
import subprocess
import sys

import pytest

from scripts.observation_runtime import personal_native_writer_lifetime as native
from scripts.observation_runtime.atlas_r15_paper_offline_commissioning import (
    ARTIFACT,RELEASE,
)
from scripts.observation_runtime.atlas_r15_disposable_writer_process_audit import (
    _windows_handle_identity,
)
from app.services.quality_dips_autonomous_enrollment import WRITERS as QD_ROLES
from app.services.perp_operational_contract import WRITERS as HL_ROLES


def schemas(identity=None):
    if identity is None:
        identity={'schema':'QD_OP_PROCESS_ID_V1','pid':30303,
                  'creation_filetime':134388575861975776,
                  'image':str(RELEASE/'python/python.exe')}
    qd={'release_digest':ARTIFACT,
        'writers':{role:copy.deepcopy(identity) for role in QD_ROLES}}
    hl={'release_digest':ARTIFACT,
        'writers':{role:copy.deepcopy(identity) for role in HL_ROLES}}
    return qd,hl


def test_exact_r15_native_writer_12_roles_share_validated_process_identity():
    qd,hl=schemas()
    old=copy.deepcopy((qd,hl))
    rows,selected=native.writer_roster(qd,hl,release_digest=ARTIFACT)
    assert (qd,hl)==old
    assert len(rows)==12
    assert set(r[0] for r in rows)=={'QUALITY_DIPS','HYPERLIQUID'}
    assert len(set(rows.values()))==1
    assert selected['revision']==14
    assert selected['financial_authority'] is False


@pytest.mark.parametrize('damage',[
    'missing_qd_role','missing_hl_funding','missing_hl_mark',
    'fake_extra_role','wrong_release','wrong_qd_release','wrong_hl_release',
    'foreign_executable','foreign_perp_executable','pid_reused',
    'bad_filetime','bad_process_pid','pid_boolean','invalid_filetime',
    'foreign_schema','unnormalized_path','percent_path','wrong_drive',
])
def test_native_activation_structural_live_writer_roster_refuses_forgery(damage):
    qd,hl=schemas()
    if damage=='missing_qd_role':qd['writers'].pop('source')
    elif damage=='missing_hl_funding':hl['writers'].pop('funding')
    elif damage=='missing_hl_mark':hl['writers'].pop('mark')
    elif damage=='fake_extra_role':hl['writers']['options']=hl['writers']['source']
    elif damage=='wrong_release':pass
    elif damage=='wrong_qd_release':qd['release_digest']='a'*64
    elif damage=='wrong_hl_release':hl['release_digest']='a'*64
    elif damage=='foreign_executable':
        qd['writers']['decision']['image']=r'D:\Other\python.exe'
    elif damage=='foreign_perp_executable':
        hl['writers']['mark']['image']=r'D:\Other\python.exe'
    elif damage=='pid_reused':
        hl['writers']['mark']['creation_filetime']+=1
    elif damage=='bad_filetime':
        hl['writers']['mark']['creation_filetime']+=1
    elif damage=='bad_process_pid':
        qd['writers']['source']['pid']=-1
    elif damage=='pid_boolean':qd['writers']['decision']['pid']=True
    elif damage=='invalid_filetime':qd['writers']['decision']['creation_filetime']=0
    elif damage=='foreign_schema':hl['writers']['source']['schema']='FAKE'
    elif damage=='unnormalized_path':
        qd['writers']['decision']['image']=str(RELEASE)+r'\python\..\python\python.exe'
    elif damage=='percent_path':qd['writers']['decision']['image']=r'D:\%USERPROFILE%\python.exe'
    elif damage=='wrong_drive':qd['writers']['decision']['image']=r'C:\python.exe'
    digest='f'*64 if damage=='wrong_release' else ARTIFACT
    with pytest.raises((ValueError,TypeError,KeyError)):
        native.writer_roster(qd,hl,release_digest=digest)


@pytest.mark.skipif(sys.platform!='win32',reason='Native Windows retained handle required')
def test_actual_selected_r15_child_handles_held_alive_then_expired_refused():
    # No imports from the project in the subprocess, no file writes, no data.
    child=subprocess.Popen(
        [str(RELEASE/'python/python.exe'),'-I','-B','-S','-c',
         'import time;time.sleep(2.5)'],
        cwd=str(RELEASE),stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW)
    try:
        observed=_windows_handle_identity(child._handle)
        identity={'schema':'QD_OP_PROCESS_ID_V1','pid':child.pid,
                  'creation_filetime':observed['creation_filetime'],
                  'image':observed['image']}
        qd,hl=schemas(identity)
        with native.retain_live_enrollment_writers(qd,hl,release_digest=ARTIFACT) as held:
            assert held.verify_still_running() is True
            assert child.poll() is None
        # The returned context cannot be reused as an enrolled authority.
        assert child.poll() is None
        child.wait(timeout=6)
        assert child.returncode==0
        with pytest.raises(ValueError,match='PERSONAL_ACTIVATION_WRITER_PROCESS_EXITED|PERSONAL_ACTIVATION_ACTUAL_PROCESS_HANDLE_UNAVAILABLE'):
            with native.retain_live_enrollment_writers(qd,hl,release_digest=ARTIFACT):
                pytest.fail('Expired writer must be refused')
    finally:
        if child.poll() is None:
            child.terminate()
            child.wait(timeout=5)


@pytest.mark.skipif(sys.platform!='win32',reason='Native Windows retained handle required')
def test_real_current_process_pid_with_wrong_filetime_never_passes():
    from scripts.observation_runtime.atlas_r15_paper_offline_commissioning import selected_code
    assert selected_code()['revision']==14
    # The current Python might not be installed R15. Its correct live PID
    # must not be accepted under a substituted R15 executable identity.
    foreign={'schema':'QD_OP_PROCESS_ID_V1','pid':os.getpid(),
             'creation_filetime':134388500000000000,
             'image':str(RELEASE/'python/python.exe')}
    qd,hl=schemas(foreign)
    with pytest.raises(ValueError,match='PERSONAL_ACTIVATION_PROCESS_INCARCATION_OR_IMAGE_CHANGED|PERSONAL_ACTIVATION_WRITER_PROCESS_EXITED'):
        with native.retain_live_enrollment_writers(qd,hl,release_digest=ARTIFACT):
            pytest.fail('Foreign current-process image must not be admitted')


@pytest.mark.skipif(sys.platform!='win32',reason='Native R15 Windows resource IDs required')
def test_actual_r15_commission_refuses_missing_original_owned_job_before_clock_or_native_publication(
        tmp_path,monkeypatch):
    import json
    from pathlib import Path
    from app.services.paper_financial_replay import digest
    from app.services.personal_paper_runtime import validate_policy
    from scripts.observation_runtime.atlas_independent_ntp_clock import SOURCE
    from scripts.observation_runtime import personal_activation_commission as commission
    from scripts.observation_runtime.atlas_r15_two_account_enrollment_handoff import (
        inspect as draft,
    )
    from app.services.quality_dips_autonomous_enrollment import (
        validate_enrollment as validate_qd,
    )
    from app.services.perp_operational_contract import (
        validate_enrollment as validate_hl,
    )
    from scripts.observation_runtime.personal_version_safe_release_clock import PROFILE

    original=draft()
    missing={'schema':'QD_OP_PROCESS_ID_V1','pid':2_100_000_000,
             'creation_filetime':134388535100000000,
             'image':str(RELEASE/'python/python.exe')}
    records={}
    for lane,roles,validator in (
            ('QUALITY_DIPS',QD_ROLES,validate_qd),
            ('HYPERLIQUID',HL_ROLES,validate_hl)):
        enrollment=copy.deepcopy(original['accounts'][lane][
            'provisional_r15_native_enrollment_unaccepted'])
        enrollment['writers']={role:copy.deepcopy(missing) for role in roles}
        enrollment['acceptance_id']='SYNTHETIC_EXPIRED_ID_TEST_ONLY'
        records[lane]=validator(enrollment)

    accounts={lane:digest(e) for lane,e in records.items()}
    policy=json.loads((Path(__file__).resolve().parents[1]/
        'docs/ATLAS_PERSONAL_PAPER_RELEASE_POLICY.json').read_text(encoding='utf-8'))
    record={'schema':'ATLAS_PERSONAL_ACTIVATION_V1',
            'origin':'LOCAL_OPERATOR','actions':['READ_ONLY'],
            'release_digest':ARTIFACT,'accounts':accounts,
            'policy_digest':digest(validate_policy(policy))}
    files={}
    for name,body in (
            ('qd',records['QUALITY_DIPS']),('perp',records['HYPERLIQUID']),
            ('accounts',accounts),('policy',policy),('record',record)):
        p=tmp_path/(name+'.json')
        p.write_text(json.dumps(body,sort_keys=True),encoding='utf-8')
        files[name]=str(p)
    # R15 requires the already-retained original owned Job; even a fabricated
    # enrolled PID must not be opened, nor trigger clock/native publication.
    monkeypatch.setattr(commission,'NativeVersionSafePaperOperatorClock',
                        lambda **kw:pytest.fail('INVALID_PID_MUST_NOT_ACQUIRE_CLOCK'))
    monkeypatch.setattr(commission,'publish_personal_activation',
                        lambda **kw:pytest.fail('INVALID_PID_MUST_NOT_PUBLISH_NATIVE_ACTIVATION'))
    with pytest.raises(ValueError,match='ACTIVATION_R15_RETAINED_NATIVE_JOB_REQUIRED'):
        commission.commission(
            root=r'D:\AtlasCustody\PersonalPaper\expired-writer-only-test',
            record_path=files['record'],policy_path=files['policy'],
            release_digest=ARTIFACT,accounts_path=files['accounts'],
            expected_clock_source=SOURCE,runtime_id='EXPIRED_TEST_ONLY',
            qd_enrollment_path=files['qd'],perp_enrollment_path=files['perp'],
            clock_profile=PROFILE)
    assert not Path(r'D:\AtlasCustody\PersonalPaper\expired-writer-only-test').exists()
