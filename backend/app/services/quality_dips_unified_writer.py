"""Actual V5 coordination path for unified custody; no issuer or startup defaults.

The portfolio custodian must independently authenticate this component and hold
its durable reservation before dispatch. This port never calls native execute.
"""
from app.services.paper_financial_replay import body, digest, number, strict, text
from app.services.quality_dips_autonomous_binding import EnrolledAutonomousRuntime
from app.services.quality_dips_operational_runtime import OperationalEnrolledRuntime


class EnrolledQualityDipsWriter:
    def __init__(self, *, runtime, authority):
        if type(runtime) not in (EnrolledAutonomousRuntime, OperationalEnrolledRuntime) or authority is None:
            raise ValueError('UNIFIED_QD_EXISTING_ENROLLED_RUNTIME_REQUIRED')
        self.runtime, self.authority = runtime, authority
        self.store = runtime.financial.store
        self.manifest = strict(body(runtime.runtime.engine.ledger.manifest))
        self.binding = {'runtime': runtime, 'store': self.store,
                        'enrollment_digest': digest(runtime.enrollment), 'manifest_digest': digest(self.manifest)}
        self._cut()

    def _cut(self):
        r = self.runtime
        if (self.binding['runtime'] is not r or r.financial.store is not self.store
                or digest(r.enrollment) != self.binding['enrollment_digest']
                or digest(r.runtime.engine.ledger.manifest) != self.binding['manifest_digest']
                or self.authority.verify_components(self.binding) is not True):
            raise ValueError('UNIFIED_QD_COMPONENT_OR_AUTHORITY_CHANGED')
        with r._action(readonly=True):
            cut = self.store.verified_cut()
            with r.runtime.engine.ledger.connect(readonly=True) as db:
                db.execute('BEGIN')
                state, head, operations = r.runtime.engine.ledger._load(db)
                if db.execute('SELECT 1 FROM projections WHERE receipt IS NULL').fetchone():
                    raise ValueError('UNIFIED_QD_COORDINATION_ACK_UNKNOWN')
            if (body(cut['manifest']) != body(self.manifest) or cut['head'] != head
                    or body(cut['state']) != body(state)
                    or cut['acknowledged_operations'] != {key: digest(value[0]) for key, value in operations.items()}
                    or self.authority.verify_cut(self.binding, cut) is not True):
                raise ValueError('UNIFIED_QD_NATIVE_COORDINATION_SOURCE_MISMATCH')
            return cut

    def propose(self, frame, observation):
        """The actual QD planner; the accepted caller supplies source-bound inputs."""
        cut = self._cut()
        if self.authority.verify_frame(self.binding, frame, observation, cut) is not True:
            raise ValueError('UNIFIED_QD_FRAME_SOURCE_UNVERIFIED')
        decision = self.runtime.preview(frame)['decision']
        if decision['source_head'] != cut['head']:
            raise ValueError('UNIFIED_QD_SOURCE_CHANGED_DURING_PREVIEW')
        command = decision['command']
        return strict(body({'operation_id': command['operation_id'], 'kind': command['kind'],
                            'command': command, 'source_head': cut['head'], 'frame': frame,
                            'enrollment_digest': self.binding['enrollment_digest']}))

    def _shape(self, proposal):
        if (type(proposal) is not dict or set(proposal) != {
                'operation_id', 'kind', 'command', 'source_head', 'frame', 'enrollment_digest'}
                or type(proposal['command']) is not dict
                or type(proposal['frame']) is not dict
                or proposal['frame'].get('schema') not in ('QD_AUTO_OBSERVATION_V3', 'QD_UNIFIED_SHUTDOWN_REQUEST_V1')
                or proposal['command'].get('schema') != 'QD_AUTO_COMMAND_V1'
                or proposal['enrollment_digest'] != self.binding['enrollment_digest']
                or proposal['command'].get('epoch') != self.manifest['epoch']
                or proposal['operation_id'] != proposal['command'].get('operation_id')
                or proposal['kind'] != proposal['command'].get('kind')):
            raise ValueError('UNIFIED_QD_EXACT_COMMAND_BINDING_REQUIRED')

    def preview(self, proposal, observation):
        self._shape(proposal)
        shutdown = proposal['frame'].get('schema') == 'QD_UNIFIED_SHUTDOWN_REQUEST_V1'
        expected = (self.propose_shutdown(proposal['frame'], observation) if shutdown
                    else self.propose(proposal['frame'], observation))
        if body(expected) != body(proposal):
            raise ValueError('UNIFIED_QD_PREVIEW_COMMAND_OR_SOURCE_CHANGED')
        value = self._shutdown_preview(proposal['frame'], observation) if shutdown else self.runtime.preview(proposal['frame'])['decision']
        if value['source_head'] != proposal['source_head'] or value['command_digest'] != digest(proposal['command']):
            raise ValueError('UNIFIED_QD_PREVIEW_CHANGED')
        return value

    def verify_proposal(self, proposal, observation):
        self._shape(proposal)
        cut = self._cut()
        prior = cut['acknowledged_operations'].get(proposal['operation_id'])
        if prior is not None:
            verifier = (self.authority.verify_shutdown_request if proposal['frame'].get('schema') == 'QD_UNIFIED_SHUTDOWN_REQUEST_V1'
                        else self.authority.verify_frame)
            if (prior != digest(proposal['command'])
                    or verifier(self.binding, proposal['frame'], observation, cut) is not True):
                raise ValueError('UNIFIED_QD_CONFLICTING_RETRY')
        else:
            self.preview(proposal, observation)
        return True

    def dispatch(self, proposal, reservation):
        self._shape(proposal)
        cut = self._cut()
        if (type(reservation) is not dict or reservation.get('state') != 'RESERVED'
                or cut['head'] != proposal['source_head']
                or self.authority.verify_reservation(self.binding, proposal, reservation, cut) is not True):
            raise ValueError('UNIFIED_QD_DURABLE_RESERVATION_REQUIRED')
        if proposal['frame'].get('schema') == 'QD_UNIFIED_SHUTDOWN_REQUEST_V1':
            self._shutdown_preview(proposal['frame'], None)
            r = self.runtime.runtime
            with self.runtime._action(), r._admission(r._now()):
                result = r.engine.step(proposal['frame']['decision_id'], bundles=[],
                    **proposal['frame']['request'], shutdown_mode='SHUTDOWN_FLATTEN',
                    expected_command_digest=digest(proposal['command']))
                if result.get('filled') is True:
                    r._publish_report(r._now())
        else:
            result = self.runtime.accept(proposal['frame'], expected_command_digest=digest(proposal['command']))
        if result.get('filled') is not True:
            raise ValueError('UNIFIED_QD_EFFECT_NOT_ACKNOWLEDGED')
        receipt = result['receipt']
        # Re-read both stores and the native ACK. No second financial callback.
        cut = self._cut()
        if (cut['acknowledged_operations'].get(proposal['operation_id']) != digest(proposal['command'])
                or receipt != self.store.operation_receipt(proposal['operation_id'], digest(proposal['command']))
                or digest(cut['state']) != receipt['state_digest']):
            raise ValueError('UNIFIED_QD_ACKNOWLEDGEMENT_MISMATCH')
        return receipt

    def _shutdown_preview(self, frame, observation):
        r = self.runtime.runtime
        if (type(frame) is not dict or set(frame) != {'schema', 'decision_id', 'request'}
                or frame['schema'] != 'QD_UNIFIED_SHUTDOWN_REQUEST_V1'
                or type(frame['request']) is not dict or set(frame['request']) != {'quotes', 'observation'}
                or not r.stopped.is_set() or not r.engine.entry_admission_closed):
            raise ValueError('UNIFIED_QD_SHUTDOWN_ADMISSION_REQUIRED')
        verifier = getattr(self.authority, 'verify_shutdown_request', None)
        if verifier is None or verifier(self.binding, frame, observation, self._cut()) is not True:
            raise ValueError('UNIFIED_QD_SHUTDOWN_CUSTODY_REQUIRED')
        with self.runtime._action(readonly=True), r._admission(r._now()):
            value = r.engine.preview(frame['decision_id'], bundles=[], **frame['request'], shutdown_mode='SHUTDOWN_FLATTEN')
        if value['command']['kind'] != 'EXIT':
            raise ValueError('UNIFIED_QD_SHUTDOWN_EXIT_ONLY')
        return value

    def propose_shutdown(self, frame, observation):
        value = self._shutdown_preview(frame, observation)
        command = value['command']
        return strict(body({'operation_id': command['operation_id'], 'kind': 'EXIT', 'command': command,
                            'source_head': value['source_head'], 'frame': frame,
                            'enrollment_digest': self.binding['enrollment_digest']}))


class QualityDipsUnifiedShutdown:
    """Existing QD guarded shutdown through global exit custody; never OS killing."""
    def __init__(self, *, writer, quotes, reports, session_id):
        if type(writer) is not EnrolledQualityDipsWriter or reports is not writer.runtime.runtime.reports or quotes is None:
            raise ValueError('UNIFIED_QD_SHUTDOWN_EXACT_COMPONENTS_REQUIRED')
        text(session_id)
        self.writer, self.quotes, self.reports, self.session_id = writer, quotes, reports, session_id
        self.runtime, self.completed = None, None

    def bind(self, runtime):
        from app.services.unified_paper_runtime import UnifiedPaperRuntime
        if self.runtime is not None or type(runtime) is not UnifiedPaperRuntime:
            raise ValueError('UNIFIED_QD_SHUTDOWN_SINGLE_BINDING_REQUIRED')
        self.runtime = runtime
        self._verify()

    def _verify(self):
        verifier = getattr(self.writer.authority, 'verify_shutdown_components', None)
        lane = self.runtime.lanes['QUALITY_DIPS'] if self.runtime is not None else None
        if (lane is None or lane.writer is not self.writer or lane.shutdown is not self
                or lane.reports is not self.reports or verifier is None
                or verifier(self.writer.binding, {'runtime': self.runtime, 'writer': self.writer,
                    'quotes': self.quotes, 'reports': self.reports, 'session_id': self.session_id}) is not True):
            raise ValueError('UNIFIED_QD_SHUTDOWN_COMPONENTS_UNVERIFIED')

    def stop(self, *, emergency):
        self._verify()
        if self.runtime.state != 'STOPPING' or not self.runtime.entry_closed.is_set():
            raise ValueError('UNIFIED_QD_GLOBAL_ADMISSION_NOT_CLOSED')
        r = self.writer.runtime.runtime
        r.engine.entry_admission_closed = True
        r.stopped.set()
        if emergency:
            return {'state': 'INCOMPLETE', 'reason': 'EMERGENCY_POSITIONS_PRESERVED'}
        try:
            if not r.run_done.wait(2):
                raise ValueError('UNIFIED_QD_DRAIN_TIMEOUT')
            cut = self.writer._cut()
            if self.completed is not None:
                if cut['head'] != self.completed['source_head']:
                    raise ValueError('UNIFIED_QD_SOURCE_CHANGED_AFTER_STOP')
                return strict(body(self.completed))
            positions = {key: p for key, p in cut['state']['positions'].items() if number(p['remaining']) > 0}
            if len(positions) > 1:
                raise ValueError('UNIFIED_QD_UNEXPECTED_POSITION_COUNT')
            for key, position in positions.items():
                request = strict(body(self.quotes.observe(position, timeout=2)))
                frame = {'schema': 'QD_UNIFIED_SHUTDOWN_REQUEST_V1',
                         'decision_id': 'unified-qd-stop:' + digest([self.session_id, self.writer.manifest['epoch'], key, position['revision']]),
                         'request': request}
                proposal = self.writer.propose_shutdown(frame, self.runtime.observations['QUALITY_DIPS'])
                self.runtime.dispatch_shutdown_exit('QUALITY_DIPS', proposal)
            cut = self.writer._cut()
            if self.runtime.uncertain or any(number(p['remaining']) > 0 for p in cut['state']['positions'].values()):
                raise ValueError('UNIFIED_QD_FINANCIAL_CUT_UNRESOLVED')
            self.reports.publish_session(session_id=self.session_id,
                started_at=r.grant['engine_grant']['issued_at'], cutoff_at=r._now(), observed_at=r._now())
            if self.writer.runtime.stop() != 'STOPPED':
                raise ValueError('UNIFIED_QD_WRITER_DRAIN_INCOMPLETE')
            final = self.writer._cut()
            if final['head'] != cut['head']:
                raise ValueError('UNIFIED_QD_SOURCE_CHANGED_DURING_DRAIN')
            history = self.reports.history()
            sessions = [doc['report'] for doc in history if doc['report']['schema'] == 'FS3_QD_SESSION_REPORT_V1'
                        and doc['report']['session']['session_id'] == self.session_id]
            report = sessions[-1] if sessions else None
            verifier = getattr(self.writer.authority, 'verify_drain', None)
            if (report is None or report['status'] != 'COMPLETE' or report['open_positions']
                    or report['epoch'] != self.writer.manifest['epoch']
                    or report['source']['root'] != final['root'] or report['source']['head'] != final['head']
                    or report['source']['cutoff_revision'] != final['state']['revision']
                    or number(report['cash']['closing']) != number(final['state']['cash'])
                    or verifier is None or verifier(self.writer.binding, final, {'report': report}) is not True):
                raise ValueError('UNIFIED_QD_REPORT_OR_FINAL_DRAIN_UNVERIFIED')
            self.completed = {'state': 'ACKNOWLEDGED_FLAT_AND_DRAINED', 'source_head': final['head'], 'cash': final['state']['cash'],
                              'session_id': self.session_id, 'cutoff_at': report['period']['cutoff_inclusive']}
            return strict(body(self.completed))
        except (ValueError, OSError, TimeoutError, KeyError, TypeError):
            return {'state': 'INCOMPLETE', 'reason': 'QD_PRICE_FINANCIAL_REPORT_OR_DRAIN_UNRESOLVED'}
