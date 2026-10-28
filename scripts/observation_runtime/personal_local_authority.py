"""Existing-record Windows operator/session binding for the bounded QD pilot.

No activation writer, credential, default authority or enrollment. The sole
operator's bound native record authorizes actions; it never replaces technical,
market-data, financial, resource or ownership checks.
"""
from app.services.paper_financial_replay import body, digest, strict
from app.services.personal_paper_runtime import validate_activation_record, validate_policy
from app.services.quality_dips_autonomous_enrollment import validate_enrollment

from scripts.observation_runtime.personal_paper_inception import native_primitives
from scripts.observation_runtime.personal_windows_clock import LocalWindowsClock


class NativePersonalOperatorAuthority:
    def __init__(self, *, policy=None, enrollment=None, reader=None, clock=None, runtime_id=None):
        from scripts.observation_runtime.personal_paper_activation import (
            NativePersonalActivationReader,
        )

        if (any(x is None for x in (policy, enrollment, reader, clock, runtime_id))
                or type(reader) is not NativePersonalActivationReader or type(clock) is not LocalWindowsClock):
            raise ValueError('PERSONAL_NATIVE_OPERATOR_DEPENDENCIES_REQUIRED')
        clock.require_operational(runtime_id)
        self.policy, self.enrollment = validate_policy(policy), validate_enrollment(enrollment)
        self.reader, self.clock, self.runtime_id = reader, clock, runtime_id
        self.native = native_primitives()
        self.operator = self.native.w.current_sid()
        self._config = body({'policy': self.policy, 'enrollment': self.enrollment,
                             'runtime_id': runtime_id, 'operator': self.operator})
        self._ports = reader, clock, self.native
        self.revoked, self._record, self._last = False, None, None

    def current_operator(self):
        current = self.native.w.current_sid()
        if current != self.operator:
            raise ValueError('PERSONAL_WINDOWS_OPERATOR_CHANGED')
        return current

    def revoke(self):
        self.revoked = True

    def activation(self, action):
        if (self.revoked or any(a is not b for a, b in zip(
                (self.reader, self.clock, self.native), self._ports, strict=True))
                or body({'policy': self.policy, 'enrollment': self.enrollment,
                         'runtime_id': self.runtime_id, 'operator': self.operator}) != self._config):
            raise ValueError('PERSONAL_LOCAL_AUTHORITY_REVOKED_OR_CHANGED')
        self.clock.require_operational(self.runtime_id)
        now = self.clock()
        if type(now) is not int or self._last is not None and now < self._last:
            raise ValueError('PERSONAL_OPERATOR_CLOCK_ROLLBACK')
        record = validate_activation_record(self.reader.read(), policy=self.policy,
            operator_id=self.current_operator(), release=self.enrollment['release_digest'],
            accounts={'QUALITY_DIPS': digest(self.enrollment)}, now=now, action=action)
        if self._record is not None and body(record) != self._record:
            raise ValueError('PERSONAL_ACTIVATION_RECORD_CHANGED')
        self._record, self._last = body(record), now
        return record

    def verify(self, request):
        """Reservation verifier. One activation ID is one <=60-second session ID.

        Durable single-use enforcement is PersonalSessionReservations, not this
        read-only verifier. Construction and verification never reserve/start.
        """
        request = strict(body(request))
        if (type(request) is not dict or set(request) != {'scope', 'enrollment', 'grant'}
                or request['scope'] != 'LOCAL_ENROLLED'
                or body(request['enrollment']) != body(self.enrollment)):
            raise ValueError('PERSONAL_OPERATOR_SESSION_SCOPE')
        record = self.activation('AUTO_PAPER')
        grant = request['grant']
        if (type(grant) is not dict or set(grant) != {'schema', 'session_id', 'enrollment_digest',
                'issued_at', 'expires_at', 'capabilities'}
                or grant['schema'] != 'QD_AUTO_NATIVE_SESSION_V4'
                or grant['session_id'] != record['activation_id']
                or grant['enrollment_digest'] != digest(self.enrollment)
                or grant['capabilities'] != ['AUTO_PAPER']
                or any(type(grant[k]) is not int for k in ('issued_at', 'expires_at'))
                or not record['issued_at'] <= grant['issued_at'] <= self._last < grant['expires_at']
                <= min(grant['issued_at'] + 60, record['expires_at'])):
            raise ValueError('PERSONAL_OPERATOR_60_SECOND_SESSION_REQUIRED')
        return True
