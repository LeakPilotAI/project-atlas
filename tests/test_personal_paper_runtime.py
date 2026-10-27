"""Operator profile,activation separation and existing V4/V3 reuse;memory only."""
import copy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from app.services.paper_financial_replay import digest
from app.services.personal_paper_runtime import (
    CHECKS,
    PERSONAL_GATES,
    PROFILE,
    PersonalNativeEnrollment,
    PersonalOperatorInstallation,
    checked_personal_installation,
    compose_personal_qd,
    compose_personal_unified,
    validate_policy,
)
from app.services.quality_dips_autonomous_enrollment import AutonomousNativeEnrollment
from test_quality_dips_autonomous_enrollment import fixture as legacy_fixture

ROOT=Path(__file__).resolve().parents[1]


def policy():return json.loads((ROOT/'docs/ATLAS_PERSONAL_PAPER_RELEASE_POLICY.json').read_bytes())


def installed(accounts=None,ports=None):
    p=policy();now=[1000];facts=dict.fromkeys(CHECKS,True);reader=SimpleNamespace()
    reader.value={'schema':'ATLAS_PERSONAL_ACTIVATION_V1','profile':PROFILE,'origin':'LOCAL_OPERATOR','activation_id':'SYNTHETIC-UNIT-ACTIVATION','operator_id':'SYNTHETIC-OPERATOR','policy_digest':digest(p),'release_digest':'c'*64,'accounts':accounts or {'QUALITY_DIPS':'a'*64},'issued_at':999,'expires_at':1100,'actions':['READ_ONLY','AUTO_PAPER','SHUTDOWN_FLATTEN','EMERGENCY_STOP']}
    reader.read=lambda:copy.deepcopy(reader.value)
    owner=SimpleNamespace(current_operator=lambda:'SYNTHETIC-OPERATOR');tech=SimpleNamespace(inspect=lambda _:dict(facts));clock=lambda:now[0]
    i=PersonalOperatorInstallation(policy=p,reader=reader,identity=owner,technical=tech,clock=clock,components=ports or {'port':reader},release_digest='c'*64,accounts=reader.value['accounts'])
    return SimpleNamespace(**locals())


def test_policy_applied_without_financial_activation():
    p=validate_policy(policy());assert not p['startup_authorized'] and not p['financial_publication_authorized']
    assert not p['authority']['external_reviewer_required']


@pytest.mark.parametrize('kind',['qd-entry','positions','money','profile','startup','reviewer','withdrawal','netting'])
def test_policy_rejects_risk_or_capability_change(kind):
    p=policy()
    if kind=='qd-entry':p['accounts']['QUALITY_DIPS']['max_entry_notional']='101'
    elif kind=='positions':p['accounts']['QUALITY_DIPS']['max_open_positions']=2
    elif kind=='money':p['accounts']['HYPERLIQUID']['opening_balance']='2000'
    elif kind=='profile':p['profile_id']='STRICT'
    elif kind=='startup':p['startup_authorized']=True
    elif kind=='reviewer':p['authority']['external_reviewer_required']=True
    elif kind=='withdrawal':p['prohibited_capabilities'].remove('WITHDRAWAL')
    else:p['account_separation']['cash_netting']=True
    with pytest.raises(ValueError):validate_policy(p)


@pytest.mark.parametrize('damage',['origin','operator','profile','expired','release','policy','account','revoked','technical','ports','scope'])
def test_no_activation_from_policy_test_record_or_bad_facts(damage):
    s=installed()
    if damage=='origin':s.reader.value['origin']='SYNTHETIC_AUTHORITY'
    elif damage=='operator':s.reader.value['operator_id']='FOREIGN'
    elif damage=='profile':s.reader.value['profile']='AUTONOMOUS_PAPER_ONLY_V1'
    elif damage=='expired':s.now[0]=1101
    elif damage=='release':s.reader.value['release_digest']='b'*64
    elif damage=='policy':s.reader.value['policy_digest']='b'*64
    elif damage=='account':s.reader.value['accounts']={'HYPERLIQUID':'a'*64}
    elif damage=='revoked':s.i.revoke()
    elif damage=='technical':s.facts['FINANCIAL_INTEGRITY']=False
    elif damage=='ports':s.i.reader=SimpleNamespace(read=lambda:s.reader.value)
    else:s.i.accounts={'QUALITY_DIPS':'b'*64}
    with pytest.raises(ValueError),s.i.lease({'session':'synthetic'}):pytest.fail('bad activation reached action')


def test_personal_installation_has_no_historical_gate_acceptances():
    s=installed()
    with s.i.lease({'session':'synthetic'}) as lease:
        proof=checked_personal_installation(lease,{'session':'synthetic'})
        assert set(proof['gates'])==set(PERSONAL_GATES) and not set(proof['gates'])&{'B1','C1','D1','E1'}
        assert lease.check_components({'port':s.reader})
        assert not lease.check_components({'port':SimpleNamespace()})


def test_revocation_during_action_refuses_on_exit():
    s=installed()
    with pytest.raises(ValueError), s.i.lease({'session':'synthetic'}):s.i.revoke()


def test_personal_native_reuses_clock_custody_and_ownership_without_reviewers():
    s=legacy_fixture();s.a.update(schema='ATLAS_PERSONAL_NATIVE_ACCEPTANCE_V1',profile=PROFILE,gates=dict.fromkeys(PERSONAL_GATES,'OPERATOR_AND_TECHNICAL_CHECKS_PASSED'))
    personal=PersonalNativeEnrollment(**s.deps)
    with personal.admitted(s.g):pass
    with pytest.raises(ValueError), s.adapter.admitted(s.g):pass
    s.c['status']='UNKNOWN'
    with pytest.raises(ValueError), personal.admitted(s.g):pass


def test_default_factories_do_not_initialize_or_start():
    with pytest.raises(ValueError):compose_personal_qd()
    with pytest.raises(ValueError):compose_personal_unified()
    with pytest.raises(ValueError):AutonomousNativeEnrollment()


def test_mutated_proof_cannot_redefine_its_own_expected_authority():
    s=installed()
    with pytest.raises(ValueError),s.i.lease({'session':'synthetic'}) as lease:
        lease.snapshot['gates']['P-B1']='FORGED'
        assert not lease.check(lease.snapshot)


def test_local_native_acceptance_uses_operator_activation_not_old_gate_labels():
    from app.services.personal_paper_runtime import PersonalNativeAcceptance
    s=legacy_fixture();s.g['expires_at']=1099
    i=installed(accounts={'QUALITY_DIPS':digest(s.e)})
    port=PersonalNativeAcceptance(i.i)
    with port.lease({'scope':'LOCAL_ENROLLED','enrollment':s.e,'grant':s.g},1000) as lease:
        assert lease.snapshot['profile']==PROFILE and set(lease.snapshot['gates'])==set(PERSONAL_GATES)
        assert lease.check(copy.deepcopy(lease.snapshot),1001)
        lease.snapshot['expires_at']=999999
        assert not lease.check(lease.snapshot,1001)


def test_qd_factory_constructs_existing_runtime_without_start_or_native_access(monkeypatch):
    from app.services.personal_paper_runtime import PersonalFinancialBinding
    from app.services.quality_dips_autonomous_integration import (
        AutonomousNativePublication,
    )
    from test_personal_paper_inception_memory import system
    s=system('QUALITY_DIPS')
    try:
        e=s.n;pin={'schema':'QD_AUTO_OP_PIN_V1'}
        store=SimpleNamespace(trust=SimpleNamespace(current=lambda:pin),enrollment=e)
        publication=AutonomousNativePublication.__new__(AutonomousNativePublication);publication.store=store
        engine=SimpleNamespace(publication=publication,ledger=SimpleNamespace(manifest=s.m))
        reader_e={'schema':'QD_AUTO_OP_READ_ENROLLMENT_V1','account_id':e['account_id'],'epoch':e['epoch']}
        reader=SimpleNamespace(enrollment=reader_e)
        reports=SimpleNamespace(store=store,archive=SimpleNamespace(trust=SimpleNamespace(current=lambda:{'schema':'FS3_REPORT_PIN_V1'})))
        runtime_e={'schema':'QD_AUTO_LOCAL_RUNTIME_V3','profile':'AUTONOMOUS_PAPER_ONLY_V1','scope':'LOCAL_ENROLLED','reader_enrollment':reader_e,'process_identity':{'pid':1,'created':1,'image':'D:\\synthetic.exe'},'writer_roster':['decision','source','projection','report','coordination'],'disposable_root':None}
        deps={'enrollment':runtime_e,'engine':engine,'reader':reader,'reports':reports,'authority':object(),'ownership':object(),'clock':object(),'custody':object()}
        native_deps={k:object() for k in ('custody','clock','ownership','sessions')};native_reader=SimpleNamespace(enrollment=e)
        ports={'runtime':deps,'native':native_deps,'store':store,'reader':native_reader}
        i=installed(accounts={'QUALITY_DIPS':digest(e)},ports=ports)
        # Native compatibility has a separately scoped future test. This test
        # exercises actual factory/runtime constructors with a mocked native port.
        monkeypatch.setattr(PersonalFinancialBinding,'components',lambda _:True)
        result=compose_personal_qd(policy=i.p,enrollment=e,runtime_dependencies=deps,native_dependencies=native_deps,store=store,native_reader=native_reader,installation=i.i)
        assert result.grant is None and result.runtime.grant is None and result.runtime.halted
        assert engine.publication is result.financial and result.enrollment['execution_domain']=='PERSONAL_PAPER'
        with i.i.lease(result.installation_request()) as lease:assert lease.check_components(result.installation_components())
        result.admission.acceptance=object()
        with pytest.raises(ValueError,match='SUBSTITUTION'),result._action(readonly=True):pytest.fail('substituted admission')
        assert result.runtime.halted and not result.failed
    finally:s.ledger.db.close()


@pytest.mark.parametrize('root',[None,'C:\\AtlasCustody\\PersonalPaper\\x','D:\\AtlasCustody\\PersonalPaper\\..\\x','D:\\AtlasCustody\\PersonalPaper\\x:stream','D:\\AtlasCustody\\PersonalPaper\\%ROOT%','D:/AtlasCustody/PersonalPaper/x'])
def test_native_approval_reader_refuses_bad_config_without_io(root):
    from scripts.observation_runtime.personal_paper_activation import (
        NativePersonalActivationReader,
    )
    with pytest.raises(ValueError):NativePersonalActivationReader(root=root,native_root=[1,2,0],binding={'id':[1,3,0],'sha256':'a'*64})


def test_native_approval_reader_construction_has_no_store_initialization():
    from scripts.observation_runtime.personal_paper_activation import (
        NativePersonalActivationReader,
    )
    r=NativePersonalActivationReader(root='D:\\AtlasCustody\\PersonalPaper\\SYNTHETIC-ONLY',native_root=[1,2,0],binding={'id':[1,3,0],'sha256':'a'*64})
    assert r.root.endswith('SYNTHETIC-ONLY') # read deliberately not called
