"""Versioned, existing-account USDC readback. No provisioning or writer grants.

Reuse the operational FS1 store, FS3 report audit and native coordination pins.
This is a source-only successor interface until separately installed/approved.
"""
from contextlib import contextmanager

from app.services.paper_financial_replay import body, digest, strict
from app.services.personal_current_pins import PersonalCurrentPins
from app.services.personal_native_coordination import PersonalNativeCoordination
from app.services.personal_publication_custody import PersonalPublicationCustody
from scripts.observation_runtime.personal_coordination_store import NativePersonalCoordinationImages
from scripts.observation_runtime.personal_local_authority import NativePersonalOperatorAuthority
from scripts.observation_runtime.personal_paper_inception import (
    PersonalInceptionBootstrap, validate_initial_current, validate_personal_inception,
)
from scripts.observation_runtime.personal_writer_ownership import NativePersonalWriterOwnership
from scripts.volume_inspector.operational_perp_store import (
    OperationalPerpReportArchive, OperationalPerpReportService, OperationalPerpStore,
)
from scripts.volume_inspector.financial_reporting import ProjectionTarget


class NativePersonalPerpReadAuthority:
    """READ_ONLY leases only; no reservation, ACK fabrication or schema repair."""

    def __init__(self, *, operator, ownership, source, reports):
        if (type(operator) is not NativePersonalOperatorAuthority
                or type(ownership) is not NativePersonalWriterOwnership
                or ownership.read_only is not True or ownership.authority is not operator
                or operator._lane != 'HYPERLIQUID'
                or type(source) is not PersonalCurrentPins
                or type(reports) is not PersonalCurrentPins
                or source.name == reports.name or source.ledger is not reports.ledger
                or type(source.ledger) is not PersonalNativeCoordination
                or type(source.ledger.images) is not NativePersonalCoordinationImages
                or ownership.ledger is not source.ledger
                or ownership.enrollment != operator.enrollment
                or digest(source.ledger.manifest) != operator.enrollment['inception_digest']):
            raise ValueError('PERP_CURRENT_EXACT_READONLY_NATIVE_PORTS_REQUIRED')
        self.operator, self.ownership = operator, ownership
        self.source, self.reports, self.clock = source, reports, operator.clock
        self.ledger = source.ledger
        self._ports = operator, ownership, source, reports, self.clock, self.ledger
        self._enrollment = body(operator.enrollment)

    def _capture(self):
        if (any(a is not b for a, b in zip(
                (self.operator, self.ownership, self.source, self.reports,
                 self.clock, self.ledger), self._ports, strict=True))
                or self.operator.clock is not self.clock
                or self.ownership.authority is not self.operator
                or self.ownership.read_only is not True
                or body(self.operator.enrollment) != self._enrollment
                or body(self.ownership.enrollment) != self._enrollment
                or self.source.ledger is not self.ledger
                or self.reports.ledger is not self.ledger
                or digest(self.ledger.manifest) != self.operator.enrollment['inception_digest']):
            raise ValueError('PERP_CURRENT_READ_COMPONENT_CHANGED')
        self.operator.activation('READ_ONLY')
        source, reports = self.source.current(), self.reports.current()
        e = self.operator.enrollment
        if (source.get('schema') != 'PERP_AUTO_OP_PIN_V1'
                or reports.get('schema') != 'PERP_AUTO_OP_REPORT_PIN_V1'
                or source.get('root') != e['resources']['source']['native_id']
                or reports.get('root') != e['resources']['report']['native_id']
                or source.get('epoch') != e['epoch']):
            raise ValueError('PERP_CURRENT_READ_RESOURCE_SUBSTITUTION')
        with self.ledger.connect(readonly=True) as db:
            self.ledger._load(db)
            if (db.execute('SELECT 1 FROM projections WHERE receipt IS NULL').fetchone()
                    or db.execute("SELECT 1 FROM personal_publications WHERE state!='ACKNOWLEDGED' OR state IS NULL").fetchone()
                    or db.execute("SELECT 1 FROM personal_sessions WHERE state!='ACKNOWLEDGED' OR state IS NULL").fetchone()):
                raise ValueError('PERP_CURRENT_PENDING_OR_UNKNOWN')
        return source, reports

    @contextmanager
    def lease(self, request, now):
        request = strict(body(request))
        e = self.operator.enrollment
        if (type(now) is not int or now != self.clock()
                or type(request) is not dict or request.get('enrollment') != e):
            raise ValueError('PERP_CURRENT_READ_SCOPE_OR_TIME')
        schema = request.get('schema')
        if (schema == 'PERP_AUTO_OP_ADMISSION_REQUEST_V1'
                and set(request) == {'schema', 'enrollment', 'current', 'command'}
                and request['command'] is None):
            admission, index = 'PERP_AUTO_OP_ADMISSION_V1', 0
        elif (schema == 'PERP_AUTO_OP_REPORT_REQUEST_V1'
                and set(request) == {'schema', 'enrollment', 'current', 'action'}
                and request['action'] == 'READ'):
            admission, index = 'PERP_AUTO_OP_REPORT_ADMISSION_V1', 1
        else:
            raise ValueError('PERP_CURRENT_NO_WRITER_OR_PUBLICATION_AUTHORITY')
        read = {'schema': 'PERP_AUTO_OP_READ_ENROLLMENT_V1',
                'account_id': e['account_id'], 'epoch': e['epoch'],
                **{r+'_root': e['resources'][r]['native_id']
                   for r in ('source', 'projection', 'report')}}
        ownership_request = {'schema': 'PERSONAL_NATIVE_READ_LEASE_V1',
                             'reader_enrollment': read}
        with (self.ownership.lease(ownership_request, now) as owned,
              self.ledger.read_view()):
            cut = self._capture()
            if request['current'] != cut[index]:
                raise ValueError('PERP_CURRENT_READ_STALE_PIN')
            snapshot = {'schema': admission, 'request_digest': digest(request),
                        'status': 'READ_ACCEPTED', 'reservation_id': 'read:'+digest(request),
                        'expires_at': now+5, 'revoked': False}
            sealed, owner = body(snapshot), self
            class Lease:
                def __init__(self): self.snapshot = strict(sealed)
                def check(self, candidate, stamp):
                    return (type(stamp) is int and now <= stamp <= now+5
                            and stamp == owner.clock()
                            and body(candidate) == sealed and body(self.snapshot) == sealed
                            and owned.check(owned.snapshot, stamp) is True
                            and owner._capture() == cut)
            lease = Lease()
            if not lease.check(snapshot, now):
                raise ValueError('PERP_CURRENT_READ_LEASE_REFUSED')
            yield lease
            if not lease.check(snapshot, self.clock()):
                raise ValueError('PERP_CURRENT_READ_LEASE_CHANGED')


class PersonalPerpRuntimeCurrent:
    """Existing FS1 replay plus independently audited FS3; never initial-only IO."""

    def __init__(self, *, bootstrap, source, reports, store, reporting, clock):
        if (type(bootstrap) is not PersonalInceptionBootstrap
                or type(bootstrap.publication) is not PersonalPublicationCustody
                or type(source) is not PersonalCurrentPins
                or type(reports) is not PersonalCurrentPins
                or type(store) is not OperationalPerpStore
                or type(store.projection) is not ProjectionTarget
                or type(reporting) is not OperationalPerpReportService
                or type(reporting.archive) is not OperationalPerpReportArchive
                or type(store.authority) is not NativePersonalPerpReadAuthority
                or reporting.archive.authority is not store.authority
                or store.authority.source is not source
                or store.authority.reports is not reports
                or store.authority.clock is not clock
                or store.trust is not source or reporting.store is not store
                or reporting.archive.trust is not reports
                or reporting.archive.clock is not clock
                or source.ledger is not reports.ledger
                or source.ledger is not bootstrap.publication.ledger):
            raise ValueError('PERP_CURRENT_EXACT_NATIVE_READERS_REQUIRED')
        lane, enrollment, manifest = validate_personal_inception(bootstrap.enrollment)
        if (lane != 'HYPERLIQUID' or store.enrollment != enrollment
                or reporting.archive.enrollment != enrollment
                or body(source.ledger.manifest) != body(manifest)):
            raise ValueError('PERP_CURRENT_ACCOUNT_BINDING_REQUIRED')
        self.bootstrap, self.source, self.reports = bootstrap, source, reports
        self.store, self.reporting, self.clock = store, reporting, clock
        self._ports = bootstrap, source, reports, store, reporting, clock
        self._authority, self._archive, self._ledger = store.authority, reporting.archive, source.ledger
        self._projection = store.projection
        self._publication = bootstrap.publication
        self._e, self._m = body(enrollment), body(manifest)
        self._inception = body(bootstrap.enrollment)
        self._water = None

    def capture(self):
        if (any(a is not b for a, b in zip(
                (self.bootstrap, self.source, self.reports, self.store,
                 self.reporting, self.clock), self._ports, strict=True))
                or body(self.bootstrap.enrollment) != self._inception
                or body(self.store.enrollment) != self._e
                or self.store.trust is not self.source
                or self.reporting.store is not self.store
                or self.reporting.archive is not self._archive
                or self.store.authority is not self._authority
                or self.store.projection is not self._projection
                or self._archive.authority is not self._authority
                or self._archive.clock is not self.clock
                or self._authority.clock is not self.clock
                or body(self._archive.enrollment) != self._e
                or self.reporting.archive.trust is not self.reports
                or self.source.ledger is not self._ledger
                or self.reports.ledger is not self._ledger
                or self.bootstrap.publication.ledger is not self._ledger):
            raise ValueError('PERP_CURRENT_COMPONENT_CHANGED')
        if self.bootstrap.publication is not self._publication:
            raise ValueError('PERP_CURRENT_GENESIS_PUBLICATION_CHANGED')
        start = self.clock()
        if type(start) is not int:
            raise ValueError('PERP_CURRENT_INTEGER_UTC_REQUIRED')
        with self.source.ledger.read_view():
            original, ack = self.bootstrap.publication.acknowledged(
                self.bootstrap.scope()['operation_id'])
            validate_initial_current(self.bootstrap.enrollment, original)
            source, reports = self.source.current(), self.reports.current()
            sg, rg = self.source.known[0], self.reports.known[0]
            e = strict(self._e)
            if (type(sg) is not int or type(rg) is not int
                    or source.get('schema') != 'PERP_AUTO_OP_PIN_V1'
                    or reports.get('schema') != 'PERP_AUTO_OP_REPORT_PIN_V1'
                    or source.get('root') != e['resources']['source']['native_id']
                    or reports.get('root') != e['resources']['report']['native_id']
                    or source.get('epoch') != e['epoch']
                    or type(source.get('entries')) is not list
                    or type(reports.get('reports')) is not list
                    or not 0 <= len(source['entries']) <= 128
                    or not 1 <= len(reports['reports']) <= 128
                    or sg != len(source['entries']) or rg != len(reports['reports'])-1
                    or {k:v for k,v in source.items() if k!='entries'} !=
                       {k:v for k,v in original['source'].items() if k!='entries'}
                    or {k:v for k,v in reports.items() if k!='reports'} !=
                       {k:v for k,v in original['reports'].items() if k!='reports'}
                    or reports['reports'][:1] != original['reports']['reports']):
                raise ValueError('PERP_CURRENT_PREFIX_OR_GENERATION_CONFLICT')
            financial = self.store.verified_cut()
            documents = self.reporting.history()
            if (financial['manifest'] != strict(self._m)
                    or financial['root'] != source['root']
                    or financial['pin_schema'] != source['schema']
                    or len(documents) != len(reports['reports'])
                    or self.source.current() != source or self.reports.current() != reports
                    or self.bootstrap.publication.acknowledged(
                        self.bootstrap.scope()['operation_id']) != (original, ack)):
                raise ValueError('PERP_CURRENT_FINANCIAL_OR_REPORT_CONFLICT')
            if (not documents or type(documents[-1]['report']['source']['revision']) is not int
                    or documents[-1]['report']['source']['revision'] != sg):
                raise ValueError('PERP_CURRENT_REPORT_SOURCE_NOT_RECONCILED')
            end = self.clock()
            if type(end) is not int or not start <= end <= start+5:
                raise ValueError('PERP_CURRENT_CAPTURE_EXPIRED')
            result = {'schema':'PERSONAL_PERP_CURRENT_READBACK_V1',
                'enrollment_digest':digest(e),'manifest_digest':digest(strict(self._m)),
                'source':source,'reports':reports,'source_revision':sg,
                'report_revision':rg,'state':financial['state'],
                'financial_head':financial['head'],'genesis_ack_digest':digest(ack),
                'observed_at':end,'financial_write_authority':False}
            mark = (sg, rg, digest({k:v for k,v in result.items() if k!='observed_at'}))
            if self._water and (sg < self._water[0] or rg < self._water[1]
                    or (sg,rg)==self._water[:2] and mark[2]!=self._water[2]):
                raise ValueError('PERP_CURRENT_OBSERVED_ROLLBACK')
            self._water = mark
            return strict(body(result))
