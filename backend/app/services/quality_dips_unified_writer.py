"""Actual V5 coordination path for unified custody; no issuer or startup defaults.

The portfolio custodian must independently authenticate this component and hold
its durable reservation before dispatch. This port never calls native execute.
"""
from app.services.paper_financial_replay import body, digest, strict
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
                or proposal['command'].get('schema') != 'QD_AUTO_COMMAND_V1'
                or proposal['enrollment_digest'] != self.binding['enrollment_digest']
                or proposal['command'].get('epoch') != self.manifest['epoch']
                or proposal['operation_id'] != proposal['command'].get('operation_id')
                or proposal['kind'] != proposal['command'].get('kind')):
            raise ValueError('UNIFIED_QD_EXACT_COMMAND_BINDING_REQUIRED')

    def preview(self, proposal, observation):
        self._shape(proposal)
        expected = self.propose(proposal['frame'], observation)
        if body(expected) != body(proposal):
            raise ValueError('UNIFIED_QD_PREVIEW_COMMAND_OR_SOURCE_CHANGED')
        value = self.runtime.preview(proposal['frame'])['decision']
        if value['source_head'] != proposal['source_head'] or value['command_digest'] != digest(proposal['command']):
            raise ValueError('UNIFIED_QD_PREVIEW_CHANGED')
        return value

    def verify_proposal(self, proposal, observation):
        self._shape(proposal)
        cut = self._cut()
        prior = cut['acknowledged_operations'].get(proposal['operation_id'])
        if prior is not None:
            if (prior != digest(proposal['command'])
                    or self.authority.verify_frame(self.binding, proposal['frame'], observation, cut) is not True):
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
