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
