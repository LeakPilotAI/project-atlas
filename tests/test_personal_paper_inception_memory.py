"""Actual once-only publisher protocol with synthetic in-memory native-file port."""
import copy
from contextlib import contextmanager
from types import SimpleNamespace

import pytest
from app.services.paper_financial_replay import digest, initial_state
from app.services.personal_publication_custody import PersonalPublicationCustody
from test_paper_epoch_fixture import manifest as qd_manifest
from test_perp_financial_v2 import manifest as perp_manifest
from test_personal_paper_runtime import policy
from test_personal_session_reservation_integrity import Memory
from test_quality_dips_autonomous_enrollment import fixture

from scripts.observation_runtime.personal_paper_inception import (
    PersonalInceptionBootstrap,
    PersonalInceptionPublisher,
)
from scripts.observation_runtime.quality_dips_one_time_publisher import (
    PublicationUnknown,
)


def system(lane,fail=None):
    p=policy();n=copy.deepcopy(fixture().e)
    if lane=='QUALITY_DIPS':
        m=qd_manifest('SYNTHETIC-LOCAL-QD','QUALITY_DIPS');m.update(schema='PAPER_EPOCH_AUTONOMOUS_QD_V1',release=n['release_digest'],provenance='ACCEPTED_AUTONOMOUS_PAPER_PARAMETERS_V1',cost_policy='SIDE_NOTIONAL_FEE_SLIPPAGE_V1',autonomous_policy={'schema':'QD_AUTO_RISK_PARTIAL_THESIS_V1','quote_age_seconds':5,'max_spread_bps':'50','participation':'0.5','quantity_step':'0.001','partial_fraction':'0.4','max_session_seconds':3600});n['policy_digest']=digest(m['autonomous_policy'])
    else:
        from app.services.perp_operational_contract import WRITERS
        n['schema']='PERP_AUTO_NATIVE_ENROLLMENT_V1'
        for root in n['resources'].values():root['schema']='PERP_AUTO_NATIVE_ROOT_V1'
        n['writers']={r:copy.deepcopy(next(iter(n['writers'].values()))) for r in WRITERS}
        m=perp_manifest();m.update(schema='PAPER_EPOCH_PERP_OPERATIONAL_V1',release=n['release_digest'],provenance='ACCEPTED_PERP_PAPER_PARAMETERS_V1');n['policy_digest']=digest(m['perp_policy'])
    n.update(epoch=m['epoch'],inception_digest=digest(m))
    scope={'schema':'FS3_QD_REPORT_SCOPE_V2' if lane=='QUALITY_DIPS' else 'FS3_PERP_REPORT_SCOPE_V3','account_id':n['account_id'],'epoch':n['epoch'],'policy_digest':digest(m),'timezone':m['timezone'],'session_reporting_policy':'ACKNOWLEDGED_EVENT_TIME_INCLUSIVE_CUT_V1'}
    if lane=='HYPERLIQUID':scope['funding_reporting_policy']='POSTED_CASH_AND_SETTLEMENT_ACCRUAL_V1'
    e={'profile':'PERSONAL_PAPER_ONLY_V1','personal_policy':p,'lane':lane,'native_enrollment':n,'parameters':m,'report_scope':scope};now=[m['opened_at']+1]
    ledger=Memory();PersonalPublicationCustody.install_schema(ledger.db);ledger.db.commit();custody=PersonalPublicationCustody(ledger)
    allowed=[True];files=SimpleNamespace(values={})
    @contextmanager
    def issuer_lease(scope,stamp):yield SimpleNamespace(check=lambda candidate,t:allowed[0] and candidate==scope)
    issuer=SimpleNamespace(lease=issuer_lease)
    @contextmanager
    def owner_lease(context,stamp):yield SimpleNamespace(check=lambda candidate,t:candidate==context)
    owner=SimpleNamespace(lease=owner_lease)
    @contextmanager
    def open_files(_e):
        if files.values:raise ValueError('NO_ADOPTION')
        def write(role,name,doc):
            if (role,name) in files.values:raise ValueError('NO_REPLACE')
            files.values[role,name]=copy.deepcopy(doc)
            if fail==name:raise OSError('INTERRUPTED_NATIVE_PUBLICATION')
            return {'id':[1,len(files.values),0],'sha256':digest(doc)}
        yield SimpleNamespace(write=write,verify=lambda:None)
    file_port=SimpleNamespace(open=open_files)
    def verify(_e,current):
        if fail=='readback':return False
        state=initial_state(m)
        return (state['cash']=='1000' and state['positions']=={} and current['state_digest']==digest(state)
                and files.values['source','inception.json']['parameters']==m and files.values['report','0001-report.json']['report']['source']['revision']==0)
    b=PersonalInceptionBootstrap(enrollment=e,publication=custody,issuer=issuer,clock=lambda:now[0],readback=SimpleNamespace(verify=verify))
    observer=lambda:{'schema':'QD_OP_PROCESS_ID_V1','pid':123,'creation_filetime':456,'image':'D:\\synthetic-owned.exe'}
    pub=PersonalInceptionPublisher(bootstrap=b,custody=custody,ownership=owner,observer=observer,files=file_port)
    return SimpleNamespace(**locals())


@pytest.mark.parametrize('lane',['QUALITY_DIPS','HYPERLIQUID'])
def test_actual_personal_inception_recipe_is_once_only_and_exactly_1000(lane):
    s=system(lane)
    try:
        ready=s.pub.publish();assert not ready['financial_startup_authorized']
        state=initial_state(s.m);assert state['cash']=='1000' and state['positions']=={}
        assert all(state[k] in ('0','0.0') for k in ('gross','costs','net'))
        assert ready['current']['source']['entries']==[] and ready['current']['projection']['required']==0
        assert ('projection','projection.json') not in s.files.values
        before=copy.deepcopy(s.files.values)
        with pytest.raises(ValueError):s.pub.publish()
        assert before==s.files.values
    finally:s.ledger.db.close()


@pytest.mark.parametrize('failure',['inception.json','scope.json','0001-report.json','readback'])
def test_partial_or_unacknowledged_publication_is_unknown_never_replayed(failure):
    s=system('QUALITY_DIPS',failure)
    try:
        with pytest.raises(PublicationUnknown):s.pub.publish()
        assert s.custody.row(s.b.scope()['operation_id'])[2]=='UNKNOWN'
        before=copy.deepcopy(s.files.values)
        with pytest.raises(ValueError):s.pub.publish()
        assert s.files.values==before
    finally:s.ledger.db.close()


@pytest.mark.parametrize('lane',['QUALITY_DIPS','HYPERLIQUID'])
@pytest.mark.parametrize('damage',['foreign-enrollment','cash','fees-or-risk','account-policy','risk-baseline'])
def test_invalid_personal_inception_refuses_before_reservation_or_file_writes(lane,damage):
    from scripts.observation_runtime.personal_paper_inception import (
        validate_personal_inception,
    )
    s=system(lane)
    try:
        e=copy.deepcopy(s.e)
        if damage=='foreign-enrollment':e['native_enrollment']['schema']='FS2_TEST_PIN_V1'
        elif damage=='cash':e['parameters']['opening_cash']='1001'
        elif damage=='account-policy':e['native_enrollment']['policy_digest']='f'*64
        elif damage=='risk-baseline':e['parameters']['initial_net_r']='1';e['native_enrollment']['inception_digest']=digest(e['parameters'])
        elif lane=='QUALITY_DIPS':e['parameters']['fees_bps']='0';e['native_enrollment']['inception_digest']=digest(e['parameters'])
        else:
            e['parameters']['perp_policy']['risk_limit']='2'
            e['native_enrollment']['inception_digest']=digest(e['parameters']);e['native_enrollment']['policy_digest']=digest(e['parameters']['perp_policy'])
        with pytest.raises(ValueError):validate_personal_inception(e)
        assert not s.files.values and s.custody.row(s.b.scope()['operation_id']) is None
    finally:s.ledger.db.close()


@pytest.mark.parametrize('column',['commit_body','ack_body'])
def test_corrupt_receipt_schema_never_yields_acknowledged_inception(column):
    import json
    s=system('QUALITY_DIPS')
    try:
        s.pub.publish();op=s.b.scope()['operation_id']
        index=4 if column=='commit_body' else 5
        value=json.loads(s.custody.row(op)[index]);value['schema']='UNTRUSTED_TEST_RECEIPT'
        s.ledger.db.execute('UPDATE personal_publications SET '+column+'=? WHERE id=?',(json.dumps(value),op));s.ledger.db.commit()
        with pytest.raises(ValueError):s.b.verify_publication()
    finally:s.ledger.db.close()



def test_personal_once_only_publication_preserves_actual_v4_intent_identity():
    from app.services.quality_dips_autonomous_enrollment import publication_intent
    s=system('QUALITY_DIPS')
    try:
        with pytest.raises(ValueError):s.b.native_publication()
        s.pub.publish();expected=publication_intent(s.n);proof=s.b.native_publication()
        assert s.b.scope()['native_intent']==expected
        assert proof['operation_id']==expected['operation_id'] and proof['intent_digest']==digest(expected)
        assert proof['ack_id']==digest(s.custody.acknowledged(expected['operation_id'])[1])
    finally:s.ledger.db.close()
