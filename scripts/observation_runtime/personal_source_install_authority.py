"""Installed Windows-bound authorization for a once-only QD source image.

Requires an already native-bound activation; cannot issue its own approval.
No source or account creation occurs in this module.
"""
from contextlib import contextmanager

from app.services.paper_financial_replay import body, digest
from app.services.personal_paper_runtime import validate_activation_record, validate_policy
from scripts.observation_runtime.personal_windows_clock import LocalWindowsClock
from scripts.observation_runtime.personal_paper_activation import NativePersonalActivationReader
from scripts.volume_inspector.windows_output import current_sid


class NativePersonalSourceInstallAuthority:
    def __init__(self, *, reader, policy, release_digest, accounts, clock, runtime_id,
                 enrollment_digest, root_id):
        if type(reader) is not NativePersonalActivationReader or type(clock) is not LocalWindowsClock:
            raise ValueError('SOURCE_INSTALL_NATIVE_ACTIVATION_AND_CLOCK_REQUIRED')
        clock.require_operational(runtime_id)
        if (type(enrollment_digest) is not str or len(enrollment_digest) != 64
                or any(c not in '0123456789abcdef' for c in enrollment_digest)
                or type(root_id) is not list or len(root_id) != 3
                or any(type(v) is not int or v < 0 for v in root_id)):
            raise ValueError('SOURCE_INSTALL_NATIVE_ENROLLMENT_REQUIRED')
        self.reader, self.policy, self.release = reader, validate_policy(policy), release_digest
        self.accounts, self.clock, self.runtime_id = accounts, clock, runtime_id
        self.enrollment_digest, self.root_id = enrollment_digest, list(root_id)
        self.operator = current_sid()
        self.used = False

    def _check(self, request):
        if self.used or current_sid() != self.operator:
            raise ValueError('SOURCE_INSTALL_OPERATOR_OR_ONCE_ONLY_REFUSED')
        self.clock.require_operational(self.runtime_id)
        now = self.clock()
        record = validate_activation_record(self.reader.read(), policy=self.policy,
            operator_id=self.operator, release=self.release, accounts=self.accounts,
            now=now, action='CONNECT_APPROVED_DATA')
        if (request.get('schema') != 'PERSONAL_COORDINATION_INSTALL_V1'
                or request.get('root') != self.root_id
                or request.get('enrollment') != self.enrollment_digest
                or type(request.get('image_digest')) is not str
                or len(request['image_digest']) != 64
                or any(c not in '0123456789abcdef' for c in request['image_digest'])):
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
