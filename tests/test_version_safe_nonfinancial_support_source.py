"""New version-safe NTP support source: exact evidence; no native installation."""
import copy
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile

import pytest

from scripts import build_version_safe_support_candidate as vs
from scripts import support_deployment as old
from scripts.observation_runtime.atlas_independent_ntp_clock import IndependentNtpClock

MANIFEST = 'd61fd6c9fa18bd819f3328040e6c40581efc8faeef8eca8e6326eb110b919ad8'
SUPPORT = '6a22a5a7a75150a421cb769aee85e95a8e297b4c0a3457d503bc808c661ff674'
ARCHIVE = '3bf7ff32eeda8235afaa5f6befe0abb66f09faac0096dc6fadb8e6cc7782a6b2'


def evidence():
    assert hashlib.sha256((vs.DEST/'deployment.json').read_bytes()).hexdigest()==MANIFEST
    assert hashlib.sha256((vs.DEST/'support-source.zip').read_bytes()).hexdigest()==ARCHIVE
    m=json.loads((vs.DEST/'deployment.json').read_bytes())
    with ZipFile(vs.DEST/'support-source.zip') as z:
        raw=z.read('support-manifest.json')
    assert hashlib.sha256(raw).hexdigest()==SUPPORT
    return m,json.loads(raw)


def test_complete_create_only_archive_and_nonfinancial_app_proof():
    m,p=evidence()
    # Once support has been physically installed, the old source-only
    # verifier must refuse to reinterpret its create-only target as absent.
    with pytest.raises(ValueError,match='VERSION_SAFE_SUPPORT_TARGET_ALREADY_EXISTS'):
        vs.verify()
    assert hashlib.sha256((vs.DEST/'support-source.zip').read_bytes()).hexdigest()==ARCHIVE
    assert hashlib.sha256((vs.DEST/'deployment.json').read_bytes()).hexdigest()==MANIFEST
    assert m['schema']=='QD_SUPPORT_DEPLOYMENT_V2'
    assert m['status']=='REVIEW_INVENTORY_NOT_PERMISSION'
    assert m['application']=={
        'release':vs.NEW,'root':str(vs.APPLICATION_PATH),
        'receipt':str(vs.APP_RECEIPT),'receipt_sha256':vs.RECEIPT_SHA,
        'artifact_digest':vs.ARTIFACT}
    assert m['runtime']['providers'] is False
    assert m['runtime']['financial_writers'] is False
    assert m['runtime']['workspace_fallback'] is False
    assert p['application_release']==vs.NEW
    assert p['clock']==vs.NTP
    for flag in ('installation_authorized','promotion_authorized',
                 'providers_authorized','financial_startup_authorized'):
        assert p[flag] is False
    assert len(p['required_installed_application_sources'])==24
    assert len(m['files'])==10
    assert Path(m['destination']).is_dir()
    assert Path(m['control']).is_dir()


def test_explicit_installed_ntp_and_six_financial_admission_source_pins():
    m,p=evidence()
    receipt,installed=vs.verify_predecessor_and_app()
    assert receipt['selected'] is False
    assert receipt['artifact_digest']==vs.ARTIFACT
    req={r['path']:r['sha256'] for r in p['required_installed_application_sources']}
    assert set(vs.PINS).issubset(req)
    for path,pin in vs.PINS.items():
        assert req[path]==pin==installed[path]
    for name in vs.SIX:
        path='scripts/observation_runtime/'+name
        assert req[path]==installed[path]
    assert vs.validate_new_profile(m,p,installed)==m


def test_historical_support_adapter_never_approves_new_ntp_profile():
    m,p=evidence()
    assert old.support_clock_profile(m)=='WINDOWS_TIME_CODE_SELECTION_V1'
    assert old.support_clock_profile({'application':{
        **m['application'],'release':old.V8_NTP_APP,
        'receipt_sha256':old.V8_NTP_RECEIPT_SHA256,
        'artifact_digest':old.V8_NTP_ARTIFACT_DIGEST}})==old.V7_NTP_CLOCK_PROFILE
    # This is why new release support is SOURCE-ONLY and not yet installable
    # with historical code; NEVER downgrade to Windows Time as a shortcut.


@pytest.mark.parametrize('field',('source','clock','commission'))
def test_new_ntp_installed_source_pin_damage_is_refused(field):
    m,p=evidence()
    _,installed=vs.verify_predecessor_and_app()
    forged=copy.deepcopy(p)
    name=list(vs.PINS)[{'source':0,'clock':1,'commission':2}[field]]
    rows=forged['required_installed_application_sources']
    next(x for x in rows if x['path']==name)['sha256']='f'*64
    expected=('VERSION_SAFE_SUPPORT_FINANCIAL_INTERFACE_PIN_REQUIRED'
              if field=='commission' else 'VERSION_SAFE_SUPPORT_CLOCK_PIN_REQUIRED')
    with pytest.raises(ValueError,match=expected):
        vs.validate_new_profile(m,forged,installed)


def test_incorrect_clock_issuer_or_financial_flags_refuse():
    m,p=evidence()
    _,installed=vs.verify_predecessor_and_app()
    wrong=copy.deepcopy(p)
    wrong['clock']['issuer']='WINDOWS_TIME_CODE_SELECTION_V1'
    with pytest.raises(ValueError,match='VERSION_SAFE_SUPPORT_EXACT_NTP_PACKAGE_REQUIRED'):
        vs.validate_new_profile(m,wrong,installed)
    for key in ('installation_authorized','promotion_authorized',
                'financial_startup_authorized','providers_authorized'):
        wrong=copy.deepcopy(p)
        wrong[key]=True
        with pytest.raises(ValueError,match='VERSION_SAFE_SUPPORT_EXACT_NTP_PACKAGE_REQUIRED'):
            vs.validate_new_profile(m,wrong,installed)


def test_changed_native_app_receipt_and_support_manifest_refuse(monkeypatch):
    m,p=evidence()
    _,installed=vs.verify_predecessor_and_app()
    wrong=copy.deepcopy(m)
    wrong['application']['artifact_digest']='f'*64
    with pytest.raises(ValueError,match='VERSION_SAFE_SUPPORT_EXACT_APP_SCOPE_REQUIRED'):
        vs.validate_new_profile(wrong,p,installed)
    monkeypatch.setattr(vs,'RECEIPT_SHA','f'*64)
    with pytest.raises(ValueError,match='VERSION_SAFE_SUPPORT_INSTALLED_RECEIPT_PIN_REQUIRED'):
        vs.verify_predecessor_and_app()


def test_old_v8_native_support_unmodified_and_new_target_not_selected():
    m,p=evidence()
    old_receipt=Path('D:/AtlasRuntime/support-installations/03122857979ccbc97572acda7a63d98640bb081c868de13929dcedd556883a26/receipt.json')
    assert hashlib.sha256(old_receipt.read_bytes()).hexdigest()==(
        '85bd24430576a8cfde7735c8412263da4ca6aea8459c55ec3d70c1f6a0c62d60')
    from scripts.release_selection import digest
    selected=json.loads(Path('D:/AtlasRuntime/selection/r0011.json').read_bytes())['record']
    assert digest(selected)==vs.V7_HEAD
    assert selected['selected']['release']==vs.V7
    assert not Path('D:/AtlasRuntime/selection/r0012.json').exists()
    assert Path(m['destination']).is_dir()
    assert Path(m['control']).is_dir()


def test_second_source_build_refuses_without_overwrite():
    with pytest.raises(ValueError,match='VERSION_SAFE_SUPPORT_CREATE_ONLY_CANDIDATE_EXISTS'):
        vs.build()


def test_legacy_native_support_installer_refuses_independent_ntp_as_old_profile(monkeypatch):
    m,p=evidence()
    monkeypatch.setattr(old,'_install',lambda *a,**kw:pytest.fail('NATIVE_INSTALL_MUST_NOT_RUN'))
    clock=object.__new__(IndependentNtpClock)
    with pytest.raises(ValueError,match='GENUINE_REVIEWED_SUPPORT_CLOCK_PROFILE_REQUIRED'):
        old.install_operational(approved=True,manifest=m,
            archive=vs.DEST/'support-source.zip',manifest_sha256=MANIFEST,
            parent_identity=[4004218753,65536,1113770],clock=clock)
