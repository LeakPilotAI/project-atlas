"""Personal native operation admission over existing durable coordination.

No issuer, path, grant, financial inception or session defaults. This adapter
authorizes only an already reserved canonical engine operation under the same
native operator/session/writer binding. Local custody is not anti-rollback trust.
"""
from contextlib import contextmanager, nullcontext

from app.services.paper_financial_replay import body, digest, strict
from app.services.personal_current_pins import PersonalCurrentPins
from app.services.personal_native_coordination import PersonalNativeCoordination
from app.services.personal_publication_custody import PersonalFinancialOperationCustody
from app.services.quality_dips_autonomous_paper import AutonomousPaper

from scripts.observation_runtime.personal_engine_session import NativePersonalEngineSession
from scripts.observation_runtime.personal_local_authority import NativePersonalOperatorAuthority
from scripts.observation_runtime.personal_writer_ownership import NativePersonalWriterOwnership


class NativePersonalFinancialAuthority:
    def __init__(self, *, operator=None, ownership=None, engine=None, session=None, source=None):
        if (type(operator) is not NativePersonalOperatorAuthority
                or type(ownership) is not NativePersonalWriterOwnership
                or type(engine) is not AutonomousPaper or type(session) is not NativePersonalEngineSession
                or type(source) is not PersonalCurrentPins or type(source.ledger) is not PersonalNativeCoordination
                or ownership.authority is not operator or session.operator is not operator
                or ownership.ledger is not source.ledger or engine.ledger is not source.ledger
                or engine.session_authority is not session or engine.clock is not operator.clock
                or body(engine.ledger.manifest) != body(session.manifest)):
            raise ValueError('PERSONAL_FINANCIAL_NATIVE_COMPONENTS_REQUIRED')
        self.operator, self.ownership, self.engine, self.session, self.source = operator, ownership, engine, session, source
        self.ledger = source.ledger
        self.custody = PersonalFinancialOperationCustody(self.ledger)
        self._ports = operator, ownership, engine, session, source, self.ledger, self.custody
        self._enrollment = body(operator.enrollment)
        self._manifest = body(self.ledger.manifest)

    def _verify(self, command):
        if (any(a is not b for a, b in zip((self.operator, self.ownership, self.engine, self.session,
                self.source, self.ledger, self.custody), self._ports, strict=True))
                or body(self.operator.enrollment) != self._enrollment
                or body(self.ownership.enrollment) != self._enrollment
                or body(self.ledger.manifest) != self._manifest
                or self.engine.ledger is not self.ledger or self.source.ledger is not self.ledger):
            raise ValueError('PERSONAL_FINANCIAL_COMPONENT_CHANGED')
        now = self.operator.clock()
        if command is None:
            self.operator.activation('READ_ONLY')
            pin, e = self.source.current(), self.operator.enrollment
            read = {'schema': 'QD_AUTO_OP_READ_ENROLLMENT_V1', 'account_id':e['account_id'], 'epoch':e['epoch'],
                    'inception':pin['inception'], **{r+'_root': e['resources'][r]['native_id'] for r in ('source','projection','report')}}
            return {'schema':'PERSONAL_NATIVE_READ_LEASE_V1','reader_enrollment':read}, now
        grant = strict(body(self.engine.grant))
        self.session.verify(grant, now=now)
        native = {'schema':'QD_AUTO_NATIVE_SESSION_V4','session_id':grant['session_id'],
                  'enrollment_digest':digest(self.operator.enrollment), 'issued_at':grant['issued_at'],
                  'expires_at':grant['expires_at'],'capabilities':['AUTO_PAPER']}
        request = {'scope':'LOCAL_ENROLLED','enrollment':self.operator.enrollment,'grant':native}
        if self.operator.verify(request) is not True:
            raise ValueError('PERSONAL_FINANCIAL_SESSION_REFUSED')
        if (command.get('schema') != 'QD_AUTO_COMMAND_V1' or command.get('manual') is not False
                or command.get('epoch') != self.ledger.manifest['epoch']
                or command.get('session_id') != grant['session_id']):
            raise ValueError('PERSONAL_FINANCIAL_COMMAND_SCOPE')
        return request, now

    def _canonical(self, command):
        with self.ledger.connect(readonly=True) as db:
            _state, _head, operations = self.ledger._load(db)
            operation = operations.get(command['operation_id'])
            row = db.execute('SELECT body,receipt FROM projections WHERE id=?', (command['operation_id'],)).fetchone()
            if (operation is None or body(operation[0]) != body(command) or row != (digest(command), None)
                    or db.execute("SELECT 1 FROM personal_sessions WHERE state!='ACKNOWLEDGED' OR state IS NULL").fetchone()):
                raise ValueError('PERSONAL_FINANCIAL_UNRESERVED_OR_ALREADY_ACKNOWLEDGED')
            return strict(body(operation[1]))

    @contextmanager
    def lease(self, request, now):
        request = strict(body(request))
        if (type(request) is not dict or set(request) != {'schema','enrollment','current','command'}
                or request['schema'] != 'QD_AUTO_OP_ADMISSION_REQUEST_V1'
                or body(request['enrollment']) != self._enrollment):
            raise ValueError('PERSONAL_FINANCIAL_REQUEST_SCOPE')
        command = request['command']
        context, stamp = self._verify(command)
        if type(now) is not int or now != stamp or request['current'] != self.source.current():
            raise ValueError('PERSONAL_FINANCIAL_STALE_CUT')
        if (request['current'].get('schema') != 'QD_AUTO_OP_PIN_V1'
                or request['current'].get('root') != self.operator.enrollment['resources']['source']['native_id']
                or request['current'].get('epoch') != self.ledger.manifest['epoch']
                or type(request['current'].get('entries')) is not list
                or not 0 <= len(request['current']['entries']) <= 128):
            raise ValueError('PERSONAL_FINANCIAL_FOREIGN_SOURCE')
        with self.ownership.lease(context, now) as owned:
            if request['current'] != self.source.current():
                raise ValueError('PERSONAL_FINANCIAL_CUT_CHANGED_BEFORE_ADMISSION')
            with self.ledger.connect(readonly=True) as db:
                if db.execute("SELECT 1 FROM personal_publications WHERE state!='ACKNOWLEDGED' OR state IS NULL").fetchone():
                    raise ValueError('PERSONAL_FINANCIAL_PENDING_OR_UNKNOWN')
            expected = None if command is None else self._canonical(command)
            if command is not None and command['expected_source_revision'] != len(request['current']['entries']):
                raise ValueError('PERSONAL_FINANCIAL_SOURCE_REVISION')
            ident = 'personal-financial:'+digest([self._enrollment, command['operation_id']]) if command is not None else 'read:'+digest(request)
            intent = {'schema':'PERSONAL_FINANCIAL_INTENT_V1','operation_id':ident,'request_digest':digest(request)}
            reservation = self.custody.reserve(intent, context, now) if command is not None else nullcontext(None)
            with reservation as tx:
                snapshot = {'schema':'QD_AUTO_OP_ADMISSION_V1','request_digest':digest(request),
                            'status':'READ_ACCEPTED' if command is None else 'PENDING',
                            'reservation_id':ident,'expires_at':now+5,'revoked':False}
                sealed, owner, acknowledged = body(snapshot), self, [None]

                class Lease:
                    def __init__(self): self.snapshot = strict(sealed)
                    def check(self, candidate, stamp):
                        owner._verify(command)
                        return (type(stamp) is int and now <= stamp <= now+5
                                and body(candidate) == sealed and body(self.snapshot) == sealed
                                and owned.check(owned.snapshot, stamp) is True
                                and (tx is None or tx.check(tx.snapshot, stamp)))
                    def acknowledge(self, req, receipt, pin):
                        if (tx is None or req != request or receipt != expected or pin != owner.source.current()
                                or not self.check(snapshot, owner.operator.clock())
                                or {k:v for k,v in pin.items() if k!='entries'} != {k:v for k,v in request['current'].items() if k!='entries'}
                                or pin['entries'][:-1] != request['current']['entries']
                                or len(pin['entries']) != len(request['current']['entries'])+1):
                            raise ValueError('PERSONAL_FINANCIAL_ACK_EVIDENCE')
                        commit = tx.commit({'receipt':receipt,'source':pin}, owner.operator.clock())
                        tx.acknowledge(commit, owner.operator.clock())
                        result = {'schema':'QD_AUTO_OP_RESERVATION_ACK_V1','request_digest':digest(request),
                                  'receipt_digest':digest(receipt),'status':'ACKNOWLEDGED'}
                        acknowledged[0] = result
                        return strict(body(result))
                    def verify_ack(self, ack):
                        current, _receipt = owner.custody.acknowledged(ident)
                        return (acknowledged[0] is not None and ack == acknowledged[0]
                                and current == {'receipt':expected,'source':owner.source.current()})
                    def mark_unknown(self, req):
                        if tx is None or req != request: raise ValueError('PERSONAL_FINANCIAL_UNKNOWN_SCOPE')
                        context, stamp = owner._verify(command)
                        with owner.ownership.lease(context, stamp): tx.mark_unknown('NATIVE_PUBLICATION_UNCERTAIN')

                lease = Lease()
                yield lease
                if not lease.check(snapshot, self.operator.clock()):
                    raise ValueError('PERSONAL_FINANCIAL_LEASE_CHANGED')
