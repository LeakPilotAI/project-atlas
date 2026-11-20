"""Exact contracts with explicitly synthetic enrollment and observations."""
import copy
from types import SimpleNamespace

import pytest
from app.services.paper_financial_replay import digest
from app.services.unified_writer_roster import EXCLUSIONS, ROLES, UnifiedWriterRoster


def fixture():
    writers={k:SimpleNamespace(manifest={'epoch':k}) for k in ('QUALITY_DIPS','HYPERLIQUID')}
    process={'pid':17,'created':1234,'image':'D:/EXPLICIT-SYNTHETIC.exe'}
    e={'schema':'ATLAS_UNIFIED_WRITER_RESOURCES_V1','session_id':'synthetic-session',
        'account_binding':digest({k:digest(w.manifest) for k,w in writers.items()}),'writer_binding':'synthetic-accepted-roster',
        'roles':{k:{'writer_id':k,'process':process,'resource':[1,2,3]} for k in ROLES},
        'exclusions':{k:'EXPLICIT_SYNTHETIC_EXCLUSION' for k in EXCLUSIONS}}
    value={'schema':'ATLAS_UNIFIED_WRITER_OBSERVATION_V1','observed_at':100,'roles':copy.deepcopy(e['roles']),
        'unknown_writers':[],'active_operations':dict.fromkeys(ROLES,0),'unknown_operations':False}
    a=SimpleNamespace(verify_enrollment=lambda *args:True,verify_observation=lambda *args:True,verify_drain=lambda *args:True)
    observer=SimpleNamespace(read=lambda expected:copy.deepcopy(value))
    roster=UnifiedWriterRoster(enrollment=e,writers=writers,observer=observer,authority=a,clock=lambda:100)
    return SimpleNamespace(**locals())


def test_complete_role_resource_roster_and_explicit_zero_drain():
    s=fixture();grant={'session_id':'synthetic-session'}
    with s.roster.lease(grant,s.writers,100) as lease:assert lease.check()
    assert s.roster.drain(grant,s.writers,100)
    close=s.roster.owned_roster(grant,s.writers,100)
    assert len(close['processes'])==1 and close['writer_binding']==s.e['writer_binding']
    s.value['active_operations']['PERP_FUNDING']=1
    assert not s.roster.drain(grant,s.writers,100)


@pytest.mark.parametrize('damage',['missing','unknown','pending-unknown','stale','birth','resource','writer','authority'])
def test_missing_foreign_and_unverified_native_roster_refuses(damage):
    s=fixture()
    if damage=='missing':s.value['roles'].pop('PERP_MARK')
    elif damage=='unknown':s.value['unknown_writers']=['foreign']
    elif damage=='pending-unknown':s.value['unknown_operations']=True
    elif damage=='stale':s.value['observed_at']=90
    elif damage=='birth':s.value['roles']['QD_SOURCE']['process']['created']=999
    elif damage=='resource':s.value['roles']['PERP_REPORT']['resource']=[9,9,9]
    elif damage=='writer':s.value['roles']['GLOBAL_CUSTODY']['writer_id']='foreign'
    else:s.a.verify_observation=lambda *args:False
    with pytest.raises(ValueError):s.roster.owned_roster({'session_id':'synthetic-session'},s.writers,100)


def test_enrollment_requires_every_role_and_exclusion_receipt():
    s=fixture();s.e['roles'].pop('SESSION_RESERVATION')
    with pytest.raises(ValueError):UnifiedWriterRoster(enrollment=s.e,writers=s.writers,observer=s.observer,authority=s.a,clock=lambda:100)


@pytest.mark.parametrize('finish', [103, 99, 100.0])
def test_roster_observation_must_still_be_fresh_when_verification_finishes(finish):
    s = fixture()
    now = [100]
    def verify(*args):
        now[0] = finish
        return True
    s.a.verify_observation = verify
    roster = UnifiedWriterRoster(enrollment=s.e, writers=s.writers, observer=s.observer,
                                 authority=s.a, clock=lambda: now[0])
    with pytest.raises(ValueError):
        roster.owned_roster({'session_id': 'synthetic-session'}, s.writers, 100)


@pytest.mark.parametrize('damage',[
    'unknown_writer','unknown_operation','process_incarnation','resource_identity',
    'read_authority','enrollment_authority','writer_object','clock_identity',
    'observation_stale',
])
def test_successful_writer_lease_exit_must_revalidate_native_roster(damage):
    """An ownership change after entry must not return cleanly to the caller."""
    s=fixture()
    with pytest.raises(ValueError):
        with s.roster.lease({'session_id':'synthetic-session'},s.writers,100) as lease:
            assert lease is not None
            if damage=='unknown_writer':
                s.value['unknown_writers'].append('SYNTHETIC_UNOWNED_PROCESS')
            elif damage=='unknown_operation':
                s.value['unknown_operations']=True
            elif damage=='process_incarnation':
                s.value['roles']['QD_PROJECTION']['process']['created']=5555
            elif damage=='resource_identity':
                s.value['roles']['PERP_SOURCE']['resource']=[9,8,7]
            elif damage=='read_authority':
                s.a.verify_observation=lambda *_:False
            elif damage=='enrollment_authority':
                s.a.verify_enrollment=lambda *_:False
            elif damage=='writer_object':
                s.writers['QUALITY_DIPS']=SimpleNamespace(manifest={'epoch':'NEW'})
            elif damage=='clock_identity':
                s.roster.clock=lambda:100
            else:
                s.value['observed_at']=90


def test_successful_writer_lease_rechecks_read_observer_on_exit():
    s=fixture()
    count=[0]
    def counted_read(expected):
        count[0]+=1
        return copy.deepcopy(s.value)
    s.observer.read=counted_read
    with s.roster.lease({'session_id':'synthetic-session'},s.writers,100):
        assert count[0]==1
    assert count[0]==2


def test_failed_writer_lease_body_retains_original_unknown_error():
    s=fixture()
    with pytest.raises(RuntimeError,match='SYNTHETIC_FINANCIAL_EFFECT_UNKNOWN'):
        with s.roster.lease({'session_id':'synthetic-session'},s.writers,100):
            s.value['unknown_operations']=True
            raise RuntimeError('SYNTHETIC_FINANCIAL_EFFECT_UNKNOWN')


def test_writer_lease_failure_without_explicit_check_is_not_success():
    s=fixture()
    with pytest.raises(ValueError,match='NATIVE_WRITER_RESOURCE_OR_QUIESCENCE_UNVERIFIED'):
        with s.roster.lease({'session_id':'synthetic-session'},s.writers,100):
            # Deliberately skip lease.check(). The outer context must check.
            s.value['unknown_writers']=['UNOWNED_AFTER_ENTRY']
