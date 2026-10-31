"""V5 LOCAL_ENROLLED contract path, confined disposable execution only.

Reuses V3 and FS1-FS3 without converting test pins into operational authority.
No installed entry, issuer, account inception, provider or operational backend.
"""

import importlib.util
from contextlib import contextmanager, nullcontext
from pathlib import Path
from threading import get_ident

from app.investment.quality_dips_operational_contract import exact
from app.services.paper_financial_replay import body, digest, strict
from app.services.quality_dips_autonomous_enrollment import ROLES, validate_enrollment
from app.services.quality_dips_autonomous_integration import AutonomousNativePublication


class NativeFinancialBinding:
    """Native publication/replay/report port over explicitly disposable FS2 bytes.

    Native identity, complete immutable source, independent arithmetic, FS3 and
    SQL pending-ACK consistency are checked by the existing selected read port.
    Current-pin authenticity and writer exclusion remain injected dependencies.
    """

    def __init__(self, *, enrollment=None, runtime=None, test_root=None, release_digest=None):
        if any(v is None for v in (enrollment, runtime, test_root, release_digest)):
            raise ValueError("V5_ACCEPTED_COMPONENT_BINDINGS_REQUIRED")
        self.e = body(validate_enrollment(enrollment))
        self.runtime, self.root, self.release = runtime, Path(test_root).absolute(), release_digest
        repo = Path(__file__).resolve().parents[3]
        if (
            self.root.parent != repo / "logs/diagnostics"
            or not self.root.name.startswith(("qd-auto-runtime-", "qd-http-browser-runtime-"))
            or self.root.drive.upper() != "D:"
            or runtime.enrollment["scope"] != "DISPOSABLE"
            or any(p.is_symlink() or p.is_junction() for p in (self.root, *self.root.parents))
        ):
            raise ValueError("V5_DISPOSABLE_EXECUTION_DOMAIN_REQUIRED")
        spec = importlib.util.spec_from_file_location(
            "v5_bound_native", repo / "scripts/volume_inspector/snapshot_store.py"
        )
        self.native = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.native)
        self.engine, self.reader, self.reports = runtime.engine, runtime.reader, runtime.reports
        self.delegate = self.engine.publication
        if type(self.delegate) is not AutonomousNativePublication:
            raise ValueError("V5_EXISTING_AUTONOMOUS_PUBLICATION_REQUIRED")
        self.store = self.delegate.store
        self.actor = None
        self._constructing = True
        self.components()
        self._constructing = False

    @property
    def enrollment(self):
        return strict(self.e)

    def components(self):
        e, r = self.enrollment, self.runtime
        manifest = self.engine.ledger.manifest
        if (
            r.engine is not self.engine
            or r.reader is not self.reader
            or r.reports is not self.reports
            or self.engine.publication is not (self.delegate if self._constructing else self)
            or self.reports.store is not self.store
            or self.delegate.store is not self.store
            or e["account_id"] != self.reader.enrollment["account_id"]
            or e["epoch"] != manifest["epoch"]
            or e["epoch"] != self.reader.enrollment["epoch"]
            or e["policy_digest"] != digest(manifest["autonomous_policy"])
            or e["inception_digest"] != digest(manifest)
            or e["release_digest"] != self.release
            or body(self.reader.enrollment) != body(r.enrollment["reader_enrollment"])
        ):
            raise ValueError("V5_COMPONENT_ACCOUNT_EPOCH_POLICY_RELEASE_MISMATCH")
        actual = {
            "source": Path(self.store.output.root),
            "projection": Path(self.store.projection.output.root),
            "report": Path(self.reports.archive.output.root),
            "coordination": Path(self.engine.ledger.path).parent,
        }
        if tuple(str(actual[k]) for k in ("source", "projection", "report")) != tuple(
            str(p) for p in self.reader.port.paths
        ):
            raise ValueError("V5_READER_RESOURCE_MISMATCH")
        for role in ROLES:
            path = Path(e["resources"][role]["path"])
            if (
                not path.is_relative_to(self.root)
                or path.drive.upper() != "D:"
                or any(p.is_symlink() or p.is_junction() for p in (path, *path.parents))
                or role in actual
                and path != actual[role]
            ):
                raise ValueError("V5_COMPONENT_RESOURCE_MISMATCH")
            with self.native.w.WindowsOutput(str(path)) as out:
                if (
                    self.native.native.file_identity(out.root_handle)
                    != e["resources"][role]["native_id"]
                ):
                    raise ValueError("V5_NATIVE_RESOURCE_IDENTITY_MISMATCH")
                if role in ("control", "custody") and list(path.iterdir()):
                    raise ValueError("V5_UNEXPECTED_CONTROL_OR_CUSTODY_FILE")
        return True

    def cut(self):
        self.components()
        p = self.reader.read_committed(self.enrollment["account_id"], self.enrollment["epoch"])
        if (
            self.reader.verify(
                p, account_id=p["account_id"], epoch=p["epoch"], now=p["observed_at"]
            )["verified"]
            is not True
        ):
            raise ValueError("V5_NATIVE_REPLAY_REPORT_REFUSED")
        # Keep original test pins intact and visibly typed. This envelope is NOT
        # an operational pin conversion. The immutable native records stay FS2.
        return {
            "schema": "QD_AUTO_NATIVE_FINANCIAL_CUT_V5",
            "execution_domain": "DISPOSABLE_TEST",
            "enrollment_digest": digest(self.enrollment),
            "source_revision": p["source_revision"],
            "state_digest": digest(p["state"]),
            "source": self.store.trust.current(),
            "reports": self.reports.archive.trust.current(),
        }

    def verify(self, enrollment, current, now=None, *, scope=None):
        if now is None and scope is None:
            return self.verify_records(enrollment, current)
        if scope != "LOCAL_ENROLLED" or body(enrollment) != self.e or now != self.engine.clock():
            raise ValueError("V5_NATIVE_ENROLLMENT_SCOPE_OR_CLOCK")
        cut = self.cut()
        if (
            current["financial_digest"] != digest(cut)
            or current["revision"] != cut["source_revision"]
            or current["acknowledged_revision"] != cut["source_revision"]
        ):
            raise ValueError("V5_CURRENT_FINANCIAL_CUT_MISMATCH")
        return True

    @contextmanager
    def action(self):
        if self.actor is not None:
            raise ValueError("V5_FINANCIAL_ACTION_ALREADY_ACTIVE")
        self.components()
        self.actor = get_ident()
        try:
            yield
        finally:
            self.actor = None

    def publish(self, command, receipt, state):
        if self.actor != get_ident():
            raise ValueError("V5_ADMITTED_FINANCIAL_ACTION_REQUIRED")
        self.components()
        return self.delegate.publish(command, receipt, state)

    def verify_records(self, records, state):
        self.components()
        return self.delegate.verify(records, state)


class EnrolledAutonomousRuntime:
    """V4-before/V3-action/V4-after under one authenticated writer lease.

    This version admits only a confined disposable execution domain. Its public
    LOCAL_ENROLLED scope exercises enrollment semantics, not accepted real trust.
    The inner V3/FS2 test schemas remain explicit and unchanged.
    """

    financial_types = (NativeFinancialBinding,)
    execution_domain = "DISPOSABLE_TEST"

    def __init__(self, *, runtime=None, admission=None, financial=None):
        if any(v is None for v in (runtime, admission, financial)):
            raise ValueError("V5_ENROLLED_DEPENDENCIES_REQUIRED")
        if (
            type(financial) not in self.financial_types
            or financial.runtime is not runtime
            or admission.native is not financial
            or admission.scope != "LOCAL_ENROLLED"
            or body(admission.enrollment) != body(financial.enrollment)
        ):
            raise ValueError("V5_ENROLLED_COMPONENT_BINDING_MISMATCH")
        financial.components()
        self.runtime, self.admission, self.financial = runtime, admission, financial
        self._enrollment = body(
            {
                "schema": "QD_AUTO_NATIVE_RUNTIME_V5",
                "scope": "LOCAL_ENROLLED",
                "execution_domain": self.execution_domain,
                "native_enrollment": admission.enrollment,
                "runtime_digest": digest(runtime.enrollment),
            }
        )
        self.grant = None
        self.failed = False

    @property
    def enrollment(self):
        return strict(self._enrollment)

    @contextmanager
    def _action(self, *, readonly=False):
        r, a = self.runtime, self.admission
        with r.gate, a.lock:
            if self.grant is None:
                raise ValueError("V5_SESSION_NOT_STARTED")
            request = {
                "scope": a.scope,
                "enrollment": a.enrollment,
                "grant": self.grant["native_grant"],
            }
            try:
                if digest(r.enrollment) != self.enrollment["runtime_digest"]:
                    raise ValueError("V5_RUNTIME_ENROLLMENT_CHANGED")
                self.financial.components()
                with a.ownership.lease(request, r.engine.clock()) as lease:
                    owner = a._checked(lease, r.engine.clock())
                    with a.admitted(request["grant"]):
                        pass
                    # The ownership lease remains held across both financial cuts.
                    with nullcontext() if readonly else self.financial.action():
                        yield
                    if body(a._checked(lease, r.engine.clock())) != body(owner):
                        raise ValueError("V5_WRITER_LEASE_CHANGED")
                    with a.admitted(request["grant"]):
                        pass
            except (OSError, ValueError, KeyError, TypeError):
                if not readonly:
                    self.failed = True
                    r._incomplete()
                raise

    def start(self, grant):
        g = strict(body(grant))
        exact(
            g,
            "QD_AUTO_NATIVE_RUNTIME_SESSION_V5",
            {"enrollment_digest", "native_grant", "runtime_grant"},
        )
        if self.grant is not None or g["enrollment_digest"] != digest(self.enrollment):
            raise ValueError("V5_SESSION_BINDING_OR_RESTART_REFUSED")
        inner = g["runtime_grant"]["engine_grant"]
        outer = g["native_grant"]
        if (
            inner["schema"] != "QD_AUTO_ENGINE_SESSION_V5"
            or inner["epoch"] != self.admission.enrollment["epoch"]
            or inner["session_id"] != outer["session_id"]
            or inner["issued_at"] != outer["issued_at"]
            or inner["expires_at"] != outer["expires_at"]
        ):
            raise ValueError("V5_NO_FIXTURE_MANUAL_OR_FOREIGN_SESSION")
        self.admission.reserve_session(outer)
        self.grant = g
        with self._action():
            return self.runtime.start(g["runtime_grant"])

    def preview(self, observation):
        r = self.runtime
        if r.stopped.is_set() or r.halted or r.grant is None:
            raise ValueError('V5_NEW_CANDIDATES_CLOSED')
        with self._action(readonly=True):
            now = r._now()
            frame = r._checked_frame(observation, now)
            if frame['sequence'] != r.sequence + 1 or frame['sequence'] > r.grant['max_observations']:
                raise ValueError('V5_PREVIEW_SEQUENCE_NOT_NEW')
            r._proof('SESSION', {'enrollment': r.enrollment, 'grant': r.grant}, now)
            r._proof('OBSERVATION', frame, now)
            decision = r.engine.preview('runtime:' + digest([frame['session_id'], frame['sequence']]), **frame['request'])
            return {'schema': 'QD_AUTO_RUNTIME_PREVIEW_V5', 'runtime_digest': digest(self.enrollment),
                    'observation_digest': digest(frame), 'decision': decision, 'authority_granted': False}

    def accept(self, observation, *, expected_command_digest=None):
        if self.runtime.stopped.is_set():
            raise ValueError("V5_NEW_CANDIDATES_CLOSED")
        with self._action():
            if expected_command_digest is None:
                return self.runtime.accept(observation)
            return self.runtime.accept(observation, expected_command_digest=expected_command_digest)

    def pause(self):
        self.runtime.engine.entry_admission_closed = True
        with self._action():
            return self.runtime.pause()

    def stop(self, *, mode="EMERGENCY", evidence=None, owned_close=None):
        if mode == "SHUTDOWN_FLATTEN":
            from app.services.quality_dips_shutdown import flatten_and_stop
            return flatten_and_stop(self, evidence, owned_close)
        if mode != "EMERGENCY":
            raise ValueError("V5_EXPLICIT_SHUTDOWN_MODE_REQUIRED")
        self.runtime.engine.entry_admission_closed = self.runtime.engine.dispatch_closed = True
        self.runtime.stopped.set()
        if self.failed:
            return "STOP_INCOMPLETE"
        if not self.runtime.run_done.wait(2):
            self.failed = True
            self.runtime.halted = True
            return "STOP_INCOMPLETE"
        try:
            with self._action():
                result = self.runtime.stop()
                if result != "STOPPED":
                    raise ValueError("V5_STOP_INCOMPLETE")
                return result
        except (OSError, ValueError, KeyError, TypeError):
            return "STOP_INCOMPLETE"

    def run(self, source):
        r = self.runtime
        if not r.feed_lock.acquire(blocking=False):
            raise ValueError("V5_FEED_ALREADY_ATTACHED")
        try:
            if self.grant is None or r.halted:
                raise ValueError("V5_SESSION_NOT_RUNNING")
            r.run_done.clear()
            while not r.stopped.is_set():
                frame = source.next(timeout=0.2)
                if r.stopped.is_set():
                    break
                if frame is not None:
                    self.accept(frame)
                else:
                    with self._action():
                        now = r._now()
                        r._proof("SESSION", {"enrollment": r.enrollment, "grant": r.grant}, now)
                        r.engine._grant(now)
                        r._catch_up_report(now)
        except (OSError, ValueError, KeyError, TypeError):
            self.failed = True
            if self.grant is not None:
                r._incomplete()
            raise
        finally:
            r.run_done.set()
            r.feed_lock.release()

    def readonly(self):
        outer = self

        class Reader:
            def read_committed(self, *args):
                with outer._action(readonly=True):
                    return outer.runtime.reader.read_committed(*args)

            def verify(self, *args, **kwargs):
                with outer._action(readonly=True):
                    return outer.runtime.reader.verify(*args, **kwargs)

        return Reader()
