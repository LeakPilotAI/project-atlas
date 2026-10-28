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
