"""Read-only personal V3/V4 custody over installed pins and native readback.

No installer, reservation, writer, recovery or default authority. Same-user pins
provide local continuity only. Actual read authority and ownership leases remain
mandatory on the existing readers and runtime; this port cannot replace them.
"""
from contextlib import contextmanager

from app.services.paper_financial_replay import body, digest, initial_state, strict
from app.services.quality_dips_autonomous_enrollment import publication_intent

from scripts.observation_runtime.personal_paper_inception import (
    validate_initial_current,
    validate_personal_inception,
)


class PersonalNativeReadAuthority:
    """Existing selected-reader lease over acknowledged local pins and ownership.

    The selected reader still performs native replay, projection and FS3 audit.
    This lease supplies no financial command permission or independent custody.
    """
    def __init__(self, *, bootstrap=None, source=None, reports=None, ownership=None, enrollment=None):
        from app.services.personal_current_pins import PersonalCurrentPins

        from scripts.observation_runtime.personal_writer_ownership import (
            NativePersonalWriterOwnership,
        )

        if (bootstrap is None or type(source) is not PersonalCurrentPins
                or type(reports) is not PersonalCurrentPins
                or type(ownership) is not NativePersonalWriterOwnership or type(enrollment) is not dict):
            raise ValueError('PERSONAL_READ_NATIVE_DEPENDENCIES_REQUIRED')
        lane, native, manifest = validate_personal_inception(bootstrap.enrollment)
        if (lane != 'QUALITY_DIPS' or body(ownership.enrollment) != body(native)
                or source.ledger is not reports.ledger or ownership.ledger is not source.ledger
                or bootstrap.publication.ledger is not source.ledger or source.name == reports.name):
            raise ValueError('PERSONAL_READ_COMPONENT_BINDING')
        self.bootstrap, self.source, self.reports, self.ownership = bootstrap, source, reports, ownership
        self.enrollment = strict(body(enrollment))
        self.clock = ownership.authority.clock
        self._ports = bootstrap, source, reports, ownership, self.clock
        self._enrollment, self._native, self._manifest = body(enrollment), body(native), body(manifest)
        self._bootstrap = body(bootstrap.enrollment)
        self._water = None
        self._request = {'schema': 'PERSONAL_NATIVE_READ_LEASE_V1', 'reader_enrollment': self.enrollment}
        ownership._context(self._request)  # Scope validation only; no handle operation.
        if (enrollment.get('manifest_digest') != digest(manifest)
                or enrollment.get('policy_digest') != native['policy_digest']):
            raise ValueError('PERSONAL_READ_MANIFEST_SCOPE')

    def _capture(self, now):
        if (any(a is not b for a, b in zip(
                (self.bootstrap, self.source, self.reports, self.ownership, self.clock), self._ports, strict=True))
                or body(self.enrollment) != self._enrollment
                or body(self.bootstrap.enrollment) != self._bootstrap
                or body(self.ownership.enrollment) != self._native
                or type(now) is not int or now != self.clock()):
            raise ValueError('PERSONAL_READ_CONTEXT_CHANGED')
        original, _ack = self.bootstrap.publication.acknowledged(self.bootstrap.scope()['operation_id'])
        validate_initial_current(self.bootstrap.enrollment, original)
        source, reports = self.source.current(), self.reports.current()
        sg, rg = self.source.known[0], self.reports.known[0]
        if (source.get('schema') != 'QD_AUTO_OP_PIN_V1' or reports.get('schema') != 'FS3_REPORT_PIN_V1'
                or type(source.get('entries')) is not list or type(reports.get('reports')) is not list
                or not 0 <= len(source['entries']) <= 128 or not 1 <= len(reports['reports']) <= 128
                or sg != len(source['entries']) or rg != len(reports['reports']) - 1
                or {k: v for k, v in source.items() if k != 'entries'}
                != {k: v for k, v in original['source'].items() if k != 'entries'}
                or {k: v for k, v in reports.items() if k != 'reports'}
                != {k: v for k, v in original['reports'].items() if k != 'reports'}
                or reports['reports'][:1] != original['reports']['reports']
                or self.enrollment.get('inception') != source['inception']):
            raise ValueError('PERSONAL_READ_CURRENT_PREFIX_OR_REVISION')
        with self.source.ledger.connect(readonly=True) as db:
            self.source.ledger._load(db)
            if (db.execute('SELECT 1 FROM projections WHERE receipt IS NULL').fetchone()
                    or db.execute("SELECT 1 FROM personal_publications WHERE state!='ACKNOWLEDGED' OR state IS NULL").fetchone()
                    or db.execute("SELECT 1 FROM personal_sessions WHERE state!='ACKNOWLEDGED' OR state IS NULL").fetchone()):
                raise ValueError('PERSONAL_READ_PENDING_OR_UNKNOWN')
        fingerprint = digest([source, reports])
        if self._water and (sg < self._water[0] or rg < self._water[1]
                or (sg, rg) == self._water[:2] and fingerprint != self._water[2]):
            raise ValueError('PERSONAL_READ_OBSERVED_ROLLBACK')
        self._water = sg, rg, fingerprint
        return source, reports, sg, rg

    @contextmanager
    def lease(self, enrollment, now):
        if body(enrollment) != self._enrollment:
            raise ValueError('PERSONAL_READ_FOREIGN_ENROLLMENT')
        with self.ownership.lease(self._request, now) as owned:
            cut = self._capture(now)
            source, reports, sg, rg = cut
            snapshot = {'schema': 'QD_READ_CURRENT_V1', 'enrollment_digest': digest(enrollment),
                        'observed_at': now, 'expires_at': now + 5, 'generation': 1 + sg + rg,
                        'source': source, 'reports': reports, 'high_water': sg,
                        'acknowledged_revision': sg, 'status': 'ACKNOWLEDGED'}
            sealed, owner = body(snapshot), self

            class Lease:
                def __init__(self): self.snapshot = strict(sealed)
                def check(self, candidate, stamp):
                    return (type(stamp) is int and now <= stamp <= now + 5
                            and body(candidate) == sealed and body(self.snapshot) == sealed
                            and owned.check(owned.snapshot, stamp) is True and owner._capture(stamp) == cut)

            lease = Lease()
            yield lease
            if not lease.check(snapshot, self.clock()):
                raise ValueError('PERSONAL_READ_LEASE_CHANGED')


class PersonalRuntimeCurrent:
    def __init__(self, *, bootstrap=None, source=None, reports=None, reader=None,
                 native_reader=None, clock=None):
        if any(x is None for x in (bootstrap, source, reports, reader, native_reader, clock)):
            raise ValueError('PERSONAL_CURRENT_INSTALLED_PORTS_REQUIRED')
        lane, e, m = validate_personal_inception(bootstrap.enrollment)
        if lane != 'QUALITY_DIPS' or body(native_reader.enrollment) != body(e):
            raise ValueError('PERSONAL_CURRENT_QD_ENROLLMENT_REQUIRED')
        if (source.ledger is not reports.ledger or source.ledger is not bootstrap.publication.ledger
                or source.name == reports.name):
            raise ValueError('PERSONAL_CURRENT_COORDINATION_SCOPE')
        self.bootstrap, self.source, self.reports = bootstrap, source, reports
        self.reader, self.native_reader, self.clock = reader, native_reader, clock
        self._ports = (bootstrap, source, reports, reader, native_reader, clock)
        self._e, self._m = body(e), body(m)
        self._inception, self._scope = body(bootstrap.enrollment), body(bootstrap.scope())
        self._high_water = None

    def _pins(self):
        source, reports = self.source.current(), self.reports.current()
        sg, rg = self.source.known[0], self.reports.known[0]
        e = strict(self._e)
        if (source.get('schema') != 'QD_AUTO_OP_PIN_V1'
                or reports.get('schema') != 'FS3_REPORT_PIN_V1'
                or source.get('root') != e['resources']['source']['native_id']
                or reports.get('root') != e['resources']['report']['native_id']
                or source.get('epoch') != e['epoch']
                or type(source.get('entries')) is not list or type(reports.get('reports')) is not list
                or not 0 <= len(source['entries']) <= 128 or not 1 <= len(reports['reports']) <= 128
                or sg != len(source['entries']) or rg != len(reports['reports']) - 1):
            raise ValueError('PERSONAL_CURRENT_PIN_REVISION_OR_RESOURCE')
        return source, reports, sg, rg

    def _capture(self, now):
        if (any(a is not b for a, b in zip(
                (self.bootstrap, self.source, self.reports, self.reader, self.native_reader, self.clock),
                self._ports, strict=True))
                or body(self.bootstrap.enrollment) != self._inception
                or body(self.bootstrap.scope()) != self._scope
                or body(self.native_reader.enrollment) != self._e):
            raise ValueError('PERSONAL_CURRENT_COMPONENT_CHANGED')
        if type(now) is not int or now != self.clock():
            raise ValueError('PERSONAL_CURRENT_CLOCK')
        e, m, scope = strict(self._e), strict(self._m), strict(self._scope)
        source, reports, sg, rg = before = self._pins()
        original, ack = self.bootstrap.publication.acknowledged(scope['operation_id'])
        row = self.bootstrap.publication.row(scope['operation_id'])
        if row is None or row[0] != self._scope:
            raise ValueError('PERSONAL_CURRENT_FOREIGN_INCEPTION_INTENT')
        validate_initial_current(self.bootstrap.enrollment, original)
        if (original['state_digest'] != digest(initial_state(m))
                or {k: v for k, v in source.items() if k != 'entries'}
                != {k: v for k, v in original['source'].items() if k != 'entries'}
                or {k: v for k, v in reports.items() if k != 'reports'}
                != {k: v for k, v in original['reports'].items() if k != 'reports'}
                or reports['reports'][:1] != original['reports']['reports']):
            raise ValueError('PERSONAL_CURRENT_INCEPTION_PREFIX_CONFLICT')
        # Reuse native replay/projection and existing selected-reader FS3 audit.
        # Do not rerun initial-only readback after acknowledged later trades.
        if self.native_reader.verify_resources() is not True:
            raise ValueError('PERSONAL_CURRENT_NATIVE_RESOURCES')
        native = self.native_reader.read_committed()
        payload = self.reader.read_committed(e['account_id'], e['epoch'])
        proof = self.reader.verify(payload, account_id=e['account_id'], epoch=e['epoch'], now=now)
        if (proof.get('verified') is not True or payload.get('account_id') != e['account_id']
                or payload.get('epoch') != e['epoch']
                or type(payload.get('source_revision')) is not int
                or payload['source_revision'] != sg or native.get('schema') != 'QD_AUTO_OP_READ_V1'
                or native.get('manifest') != m or native.get('source_pin') != source
                or type(native.get('rows')) is not list or len(native['rows']) != sg
                or native.get('state') != payload.get('state')
                or self._pins() != before
                or self.bootstrap.publication.acknowledged(scope['operation_id']) != (original, ack)
                or self.native_reader.read_committed() != native):
            raise ValueError('PERSONAL_CURRENT_FINANCIAL_OR_REPORT_CONFLICT')
        end = self.clock()
        if type(end) is not int or not now <= end <= now + 5:
            raise ValueError('PERSONAL_CURRENT_CAPTURE_EXPIRED')
        cut = {'schema': 'QD_AUTO_NATIVE_FINANCIAL_CUT_V5', 'execution_domain': 'PERSONAL_PAPER',
               'enrollment_digest': digest(e), 'source_revision': sg,
               'state_digest': digest(payload['state']), 'source': source, 'reports': reports}
        generation, fingerprint = 1 + sg + rg, digest(cut)
        old = self._high_water
        if old and (sg < old[0] or rg < old[1]
                    or (sg, rg) == old[:2] and fingerprint != old[2]):
            raise ValueError('PERSONAL_CURRENT_OBSERVED_ROLLBACK')
        self._high_water = sg, rg, fingerprint
        p = publication_intent(e)
        publication = {'schema': 'QD_AUTO_NATIVE_PUBLICATION_V4', 'intent_digest': digest(p),
                       'operation_id': p['operation_id'], 'status': 'ACKNOWLEDGED', 'ack_id': digest(ack)}
        return cut, generation, publication

    @contextmanager
    def lease(self, request, now):
        request = strict(body(request))
        if (set(request) != {'scope', 'enrollment', 'grant'} or request['scope'] != 'LOCAL_ENROLLED'
                or body(request['enrollment']) != self._e):
            raise ValueError('PERSONAL_CURRENT_REQUEST_SCOPE')
        cut, generation, publication = self._capture(now)
        snapshot = {'schema': 'QD_AUTO_NATIVE_CURRENT_V4', 'request_digest': digest(request),
                    'scope': 'LOCAL_ENROLLED', 'revision': cut['source_revision'],
                    'acknowledged_revision': cut['source_revision'], 'high_water': cut['source_revision'],
                    'generation': generation, 'financial_digest': digest(cut),
                    'publication_ack': publication['ack_id'], 'publication': publication,
                    'status': 'ACKNOWLEDGED', 'observed_at': now, 'expires_at': now + 5}
        sealed, owner = body(snapshot), self

        class Lease:
            def __init__(self):
                self.snapshot = strict(sealed)

            def check(self, candidate, stamp):
                if (type(stamp) is not int or not now <= stamp <= now + 5
                        or body(candidate) != sealed or body(self.snapshot) != sealed):
                    return False
                return owner._capture(stamp) == (cut, generation, publication)

        lease = Lease()
        yield lease
        if not lease.check(snapshot, self.clock()):
            raise ValueError('PERSONAL_CURRENT_LEASE_CHANGED')

    def runtime_current(self, request, *, now):
        """V3 view of the same audited cut; existing runtime authority still verifies it."""
        e = strict(self._e)
        runtime = request['enrollment']
        read = runtime.get('reader_enrollment', {})
        if (runtime.get('schema') != 'QD_AUTO_LOCAL_RUNTIME_V3' or runtime.get('scope') != 'LOCAL_ENROLLED'
                or body(read) != body(self.reader.enrollment)
                or read.get('schema') != 'QD_AUTO_OP_READ_ENROLLMENT_V1'
                or read.get('account_id') != e['account_id'] or read.get('epoch') != e['epoch']):
            raise ValueError('PERSONAL_CURRENT_RUNTIME_SCOPE')
        cut, _, _ = self._capture(now)
        return {'schema': 'QD_AUTO_CURRENT_V3', 'status': 'ACKNOWLEDGED',
                'source': cut['source'], 'reports': cut['reports'], 'enrollment_digest': digest(runtime),
                'observed_at': now, 'expires_at': now + 5}

    def runtime_port(self):
        return self

    def current(self, request, *, now):
        return self.runtime_current(request, now=now)
