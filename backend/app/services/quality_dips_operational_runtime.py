"""Uninstalled operational composition. No trust discovery, provisioning or startup.

Installation authority is an injected trust anchor, not a JSON file or environment
flag. Tests of this path do not install that anchor or accept any release gate.
"""

from contextlib import contextmanager
from pathlib import Path

from app.services.paper_financial_replay import body, digest, strict
from app.services.quality_dips_autonomous_binding import (
    EnrolledAutonomousRuntime,
    NativeFinancialBinding,
)
from app.services.quality_dips_autonomous_enrollment import (
    ROLES,
    AutonomousNativeEnrollment,
    validate_enrollment,
)
from app.services.quality_dips_autonomous_integration import AutonomousNativePublication
from app.services.quality_dips_autonomous_runtime import AutonomousRuntime


class OperationalFinancialBinding(NativeFinancialBinding):
    """V5 action/cut protocol over the distinct operational codec, never FS2 test pins."""

    def __init__(self, *, enrollment, runtime, store, native_reader, release_digest):
        self.e = body(validate_enrollment(enrollment))
        self.runtime, self.release = runtime, release_digest
        self.engine, self.reader, self.reports = runtime.engine, runtime.reader, runtime.reports
        self.store, self.native_reader = store, native_reader
        self.delegate, self.actor = self.engine.publication, None
        self.components()

    def components(self):
        e, r = self.enrollment, self.runtime
        if (
            r.enrollment["scope"] != "LOCAL_ENROLLED"
            or type(self.delegate) is not AutonomousNativePublication
            or self.delegate.store is not self.store
            or self.reports.store is not self.store
            or self.engine.publication not in (self.delegate, self)
            or body(self.store.enrollment) != body(e)
            or body(self.native_reader.enrollment) != body(e)
            or self.store.trust.current().get("schema") != "QD_AUTO_OP_PIN_V1"
            or e["epoch"] != self.engine.ledger.manifest["epoch"]
            or e["inception_digest"] != digest(self.engine.ledger.manifest)
            or e["policy_digest"] != digest(self.engine.ledger.manifest["autonomous_policy"])
            or e["release_digest"] != self.release
            or self.reader.enrollment["schema"] != "QD_AUTO_OP_READ_ENROLLMENT_V1"
            or self.reader.enrollment["account_id"] != e["account_id"]
            or self.reader.enrollment["epoch"] != e["epoch"]
            or body(self.reader.enrollment) != body(r.enrollment["reader_enrollment"])
        ):
            raise ValueError("OP_RUNTIME_COMPONENT_OR_TEST_SUBSTITUTION")
        # Existing-only handle access verifies ACL, reparse/link and exact identity.
        self.native_reader.verify_resources()
        for role in ROLES:
            path = Path(e["resources"][role]["path"])
            if path.drive.upper() != "D:" or any(
                p.is_symlink() or p.is_junction() for p in (path, *path.parents)
            ):
                raise ValueError("OP_RUNTIME_NAMESPACE")
        actual = {
            "source": self.store.output.root,
            "projection": self.store.projection.output.root,
            "report": self.reports.archive.output.root,
            "coordination": self.engine.ledger.path.parent,
        }
        if any(Path(actual[k]) != Path(e["resources"][k]["path"]) for k in actual):
            raise ValueError("OP_RUNTIME_RESOURCE_PATH_MISMATCH")
        return True

    def cut(self):
        self.components()
        p = self.reader.read_committed(self.enrollment["account_id"], self.enrollment["epoch"])
        proof = self.reader.verify(p, account_id=p["account_id"], epoch=p["epoch"], now=p["observed_at"])
        if proof.get('verified') is not True:
            raise ValueError('OP_RUNTIME_PRESENTATION_UNVERIFIED')
        native = self.native_reader.read_committed()
        if native["state"] != p["state"] or len(native["rows"]) != p["source_revision"]:
            raise ValueError("OP_RUNTIME_NATIVE_PRESENTATION_DISAGREEMENT")
        return {
            "schema": "QD_AUTO_NATIVE_FINANCIAL_CUT_V5",
            "execution_domain": "OPERATIONAL_ACCEPTED",
            "enrollment_digest": digest(self.enrollment),
            "source_revision": p["source_revision"],
            "state_digest": digest(p["state"]),
            "source": self.store.trust.current(),
            "reports": self.reports.archive.trust.current(),
        }


class OperationalRuntime(AutonomousRuntime):
    def _validate_resources(self, e, engine, reader, reports):
        if (
            e["scope"] != "LOCAL_ENROLLED"
            or e["disposable_root"] is not None
            or reader.enrollment.get("schema") != "QD_AUTO_OP_READ_ENROLLMENT_V1"
            or engine.publication.store.trust.current().get("schema") != "QD_AUTO_OP_PIN_V1"
        ):
            raise ValueError("OP_RUNTIME_OPERATIONAL_RESOURCES_REQUIRED")


class OperationalEnrolledRuntime(EnrolledAutonomousRuntime):
    financial_types = (OperationalFinancialBinding,)
    execution_domain = "OPERATIONAL_ACCEPTED"

    @contextmanager
    def _action(self, *, readonly=False):
        with self.installation.lease(self.installation_request()) as lease:
            proof = checked_installation(lease, self.installation_request())
            if lease.check_components(self.installation_components()) is not True:
                raise ValueError('OP_RUNTIME_DEPENDENCY_SUBSTITUTION')
            with super()._action(readonly=readonly):
                yield
            if lease.check(proof) is not True or lease.check_components(self.installation_components()) is not True:
                self.failed = True
                self.runtime._incomplete()
                raise ValueError("OP_RUNTIME_INSTALLATION_REVOKED")


def checked_installation(lease, request):
    proof = strict(body(lease.snapshot))
    if (
        set(proof) != {"schema", "domain", "binding", "accepted", "gates", "revoked"}
        or proof["schema"] != "QD_AUTO_ACCEPTED_INSTALLATION_V1"
        or proof["domain"] != "OPERATIONAL_ACCEPTED"
        or proof["accepted"] is not True
        or proof["revoked"] is not False
        or proof["binding"] != digest(request)
        or proof["gates"] != dict.fromkeys(("B1", "C1", "D1", "E1"), "ACCEPTED")
        or lease.check(proof) is not True
    ):
        raise ValueError("OP_RUNTIME_SYNTHETIC_OR_UNACCEPTED_INSTALLATION")
    return proof


def compose_operational(
    *,
    enrollment=None,
    runtime_dependencies=None,
    native_dependencies=None,
    store=None,
    native_reader=None,
    installation=None,
):
    """Consume already installed/accepted ports. This function never installs them.

    The injected installation verifier authenticates the complete component
    binding under a retained lease. A caller-supplied dictionary alone is not
    authorization. No CLI/environment loader or default trust anchor exists.
    """
    if any(
        v is None
        for v in (
            enrollment,
            runtime_dependencies,
            native_dependencies,
            store,
            native_reader,
            installation,
        )
    ):
        raise ValueError("OP_RUNTIME_ACCEPTED_INSTALLATION_REQUIRED")
    e = validate_enrollment(enrollment)

    def request():
        return {
            "schema": "QD_AUTO_RUNTIME_INSTALLATION_V1",
            "enrollment": e,
            "runtime_enrollment": runtime_dependencies["enrollment"],
            "source_pin": store.trust.current(),
            "report_pin": runtime_dependencies["reports"].archive.trust.current(),
        }

    with installation.lease(request()) as lease:
        proof = checked_installation(lease, request())
        ports = {'runtime': dict(runtime_dependencies), 'native': dict(native_dependencies),
                 'store': store, 'reader': native_reader}
        if lease.check_components(ports) is not True:
            raise ValueError('OP_RUNTIME_DEPENDENCY_SUBSTITUTION')
        r = OperationalRuntime(**runtime_dependencies)
        f = OperationalFinancialBinding(
            enrollment=e,
            runtime=r,
            store=store,
            native_reader=native_reader,
            release_digest=e["release_digest"],
        )
        # Native enrollment, sessions and all V3 custody/ownership/clock checks
        # remain active on every action. Construction cannot start a session.
        a = AutonomousNativeEnrollment(enrollment=e, native=f, **native_dependencies)
        r.engine.publication = f
        try:
            result = OperationalEnrolledRuntime(runtime=r, admission=a, financial=f)
            result.installation, result.installation_request = installation, request
            result.installation_components = lambda: {
                'runtime': {k: getattr(r, k) for k in runtime_dependencies},
                'native': {k: getattr(a, k) for k in native_dependencies},
                'store': f.store, 'reader': f.native_reader}
            if lease.check(proof) is not True:
                raise ValueError("OP_RUNTIME_INSTALLATION_CHANGED")
            return result
        except BaseException:
            r.engine.publication = f.delegate
            raise
