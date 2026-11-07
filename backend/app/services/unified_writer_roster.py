"""Exact selected-runtime roster verification, never process discovery or authority.

The enrolled observer reads retained native handles/current writer reservations.
Same-user NTFS cannot establish exclusion from arbitrary hostile same-user code.
No accepted observer/issuer is installed by this module.
"""
from contextlib import contextmanager

from app.investment.quality_dips_operational_contract import native_id
from app.services.paper_financial_replay import body, digest, strict, text

ROLES = (
    'QD_DECISION','QD_SOURCE','QD_PROJECTION','QD_REPORT','QD_COORDINATION','QD_RANKING_PUBLICATION',
    'PERP_SOURCE','PERP_PROJECTION','PERP_REPORT','PERP_ORDERS','PERP_FUNDING','PERP_MARK','PERP_MARKET_PUBLICATION',
    'GLOBAL_CUSTODY','SESSION_RESERVATION',
)
EXCLUSIONS = ('LEGACY_INVESTMENT','LEGACY_PREDICTION','LEGACY_MANUAL_PERP','LEGACY_JOURNAL','RESEARCH_MUTATION',
              'INCEPTION_PUBLISHER','RECOVERY_WRITER','LEGACY_SCANNER_FINANCIAL_MIRROR')


def validate_roster(value):
    r=strict(body(value))
    if (set(r)!= {'schema','session_id','account_binding','writer_binding','roles','exclusions'}
            or r['schema']!='ATLAS_UNIFIED_WRITER_RESOURCES_V1' or set(r['roles'])!=set(ROLES)
            or set(r['exclusions'])!=set(EXCLUSIONS)):
        raise ValueError('COMPLETE_SELECTED_WRITER_AND_EXCLUSION_ROSTER_REQUIRED')
    for k in ('session_id','account_binding','writer_binding'):text(r[k])
    by_pid={}
    for row in r['roles'].values():
        if set(row)!= {'writer_id','process','resource'}: raise ValueError('EXACT_WRITER_RESOURCE_REQUIRED')
        text(row['writer_id']);native_id(row['resource'])
        p=row['process']
        if (set(p)!= {'pid','created','image'} or type(p['pid']) is not int or p['pid']<=0
                or type(p['created']) is not int or p['created']<=0 or type(p['image']) is not str or not p['image']):
            raise ValueError('EXACT_NATIVE_PROCESS_REQUIRED')
        if p['pid'] in by_pid and by_pid[p['pid']]!=p: raise ValueError('CONFLICTING_PROCESS_INCARNATION')
        by_pid[p['pid']]=p
    if len({row['writer_id'] for row in r['roles'].values()})!=len(ROLES):
        raise ValueError('DUPLICATE_WRITER_IDENTITY')
    for receipt in r['exclusions'].values():text(receipt)
    return r


class UnifiedWriterRoster:
    def __init__(self, *, enrollment, writers, observer, authority, clock):
        if any(x is None for x in (writers,observer,authority,clock)):
            raise ValueError('ACCEPTED_ROSTER_OBSERVER_AND_AUTHORITY_REQUIRED')
        self.enrollment=validate_roster(enrollment)
        self._enrollment=body(self.enrollment)
        self.writers,self.observer,self.authority,self.clock=dict(writers),observer,authority,clock
        self.components={'writers':dict(writers),'observer':observer,'clock':clock,'authority':authority}
        if authority.verify_enrollment(self.enrollment,self.components) is not True:
            raise ValueError('INDEPENDENT_ROSTER_ENROLLMENT_REQUIRED')

    def _read(self,grant,writers):
        e=self.enrollment;now=self.clock()
        if (type(now) is not int or now < 0 or body(e)!=self._enrollment or set(writers)!= {'QUALITY_DIPS','HYPERLIQUID'} or writers!=self.writers
                or any(writers[k] is not self.components['writers'][k] for k in writers)
                or any(getattr(self,k) is not self.components[k] for k in ('observer','clock','authority'))
                or digest({k:digest(w.manifest) for k,w in writers.items()})!=e['account_binding']
                or grant.get('session_id')!=e['session_id']
                or self.authority.verify_enrollment(e,self.components) is not True):
            raise ValueError('ROSTER_COMPONENT_OR_SESSION_CHANGED')
        value=strict(body(self.observer.read(e)))
        if (set(value)!= {'schema','observed_at','roles','unknown_writers','active_operations','unknown_operations'}
                or value['schema']!='ATLAS_UNIFIED_WRITER_OBSERVATION_V1'
                or type(value['observed_at']) is not int or not 0<=now-value['observed_at']<=2
                or value['roles']!=e['roles'] or value['unknown_writers']!=[]
                or value['unknown_operations'] is not False or set(value['active_operations'])!=set(ROLES)
                or any(type(x) is not int or x<0 for x in value['active_operations'].values())
                or self.authority.verify_observation(e,value,now) is not True):
            raise ValueError('NATIVE_WRITER_RESOURCE_OR_QUIESCENCE_UNVERIFIED')
        end = self.clock()
        if (type(end) is not int or not 0 <= end-now <= 1
                or not 0 <= end-value['observed_at'] <= 2
                or body(e) != self._enrollment):
            raise ValueError('WRITER_OBSERVATION_CLOCK_OR_FRESHNESS_CHANGED')
        return value

    @contextmanager
    def lease(self,grant,writers,now):
        self._read(grant,writers)
        owner=self
        class Lease:
            def check(self):
                owner._read(grant,writers)
                return True
        yield Lease()

    def drain(self,grant,writers,now):
        first=self._read(grant,writers)
        if any(first['active_operations'].values()):return False
        second=self._read(grant,writers)
        return first==second and self.authority.verify_drain(self.enrollment,second,now) is True

    def owned_roster(self,grant,writers,now):
        self._read(grant,writers)
        by_pid={row['process']['pid']:row['process'] for row in self.enrollment['roles'].values()}
        return {'schema':'ATLAS_UNIFIED_OWNED_ROSTER_V1','session_id':self.enrollment['session_id'],
                'writer_binding':self.enrollment['writer_binding'],'account_binding':self.enrollment['account_binding'],
                'processes':[by_pid[k] for k in sorted(by_pid)]}
