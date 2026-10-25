"""Default-refusing V3 composition; no credentials, paths, providers or startup hook.

Authority/ownership/clock/custody are accepted injected dependencies, never local
files masquerading as approval. Existing strict/manual contracts are untouched.
The current FS2/FS3 autonomous implementation is disposable-only; enrolled local
activation explicitly refuses until an accepted autonomous native contract exists.
"""
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from threading import Event, Lock, RLock
from zoneinfo import ZoneInfo

from app.services.paper_financial_replay import body, digest, strict

PROFILE = "AUTONOMOUS_PAPER_ONLY_V1"


class AutonomousRuntime:
    def __init__(self, *, enrollment=None, engine=None, reader=None, reports=None,
                 authority=None, ownership=None, clock=None, custody=None):
        if any(x is None for x in (enrollment, engine, reader, reports, authority, ownership, clock, custody)):
            raise ValueError("RUNTIME_ACCEPTED_DEPENDENCIES_REQUIRED")
        self.enrollment = strict(body(enrollment))
        e = self.enrollment
        if (set(e) != {"schema", "profile", "scope", "reader_enrollment", "process_identity", "writer_roster", "disposable_root"}
                or e["schema"] != "QD_AUTO_LOCAL_RUNTIME_V3" or e["profile"] != PROFILE
                or e["scope"] not in ("DISPOSABLE", "LOCAL_ENROLLED")
                or type(e["process_identity"]) is not dict
                or set(e["process_identity"]) != {"pid", "created", "image"}
                or any(type(e["process_identity"][k]) is not int or e["process_identity"][k] <= 0 for k in ("pid", "created"))
                or type(e["process_identity"]["image"]) is not str or not e["process_identity"]["image"]
                or e["writer_roster"] != ["decision", "source", "projection", "report", "coordination"]):
            raise ValueError("RUNTIME_SCOPE_REQUIRED")
        # Do not relabel FS2_TEST_PIN_V1 or financial fixture grants operational.
        if e["scope"] != "DISPOSABLE":
            raise ValueError("ENROLLED_AUTONOMOUS_NATIVE_CONTRACT_NOT_ACCEPTED")
        root = Path(e["disposable_root"]).absolute()
        diagnostics = Path(__file__).resolve().parents[3] / "logs/diagnostics"
        paths = [engine.ledger.path, engine.publication.store.output.root if engine.publication else root,
                 reports.archive.output.root, *reader.port.paths]
        if (root.parent != diagnostics or root.drive.upper() != "D:"
                or not root.name.startswith(("qd-auto-runtime-", "qd-http-browser-runtime-"))
                or any(p.is_symlink() or p.is_junction() for p in [root, *root.parents])
                or any(not Path(p).absolute().is_relative_to(root) for p in paths)):
            raise ValueError("RUNTIME_DISPOSABLE_CONFINEMENT_REQUIRED")
        self.engine, self.reader, self.reports = engine, reader, reports
        self.authority, self.ownership, self.clock, self.custody = authority, ownership, clock, custody
        if (engine.publication is None or reports.store is not engine.publication.store
                or body(reader.enrollment) != body(e["reader_enrollment"])
                or reader.enrollment["epoch"] != engine.ledger.manifest["epoch"]):
            raise ValueError("RUNTIME_COMPONENT_BINDING_MISMATCH")
        self.gate, self.stopped = RLock(), Event()
        self.feed_lock = Lock()
        self.run_done = Event()
        self.run_done.set()
        self.grant, self.last_clock, self.sequence, self.seen = None, None, 0, {}
        self.halted = True  # Never resume on construction/restart.

    def _now(self):
        sample = strict(body(self.clock.sample()))
        if (set(sample) != {"schema", "utc", "monotonic_ns", "uncertainty_ms", "source_id"}
                or sample["schema"] != "QD_AUTO_CLOCK_V3" or type(sample["source_id"]) is not str or not sample["source_id"]
                or any(type(sample[k]) is not int for k in ("utc", "monotonic_ns", "uncertainty_ms"))
                or sample["utc"] <= 0 or sample["monotonic_ns"] < 0
                or not 0 <= sample["uncertainty_ms"] <= 1000
                or sample["utc"] != self.engine.clock()):
            raise ValueError("RUNTIME_CLOCK_UNVERIFIED")
        self._proof("CLOCK", {"enrollment_digest": digest(self.enrollment), "sample": sample}, sample["utc"])
        if self.last_clock:
            wall = sample["utc"] - self.last_clock["utc"]
            mono = (sample["monotonic_ns"] - self.last_clock["monotonic_ns"]) / 1_000_000_000
            if wall < 0 or mono < 0 or abs(wall - mono) > 2:
                raise ValueError("RUNTIME_CLOCK_DISCONTINUITY")
        self.last_clock = sample
        return sample["utc"]

    def _proof(self, kind, request, now):
        proof = strict(body(self.authority.verify(kind, request, now=now)))
        if (set(proof) != {"schema", "kind", "verified", "binding", "scope", "issuer_id"}
                or proof["schema"] != "QD_AUTO_LOCAL_AUTHORITY_V3" or proof["kind"] != kind
                or proof["verified"] is not True or proof["scope"] != self.enrollment["scope"]
                or proof["binding"] != digest(request) or type(proof["issuer_id"]) is not str or not proof["issuer_id"]):
            raise ValueError("RUNTIME_AUTHORITY_REFUSED")

    @contextmanager
    def _admission(self, now):
        request = {"enrollment": self.enrollment, "grant": self.grant}
        self._proof("SESSION", request, now)
        with self.ownership.lease(request, now=now) as lease:
            owner = strict(body(lease.snapshot))
            if (owner.get("schema") != "QD_AUTO_WRITERS_V3" or owner.get("verified") is not True
                    or body(owner.get("process_identity")) != body(self.enrollment["process_identity"])
                    or owner.get("writer_roster") != self.enrollment["writer_roster"]
                    or body(owner.get("resources")) != body(self.enrollment["reader_enrollment"])
                    or owner.get("unknown_writers") != []):
                raise ValueError("RUNTIME_WRITERS_UNVERIFIED")
            current = strict(body(self.custody.current(request, now=now)))
            self._proof("CURRENT", current, now)
            store = self.engine.publication.store
            if (current.get("schema") != "QD_AUTO_CURRENT_V3" or current.get("status") != "ACKNOWLEDGED"
                    or body(current.get("source")) != body(store.trust.current())
                    or body(current.get("reports")) != body(self.reports.archive.trust.current())
                    or current.get("enrollment_digest") != digest(self.enrollment)
                    or type(current.get("observed_at")) is not int
                    or type(current.get("expires_at")) is not int
                    or not 0 <= now - current["observed_at"] <= 5
                    or not now <= current["expires_at"] <= current["observed_at"] + 5):
                raise ValueError("RUNTIME_CUSTODY_UNVERIFIED")
            audit = self.engine.reconcile()
            history = self.reports.history()
            if ((not history and audit["source_revision"] != 0)
                    or (history and history[-1]["report"]["source"]["revision"] != audit["source_revision"])):
                raise ValueError("RUNTIME_REPORT_SOURCE_INCOMPLETE")
            if lease.check(owner, now) is not True:
                raise ValueError("RUNTIME_OWNERSHIP_CHANGED")
            yield
            if lease.check(owner, self._now()) is not True:
                raise ValueError("RUNTIME_OWNERSHIP_CHANGED")

    def _publish_report(self, now):
        day = datetime.fromtimestamp(now, ZoneInfo(self.engine.ledger.manifest["timezone"])).date().isoformat()
        return self.reports.publish(day, now)

    def start(self, grant):
        with self.gate:
            g = strict(body(grant))
            if (set(g) != {"schema", "profile", "enrollment_digest", "engine_grant", "max_observations"}
                    or g["schema"] != "QD_AUTO_LOCAL_SESSION_V3" or g["profile"] != PROFILE
                    or g["enrollment_digest"] != digest(self.enrollment)
                    or type(g["max_observations"]) is not int or not 1 <= g["max_observations"] <= 128):
                raise ValueError("RUNTIME_SESSION_SCOPE_REQUIRED")
            if self.grant is not None:
                raise ValueError("RUNTIME_ALREADY_STARTED")
            self.grant = g
            started = False
            try:
                now = self._now()
                with self._admission(now):
                    self.engine.start(g["engine_grant"])
                    started = True
                    self._publish_report(now)
                self.halted = False
                self.sequence, self.seen = 0, {}
                self.stopped.clear()
                return "RUNNING"
            except (OSError, ValueError, KeyError, TypeError):
                if started:
                    self._incomplete()
                else:
                    self.grant = None
                raise

    def _incomplete(self):
        self.halted = True
        self.stopped.set()
        self.engine.entry_admission_closed = self.engine.dispatch_closed = True
        try:
            with self.engine.ledger.connect() as db:
                self.engine._append(db, "STOP_INCOMPLETE", self.engine.grant)
        except (OSError, ValueError):
            pass  # A bad clock cannot be used to rewrite continuity evidence.
        self.engine.grant = None

    def accept(self, observation):
        with self.gate:
            if self.halted or self.grant is None or self.stopped.is_set():
                raise ValueError("RUNTIME_NOT_RUNNING")
            frame = strict(body(observation))
            try:
                now = self._now()
                if (set(frame) != {"schema", "session_id", "sequence", "observed_at", "connected", "request"}
                        or frame["schema"] != "QD_AUTO_OBSERVATION_V3"
                        or frame["session_id"] != self.grant["engine_grant"]["session_id"]
                        or type(frame["sequence"]) is not int or frame["sequence"] < 1
                        or type(frame["observed_at"]) is not int or not 0 <= now - frame["observed_at"] <= 5
                        or frame["connected"] is not True):
                    raise ValueError("RUNTIME_FEED_UNVERIFIED_OR_DISCONNECTED")
                request = frame["request"]
                if set(request) != {"bundles", "quotes", "observation"}:
                    raise ValueError("RUNTIME_OBSERVATION_SCHEMA")
                with self._admission(now):
                    self._proof("OBSERVATION", frame, now)
                    prior = self.seen.get(frame["sequence"])
                    if prior:
                        if prior[0] != digest(frame):
                            raise ValueError("RUNTIME_SEQUENCE_CONFLICT")
                        return strict(body(prior[1]))
                    if frame["sequence"] != self.sequence + 1 or frame["sequence"] > self.grant["max_observations"]:
                        raise ValueError("RUNTIME_SEQUENCE_GAP_OR_CAPACITY")
                    result = self.engine.step("runtime:" + digest([frame["session_id"], frame["sequence"]]), **request)
                    if result.get("reason") == "UNKNOWN_OR_CORRUPT":
                        raise ValueError("RUNTIME_FINANCIAL_UNKNOWN")
                    if result.get("filled"):
                        self._publish_report(now)
                    self.sequence = frame["sequence"]
                    self.seen[self.sequence] = (digest(frame), result)
                    return result
            except (OSError, ValueError, KeyError, TypeError):
                self._incomplete()
                raise

    def _catch_up_report(self, now):
        # FS3 cutoffs are exclusive. Publish the next trusted tick once, rather
        # than inventing a future cutoff or a revision on every idle poll.
        history = self.reports.history()
        if history:
            report = history[-1]["report"]
            if (report["source"]["cutoff_revision"] < report["source"]["revision"]
                    and now > report["observed_at"]):
                with self._admission(now):
                    self._publish_report(now)

    def run(self, source):
        """An explicitly started caller supplies the bounded observation source."""
        if not self.feed_lock.acquire(blocking=False):
            raise ValueError("RUNTIME_SOURCE_ALREADY_ATTACHED")
        try:
            with self.gate:
                if self.stopped.is_set():
                    return
                if self.halted:
                    raise ValueError("RUNTIME_NOT_RUNNING")
                self.run_done.clear()
            while not self.stopped.is_set():
                observation = source.next(timeout=0.2)
                if observation is not None:
                    if self.stopped.is_set():
                        break
                    self.accept(observation)
                else:
                    with self.gate:
                        if not self.stopped.is_set():
                            now = self._now()
                            self._proof("SESSION", {"enrollment": self.enrollment, "grant": self.grant}, now)
                            self.engine._grant(now)
                            self._catch_up_report(now)
        except (OSError, ValueError, KeyError, TypeError):
            if self.grant is not None and not self.stopped.is_set():
                self._incomplete()
            raise
        finally:
            self.run_done.set()
            self.feed_lock.release()

    def pause(self):
        self.engine.entry_admission_closed = True
        with self.gate:
            if self.halted:
                raise ValueError("RUNTIME_NOT_RUNNING")
            with self._admission(self._now()):
                return self.engine.pause()

    def stop(self):
        self.stopped.set()
        self.engine.entry_admission_closed = self.engine.dispatch_closed = True
        if not self.run_done.wait(2) or not self.gate.acquire(timeout=2):
            self.halted = True
            return "STOP_INCOMPLETE"
        try:
            if self.grant is None:
                return "STOPPED" if self.engine.status() == "STOPPED" else "STOP_INCOMPLETE"
            with self._admission(self._now()):
                proof = self.ownership.drain({"enrollment": self.enrollment, "grant": self.grant}, now=self._now())
                self._proof("DRAIN", proof, self._now())
                if (type(proof.get("pending")) is not int or proof["pending"] != 0 or proof.get("unknown") is not False
                        or proof.get("enrollment_digest") != digest(self.enrollment)
                        or proof.get("session_id") != self.grant["engine_grant"]["session_id"]):
                    raise ValueError("RUNTIME_DRAIN_UNVERIFIED")
                mode = self.engine.stop()
                if mode != "STOPPED":
                    raise ValueError("RUNTIME_STOP_UNKNOWN")
                self._publish_report(self._now())
                self.halted = True
                self.grant = None
                return mode
        except (OSError, ValueError, KeyError, TypeError):
            self._incomplete()
            return "STOP_INCOMPLETE"
        finally:
            self.gate.release()

    def readonly(self):
        runtime = self
        class Reader:
            def read_committed(self, *args):
                with runtime.gate:
                    return runtime.reader.read_committed(*args)
            def verify(self, *args, **kwargs):
                with runtime.gate:
                    return runtime.reader.verify(*args, **kwargs)
        return Reader()
