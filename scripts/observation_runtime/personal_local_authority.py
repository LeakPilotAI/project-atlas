"""Existing-record Windows operator/session binding for the bounded QD pilot.

No activation writer, credential, default authority or enrollment. The sole
operator's bound native record authorizes actions; it never replaces technical,
market-data, financial, resource or ownership checks.
"""
from app.services.paper_financial_replay import body, digest, strict
from app.services.perp_operational_contract import (
    validate_enrollment as validate_hl_enrollment,
)
from app.services.personal_paper_runtime import (
    validate_activation_record,
    validate_policy,
)
from app.services.quality_dips_autonomous_enrollment import validate_enrollment

from scripts.observation_runtime.personal_paper_inception import native_primitives
from scripts.observation_runtime.personal_windows_clock import LocalWindowsClock


class NativePersonalOperatorAuthority:
    def __init__(self, *, policy=None, enrollment=None, reader=None, clock=None,
                 runtime_id=None, clock_profile="WINDOWS_TIME_OPERATOR_CLOCK_V4",
                 accounts=None, postinception_owner=None, qd_enrollment=None):
        from scripts.observation_runtime.personal_paper_activation import (
            NativePersonalActivationReader,
        )
        from scripts.observation_runtime.personal_v7_operator_clock import (
            PROFILE,
            NativeV7PaperOperatorClock,
        )
        from scripts.observation_runtime.personal_v8_operator_clock import (
            PROFILE as V8_NTP_PROFILE,
        )
        from scripts.observation_runtime.personal_v8_operator_clock import (
            NativeV8PaperOperatorClock,
        )
        from scripts.observation_runtime.personal_version_safe_release_clock import (
            PROFILE as VERSION_SAFE_NTP_PROFILE,
        )
        from scripts.observation_runtime.personal_version_safe_release_clock import (
            NativeVersionSafePaperOperatorClock,
        )
        allowed_clock = (
            clock_profile == "WINDOWS_TIME_OPERATOR_CLOCK_V4" and type(clock) is LocalWindowsClock
            or clock_profile == PROFILE and type(clock) is NativeV7PaperOperatorClock
            or clock_profile == V8_NTP_PROFILE and type(clock) is NativeV8PaperOperatorClock
            or clock_profile == VERSION_SAFE_NTP_PROFILE and type(clock) is NativeVersionSafePaperOperatorClock
        )
        if (any(x is None for x in (policy, enrollment, reader, clock, runtime_id))
                or type(reader) is not NativePersonalActivationReader or not allowed_clock):
            raise ValueError('PERSONAL_NATIVE_OPERATOR_DEPENDENCIES_REQUIRED')
        clock.require_operational(runtime_id)
        self.policy = validate_policy(policy)
        self._lane = ('HYPERLIQUID' if type(enrollment) is dict
                      and enrollment.get('schema') == 'PERP_AUTO_NATIVE_ENROLLMENT_V1'
                      else 'QUALITY_DIPS')
        self.enrollment = (validate_hl_enrollment(enrollment)
                           if self._lane == 'HYPERLIQUID'
                           else validate_enrollment(enrollment))
        local_digest = digest(self.enrollment)
        if accounts is None:
            # Preserve the earlier QD-only pilot; a perpetual first inception
            # ALWAYS needs both real account identity bindings.
            if self._lane != 'QUALITY_DIPS':
                raise ValueError('PERSONAL_HL_TWO_ACCOUNT_INCEPTION_BINDING_REQUIRED')
            bound_accounts = {'QUALITY_DIPS': local_digest}
        else:
            bound_accounts = strict(body(accounts))
            if (type(accounts) is not dict
                    or set(bound_accounts) != {'QUALITY_DIPS', 'HYPERLIQUID'}
                    or bound_accounts.get(self._lane) != local_digest
                    or any(type(v) is not str or len(v) != 64
                           or any(c not in '0123456789abcdef' for c in v)
                           for v in bound_accounts.values())):
                raise ValueError('PERSONAL_NATIVE_OPERATOR_TWO_ACCOUNT_BINDING_REQUIRED')
        self.accounts = strict(body(bound_accounts))
        # The original HL authority was intentionally PREINCEPTION-ONLY.
        # Source data action G is impossible without a separately constructed
        # postinception authority tied to BOTH acknowledged FS1/FS3 accounts.
        # This never changes the rules for a preinception authority.
        self._postinception_owner = None
        self._postinception_qd = None
        self._postinception_ports = None
        if postinception_owner is not None or qd_enrollment is not None:
            from scripts.observation_runtime.personal_native_selected_owned_job_preflight import (
                RetainedSelectedNativeOwnerPreflight,
            )
            from scripts.observation_runtime.personal_writer_generation import (
                NativeRecoveredFinancialWriterOwner,
            )
            from scripts.observation_runtime.personal_version_safe_release_clock import (
                NativeVersionSafePaperOperatorClock,
                PROFILE as VERSION_SAFE_NTP_PROFILE,
                require_version_safe_release_digest,
            )
            if (self._lane != 'HYPERLIQUID'
                    or type(postinception_owner) not in (
                        RetainedSelectedNativeOwnerPreflight,
                        NativeRecoveredFinancialWriterOwner,
                    )
                    or type(qd_enrollment) is not dict
                    or type(clock) is not NativeVersionSafePaperOperatorClock
                    or clock_profile != VERSION_SAFE_NTP_PROFILE
                    or postinception_owner._phase not in (
                        'INITIAL_READBACK_ONLY', 'CURRENT_READBACK_ONLY')
                    or postinception_owner.release_digest
                    != self.enrollment['release_digest']
                    or self.accounts.get('QUALITY_DIPS')
                    != digest(validate_enrollment(qd_enrollment))
                    or self.accounts.get('HYPERLIQUID') != digest(self.enrollment)
                    or postinception_owner.require_exact_roster(
                        qd=qd_enrollment, perp=self.enrollment) is not True
                    or require_version_safe_release_digest(
                        clock=clock, runtime_id=runtime_id,
                        release_digest=postinception_owner.release_digest)
                    is not True
                    or postinception_owner.verify_still_running() is not True):
                raise ValueError('PERSONAL_HL_G_TWO_ORIGINAL_FINANCIAL_ACCOUNTS_REQUIRED')
            self._postinception_owner = postinception_owner
            self._postinception_qd = strict(body(qd_enrollment))
            self._postinception_ports = (postinception_owner, clock)
        self.reader, self.clock, self.runtime_id = reader, clock, runtime_id
        self.clock_profile = clock_profile
        self.native = native_primitives()
        self.operator = self.native.w.current_sid()
        self._config = body({'policy': self.policy, 'enrollment': self.enrollment,
                             'runtime_id': runtime_id, 'operator': self.operator, 'accounts': self.accounts})
        self._ports = reader, clock, self.native, clock_profile
        self.revoked, self._record, self._last = False, None, None

    def current_operator(self):
        current = self.native.w.current_sid()
        if current != self.operator:
            raise ValueError('PERSONAL_WINDOWS_OPERATOR_CHANGED')
        return current

    def revoke(self):
        self.revoked = True

    def activation(self, action):
        if getattr(self, '_lane', 'QUALITY_DIPS') == 'HYPERLIQUID':
            if self._postinception_owner is None:
                if action not in ('READ_ONLY', 'INITIALIZE_SIMULATED_ACCOUNTS'):
                    raise ValueError('PERSONAL_HL_FIRST_INCEPTION_ONLY_NO_PAPER_OPERATIONS')
            else:
                # This narrow G-stage owner supports source activation ONLY.
                # No INITIALIZE replay, AUTO_PAPER, SHUTDOWN, or live orders.
                if action not in ('READ_ONLY', 'CONNECT_APPROVED_DATA'):
                    raise ValueError('PERSONAL_HL_POSTINCEPTION_DATA_ONLY_NO_PAPER')
                owner = self._postinception_owner
                if (self._postinception_ports != (owner, self.clock)
                        or owner._phase not in (
                            'INITIAL_READBACK_ONLY', 'CURRENT_READBACK_ONLY')
                        or owner.release_digest != self.enrollment['release_digest']
                        or owner.require_exact_roster(
                            qd=self._postinception_qd, perp=self.enrollment)
                        is not True
                        or owner.verify_still_running() is not True):
                    raise ValueError('PERSONAL_HL_G_ORIGINAL_TWO_ACCOUNT_OWNER_LOST')
        if (self.revoked or getattr(self, '_lane', 'QUALITY_DIPS') != (
                'HYPERLIQUID' if self.enrollment.get('schema') ==
                'PERP_AUTO_NATIVE_ENROLLMENT_V1' else 'QUALITY_DIPS')
                or any(a is not b for a, b in zip(
                (self.reader, self.clock, self.native), self._ports[:3], strict=True))
                or self.clock_profile != self._ports[3]
                or body({'policy': self.policy, 'enrollment': self.enrollment,
                         'runtime_id': self.runtime_id, 'operator': self.operator,
                         'accounts': self.accounts}) != self._config):
            raise ValueError('PERSONAL_LOCAL_AUTHORITY_REVOKED_OR_CHANGED')
        self.clock.require_operational(self.runtime_id)
        now = self.clock()
        if type(now) is not int or self._last is not None and now < self._last:
            raise ValueError('PERSONAL_OPERATOR_CLOCK_ROLLBACK')
        record = validate_activation_record(self.reader.read(), policy=self.policy,
            operator_id=self.current_operator(), release=self.enrollment['release_digest'],
            accounts=self.accounts, now=now, action=action)
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


class NativePersonalRuntimeAuthority:
    """V3 proofs from the existing native operator, clock, custody and writer ports."""
    def __init__(self, *, operator=None, engine_session=None, custody=None, ownership=None,
                 source=None, enrollment=None):
        from app.services.quality_dips_iex_input import IEXPaperQuotes

        from scripts.observation_runtime.personal_engine_session import (
            NativePersonalEngineSession,
        )
        from scripts.observation_runtime.personal_runtime_current import (
            PersonalRuntimeCurrent,
        )
        from scripts.observation_runtime.personal_writer_ownership import (
            NativePersonalWriterOwnership,
        )

        if (type(operator) is not NativePersonalOperatorAuthority
                or type(engine_session) is not NativePersonalEngineSession
                or type(custody) is not PersonalRuntimeCurrent
                or type(ownership) is not NativePersonalWriterOwnership
                or type(source) is not IEXPaperQuotes or type(enrollment) is not dict
                or engine_session.operator is not operator or ownership.authority is not operator
                or custody.clock is not operator.clock):
            raise ValueError('PERSONAL_RUNTIME_NATIVE_DEPENDENCIES_REQUIRED')
        self.operator, self.engine_session, self.custody = operator, engine_session, custody
        self.ownership, self.source = ownership, source
        self.enrollment = strict(body(enrollment))
        self._ports = operator, engine_session, custody, ownership, source
        self._enrollment, self._grant = body(enrollment), None
        ownership._context({'enrollment': enrollment, 'grant': None})

    def verify(self, kind, request, *, now):
        if (any(a is not b for a, b in zip(
                (self.operator, self.engine_session, self.custody, self.ownership, self.source),
                self._ports, strict=True)) or body(self.enrollment) != self._enrollment
                or type(now) is not int or now != self.operator.clock()):
            raise ValueError('PERSONAL_RUNTIME_AUTHORITY_CHANGED')
        self.operator.activation('AUTO_PAPER')
        request = strict(body(request))
        context = {'enrollment': self.enrollment,
                   'grant': strict(self._grant) if self._grant is not None else None}
        if kind == 'CLOCK':
            if (set(request) != {'enrollment_digest', 'sample'}
                    or request['enrollment_digest'] != digest(self.enrollment)
                    or self.operator.clock.verify_runtime_sample(request['sample']) is not True):
                raise ValueError('PERSONAL_RUNTIME_CLOCK_REFUSED')
        elif kind == 'SESSION':
            if (set(request) != {'enrollment', 'grant'} or body(request['enrollment']) != self._enrollment
                    or type(request['grant']) is not dict
                    or request['grant'].get('schema') != 'QD_AUTO_LOCAL_SESSION_V3'
                    or request['grant'].get('enrollment_digest') != digest(self.enrollment)
                    or self._grant is not None and body(request['grant']) != self._grant):
                raise ValueError('PERSONAL_RUNTIME_SESSION_REFUSED')
            self.engine_session.verify(request['grant']['engine_grant'], now=now)
            self._grant = body(request['grant'])
        elif kind in ('CURRENT', 'DRAIN', 'OBSERVATION'):
            if self._grant is None:
                raise ValueError('PERSONAL_RUNTIME_SESSION_MISSING')
            self.engine_session.verify(context['grant']['engine_grant'], now=now)
            if kind == 'CURRENT':
                if request != self.custody.current(context, now=now):
                    raise ValueError('PERSONAL_RUNTIME_CURRENT_REFUSED')
            elif kind == 'DRAIN':
                if request != self.ownership.drain(context, now=now):
                    raise ValueError('PERSONAL_RUNTIME_DRAIN_REFUSED')
            elif (request.get('session_id') != context['grant']['engine_grant']['session_id']
                  or self.source.verify_observation(request, now=now) is not True):
                raise ValueError('PERSONAL_RUNTIME_OBSERVATION_REFUSED')
        else:
            raise ValueError('PERSONAL_RUNTIME_UNKNOWN_PROOF_KIND')
        return {'schema': 'QD_AUTO_LOCAL_AUTHORITY_V3', 'kind': kind, 'verified': True,
                'binding': digest(request), 'scope': 'LOCAL_ENROLLED', 'issuer_id': 'PERSONAL_LOCAL_OPERATOR'}
