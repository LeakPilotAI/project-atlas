"""Personal QD reader -> existing read-only host. No writer/provider/launcher.

Uses the already composed personal runtime's actual reader and installation
lease; it does not translate personal acceptance into strict operational gates.
Constructing this adapter grants neither a financial session nor host startup.
"""

import os
import threading
import uuid

from app.services.paper_financial_replay import body, digest, strict
from app.services.personal_paper_runtime import (
    PersonalEnrolledRuntime,
    PersonalOperatorInstallation,
    checked_personal_installation,
)

from scripts.observation_runtime.quality_dips_read_service import observe_self


class PersonalReadComposition:
    def __init__(self, *, runtime=None, observer=None):
        if type(runtime) is not PersonalEnrolledRuntime:
            raise ValueError("PERSONAL_COMPOSED_RUNTIME_REQUIRED")
        if type(runtime.installation) is not PersonalOperatorInstallation:
            raise ValueError("PERSONAL_READ_INSTALLATION_REQUIRED")
        self.runtime, self.installation = runtime, runtime.installation
        self.reader = runtime.runtime.reader
        self.clock = runtime.runtime.engine.clock
        self.observer = observe_self if observer is None else observer
        self.identity = strict(body(self.observer()))
        if (set(self.identity) != {"pid", "creation_filetime", "image"}
                or type(self.identity["pid"]) is not int or self.identity["pid"] != os.getpid()
                or type(self.identity["creation_filetime"]) is not int or self.identity["creation_filetime"] <= 0
                or type(self.identity["image"]) is not str or not self.identity["image"].startswith("D:\\")):
            raise ValueError("PERSONAL_READ_PROCESS_IDENTITY_REQUIRED")
        native = runtime.admission.enrollment
        self.account, self.epoch = native["account_id"], native["epoch"]
        self.enrollment = strict(body(self.reader.enrollment))
        if (self.enrollment.get("schema") != "QD_AUTO_OP_READ_ENROLLMENT_V1"
                or self.enrollment.get("account_id") != self.account or self.enrollment.get("epoch") != self.epoch
                or self.installation.accounts.get("QUALITY_DIPS") != digest(native)
                or self.installation.release != native["release_digest"]
                or runtime.enrollment.get("execution_domain") != "PERSONAL_PAPER"):
            raise ValueError("PERSONAL_READ_ACCOUNT_OR_DOMAIN_MISMATCH")
        self._native_digest, self._read_digest = digest(native), digest(self.enrollment)
        self._runtime_digest, self._scope = digest(runtime.enrollment), (self.account, self.epoch)
        self._ports = (runtime, self.installation, self.reader, self.clock, self.observer)
        self.host_id = uuid.uuid4().hex
        self.host_claim_lock, self.host_claimed = threading.Lock(), False
        self._host_id, self._identity = self.host_id, body(self.identity)
        self.operational = True  # Host lifecycle only; not strict gate acceptance.
        self._verify()

    def _verify(self):
        r = self.runtime
        if (any(a is not b for a, b in zip(
                (r, self.installation, self.reader, self.clock, self.observer), self._ports, strict=True))
                or r.installation is not self.installation or r.runtime.reader is not self.reader
                or r.runtime.engine.clock is not self.clock
                or digest(r.admission.enrollment) != self._native_digest
                or digest(r.enrollment) != self._runtime_digest
                or (self.account, self.epoch) != self._scope
                or digest(self.reader.enrollment) != self._read_digest
                or digest(self.enrollment) != self._read_digest
                or self.host_id != self._host_id or body(self.identity) != self._identity
                or body(self.observer()) != self._identity
                or self.installation.accounts.get("QUALITY_DIPS") != self._native_digest
                or r.admission.acceptance is not r._personal_acceptance):
            raise ValueError("PERSONAL_READ_COMPONENT_OR_PROCESS_CHANGED")
        r.financial.components()  # Existing native identity/current/read checks.

    def admitted(self, operation):
        self._verify()
        request = {"schema": "ATLAS_PERSONAL_READ_SERVICE_CONTEXT_V1", "action": "READ_ONLY",
                   "host_id": self.host_id, "process": self.identity,
                   "enrollment_digest": self._native_digest, "reader_digest": self._read_digest}
        now = self.clock()
        with self.installation.lease(request) as lease:
            proof = checked_personal_installation(lease, request)
            if not lease.check_components(self.runtime.installation_components()):
                raise ValueError("PERSONAL_READ_INSTALLATION_COMPONENTS_CHANGED")
            result = operation()
            self._verify()
            end = self.clock()
            if (type(now) is not int or type(end) is not int or not now <= end <= now + 30
                    or not lease.check(proof)
                    or not lease.check_components(self.runtime.installation_components())):
                raise ValueError("PERSONAL_READ_CONTINUITY_LOST")
            return result

    def read_committed(self, account_id, epoch):
        if (account_id, epoch) != (self.account, self.epoch):
            raise ValueError("PERSONAL_READ_ACCOUNT_SCOPE")
        return self.admitted(lambda: self.reader.read_committed(account_id, epoch))

    def verify(self, payload, **context):
        if (context.get("account_id"), context.get("epoch")) != (self.account, self.epoch):
            raise ValueError("PERSONAL_READ_ACCOUNT_SCOPE")
        return self.admitted(lambda: self.reader.verify(payload, **context))

    def preflight(self):
        return self.read_committed(self.account, self.epoch)

    def verify_control_bridge(self, bridge):
        from app.services.quality_dips_stop_bridge import PaperStopBridge

        self._verify()
        process = {'pid': self.identity['pid'], 'created': self.identity['creation_filetime'],
                   'image': self.identity['image']}
        if (type(bridge) is not PaperStopBridge or bridge.runtime is not self.runtime
                or body(bridge.identity) != body(process)):
            return False
        # READ_ONLY is insufficient. The explicit action lease is also checked
        # on every command by the bridge, not just at route registration.
        with bridge.authorized('SHUTDOWN_FLATTEN'):
            return True


class PersonalReadOnlyAccountComposition:
    """Manual restart reader with historical writer enrollment left untouched.

    No financial runtime, command bridge, session reservation or provider. The
    host owns only its new reader process; it gains no historical writer control.
    """
    def __init__(self, *, current=None, installation=None, ownership=None):
        from app.services.quality_dips_operational_presentation import (
            OperationalAutonomousSelectedRead,
        )

        from scripts.observation_runtime.personal_installation_technical import (
            NativePersonalTechnicalChecks,
        )
        from scripts.observation_runtime.personal_runtime_current import PersonalRuntimeCurrent
        from scripts.observation_runtime.personal_writer_ownership import (
            NativePersonalWriterOwnership,
        )

        if (type(current) is not PersonalRuntimeCurrent or type(installation) is not PersonalOperatorInstallation
                or type(ownership) is not NativePersonalWriterOwnership or ownership.read_only is not True
                or type(current.reader) is not OperationalAutonomousSelectedRead
                or type(installation.technical) is not NativePersonalTechnicalChecks
                or installation.technical.current is not current or installation.technical.engine is not None
                or installation.technical.ownership is not ownership or installation.identity is not ownership.authority
                or installation.clock is not current.clock):
            raise ValueError('PERSONAL_EXISTING_READ_ONLY_ACCOUNT_REQUIRED')
        self.current, self.installation, self.ownership = current, installation, ownership
        self.reader, self.clock, self.observer = current.reader, current.clock, observe_self
        self.enrollment = strict(body(self.reader.enrollment))
        self.account, self.epoch = self.enrollment['account_id'], self.enrollment['epoch']
        self._native_digest = digest(current.bootstrap.enrollment['native_enrollment'])
        native = current.bootstrap.enrollment['native_enrollment']
        if (installation.release != native['release_digest']
                or body(ownership.enrollment) != body(native)):
            raise ValueError('PERSONAL_READ_ONLY_RELEASE_OR_ENROLLMENT')
        self._read_digest = digest(self.enrollment)
        self.identity = strict(body(self.observer()))
        self._identity = body(self.identity)
        self.host_id = self._host_id = uuid.uuid4().hex
        self.host_claim_lock, self.host_claimed = threading.Lock(), False
        self.operational = True  # Read-host lifecycle only, never financial startup.
        self._ports = current, installation, ownership, self.reader, self.clock, self.observer
        self._verify()

    def components(self):
        return {'current':self.current,'reader':self.reader,'ownership':self.ownership,'clock':self.clock}

    def _verify(self):
        if (any(a is not b for a,b in zip((self.current,self.installation,self.ownership,self.reader,self.clock,self.observer),
                                        self._ports,strict=True))
                or self.ownership.read_only is not True or self.current.reader is not self.reader
                or self.installation.accounts != {'QUALITY_DIPS':self._native_digest}
                or digest(self.current.bootstrap.enrollment['native_enrollment']) != self._native_digest
                or digest(self.reader.enrollment) != self._read_digest
                or digest(self.enrollment) != self._read_digest or self.host_id != self._host_id
                or (self.account,self.epoch) != (self.enrollment['account_id'],self.enrollment['epoch'])
                or body(self.identity) != self._identity or body(self.observer()) != self._identity
                or self.ownership.identity != {'schema':'QD_OP_PROCESS_ID_V1',**self.identity}):
            raise ValueError('PERSONAL_READ_ONLY_PROCESS_OR_ACCOUNT_CHANGED')
        self.ownership._verify()

    def admitted(self, operation):
        self._verify()
        request = {'schema':'ATLAS_PERSONAL_READ_SERVICE_CONTEXT_V1','action':'READ_ONLY',
                   'host_id':self.host_id,'process':self.identity,
                   'enrollment_digest':self._native_digest,'reader_digest':self._read_digest}
        with self.installation.lease(request) as lease:
            proof = checked_personal_installation(lease, request)
            if not lease.check_components(self.components()):
                raise ValueError('PERSONAL_READ_ONLY_COMPONENT_CHANGED')
            self.current._capture(self.clock())
            result = operation()
            self._verify()
            if not lease.check(proof) or not lease.check_components(self.components()):
                raise ValueError('PERSONAL_READ_ONLY_ACCEPTANCE_CHANGED')
            return result

    def read_committed(self, account_id, epoch):
        if (account_id,epoch) != (self.account,self.epoch):
            raise ValueError('PERSONAL_READ_ONLY_ACCOUNT_SCOPE')
        return self.admitted(lambda:self.reader.read_committed(account_id,epoch))

    def verify(self, payload, **context):
        if (context.get('account_id'),context.get('epoch')) != (self.account,self.epoch):
            raise ValueError('PERSONAL_READ_ONLY_ACCOUNT_SCOPE')
        return self.admitted(lambda:self.reader.verify(payload,**context))

    def preflight(self):
        return self.read_committed(self.account,self.epoch)

    def verify_control_bridge(self, bridge):
        return False
