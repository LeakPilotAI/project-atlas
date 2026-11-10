"""Installed Windows-bound authorization for a once-only QD source image.

Requires an already native-bound activation; cannot issue its own approval.
No source or account creation occurs in this module.
"""
import hashlib
from contextlib import contextmanager

from app.services.paper_financial_replay import body, digest
from app.services.personal_paper_runtime import validate_activation_record, validate_policy
from scripts.observation_runtime.personal_windows_clock import LocalWindowsClock
from scripts.observation_runtime.personal_v7_operator_clock import (
    NativeV7PaperOperatorClock, PROFILE as V7_NTP_PROFILE,
)
from scripts.observation_runtime.personal_v8_operator_clock import (
    NativeV8PaperOperatorClock, PROFILE as V8_NTP_PROFILE,
)
from scripts.observation_runtime.personal_version_safe_release_clock import (
    NativeVersionSafePaperOperatorClock, PROFILE as VERSION_SAFE_NTP_PROFILE,
    require_version_safe_release_digest,
)
from scripts.observation_runtime.personal_paper_activation import NativePersonalActivationReader
from scripts.volume_inspector.windows_output import current_sid


class NativePersonalSourceInstallAuthority:
    def __init__(self, *, reader, policy, release_digest, accounts, clock, runtime_id,
                 enrollment_digest, root_id, initial_image,
                 clock_profile="WINDOWS_TIME_OPERATOR_CLOCK_V4"):
        valid_clock = (
            clock_profile == "WINDOWS_TIME_OPERATOR_CLOCK_V4" and type(clock) is LocalWindowsClock
            or clock_profile == V7_NTP_PROFILE and type(clock) is NativeV7PaperOperatorClock
            or clock_profile == V8_NTP_PROFILE and type(clock) is NativeV8PaperOperatorClock
            or clock_profile == VERSION_SAFE_NTP_PROFILE and type(clock) is NativeVersionSafePaperOperatorClock
        )
        if type(reader) is not NativePersonalActivationReader or not valid_clock:
            raise ValueError('SOURCE_INSTALL_NATIVE_ACTIVATION_AND_CLOCK_REQUIRED')
        # A valid R15 clock is not proof that a caller-selected release digest
        # belongs to R15. Rebind the exact selected immutable artifact first.
        if clock_profile == VERSION_SAFE_NTP_PROFILE:
            if require_version_safe_release_digest(
                    clock=clock, runtime_id=runtime_id,
                    release_digest=release_digest) is not True:
                raise ValueError('SOURCE_INSTALL_SELECTED_RELEASE_REQUIRED')
        clock.require_operational(runtime_id)
        if (type(enrollment_digest) is not str or len(enrollment_digest) != 64
                or any(c not in '0123456789abcdef' for c in enrollment_digest)
                or type(root_id) is not list or len(root_id) != 3
                or any(type(v) is not int or v < 0 for v in root_id)):
            raise ValueError('SOURCE_INSTALL_NATIVE_ENROLLMENT_REQUIRED')
        self.reader, self.policy, self.release = reader, validate_policy(policy), release_digest
        self.accounts, self.clock, self.runtime_id = accounts, clock, runtime_id
        if type(initial_image) is not bytes or not initial_image:
            raise ValueError('SOURCE_INSTALL_EXACT_INITIAL_IMAGE_REQUIRED')
        self.enrollment_digest, self.root_id = enrollment_digest, list(root_id)
        self.initial_image_digest = hashlib.sha256(initial_image).hexdigest()
        self.operator = current_sid()
        self.clock_profile = clock_profile
        self._bound_clock = clock
        self._bound_clock_profile = clock_profile
        self.used = False

    def _check(self, request):
        if (self.used or current_sid() != self.operator
                or self.clock is not self._bound_clock
                or self.clock_profile != self._bound_clock_profile):
            raise ValueError('SOURCE_INSTALL_OPERATOR_OR_ONCE_ONLY_REFUSED')
        self.clock.require_operational(self.runtime_id)
        now = self.clock()
        record = validate_activation_record(self.reader.read(), policy=self.policy,
            operator_id=self.operator, release=self.release, accounts=self.accounts,
            now=now, action='CONNECT_APPROVED_DATA')
        if (request.get('schema') != 'PERSONAL_COORDINATION_INSTALL_V1'
                or request.get('root') != self.root_id
                or request.get('enrollment') != self.enrollment_digest
                or request.get('image_digest') != self.initial_image_digest):
            raise ValueError('SOURCE_INSTALL_IMAGE_BINDING_REFUSED')
        return digest(record)

    @contextmanager
    def lease(self, request):
        original = body(request)
        activation = self._check(request)
        owner = self
        class Lease:
            def check(self, current):
                try:
                    return (not owner.used and body(current) == original
                            and owner._check(current) == activation)
                except (ValueError, OSError, KeyError, TypeError):
                    return False
        lease = Lease()
        try:
            yield lease
            if not lease.check(request):
                raise ValueError('SOURCE_INSTALL_LEASE_CHANGED')
            self.used = True
        except BaseException:
            # Once a native writer may have entered, never silently retry.
            self.used = True
            raise
