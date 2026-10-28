"""One-shot bounded driver of the existing installed personal runtime.

No provider, account, authority or process defaults. The 60-second grant includes
an eight-second Stop reserve: this never extends expired financial authority.
No successful zero-trade claim can be made without accepted observations.
"""
from threading import Event

from app.investment.alpaca_iex import IEXFeed
from app.services.paper_financial_replay import body, strict
from app.services.personal_paper_runtime import PersonalEnrolledRuntime
from app.services.quality_dips_iex_input import IEXPaperQuotes
from app.services.quality_dips_publication_reader import QualityDipsPublicationReader

from scripts.observation_runtime.personal_coordination_store import NativePersonalCoordinationImages
from scripts.observation_runtime.personal_local_authority import NativePersonalOperatorAuthority
from scripts.observation_runtime.personal_writer_ownership import NativePersonalWriterOwnership


class PersonalCommissioningRunner:
    def __init__(self, *, runtime=None, source=None, shutdown_evidence=None):
        if (type(runtime) is not PersonalEnrolledRuntime or type(source) is not IEXPaperQuotes
                or type(source.feed) is not IEXFeed
                or type(source.decision_reader) is not QualityDipsPublicationReader
                or source.authority is None
                or type(runtime.installation.identity) is not NativePersonalOperatorAuthority
                or type(runtime.runtime.ownership) is not NativePersonalWriterOwnership
                or type(runtime.runtime.engine.ledger.images) is not NativePersonalCoordinationImages
                or runtime.runtime.ownership.ledger is not runtime.runtime.engine.ledger):
            raise ValueError('PERSONAL_INSTALLED_RUNNER_DEPENDENCIES_REQUIRED')
        if shutdown_evidence is not None and shutdown_evidence is not source:
            raise ValueError('PERSONAL_COMMISSIONING_ONE_ACCEPTED_L1_SOURCE')
        self.runtime, self.source, self.evidence = runtime, source, source
        self.images = runtime.runtime.engine.ledger.images
        self._ports = (runtime, source, source.feed, source.decision_reader, source.authority,
                       runtime.installation.identity, runtime.runtime.ownership, self.images)
        self.used = False
        self.stop_requested = Event()

    def request_stop(self):
        """UI thread closes admission; only the running driver performs writes."""
        self._verify_ports()
        self.stop_requested.set()
        self.runtime.runtime.engine.entry_admission_closed = True
        self.runtime.runtime.stopped.set()
        return 'STOP_REQUESTED'

    def _verify_ports(self):
        if self.evidence is not self.source or any(a is not b for a, b in zip(self._ports,
                (self.runtime, self.source, self.source.feed, self.source.decision_reader,
                 self.source.authority, self.runtime.installation.identity,
                 self.runtime.runtime.ownership, self.runtime.runtime.engine.ledger.images), strict=True)):
            raise ValueError('PERSONAL_COMMISSIONING_COMPONENT_CHANGED')

    def _budget(self, phase):
        # Conservative hard allocation, not a claim that every future schema or
        # provider payload fits. Each native publication also enforces the cap.
        self.images.require_operation_capacity(commits=32, growth_bytes=256*1024)
        cut = self.runtime.financial.cut()
        entries, reports = len(cut['source']['entries']), len(cut['reports']['reports'])
        source_room, report_room = (2, 5) if phase == 'RUN' else (1, 3)
        if entries + source_room > 128 or reports + report_room > 128:
            raise ValueError('PERSONAL_FINANCIAL_STOP_CAPACITY_REQUIRED')

    def run(self, grant):
        if self.used or self.stop_requested.is_set():
            raise ValueError('PERSONAL_COMMISSIONING_RUNNER_ONCE_ONLY')
        self.used = True  # Even a failed attempt requires explicit recovery.
        self._verify_ports()
        owner, r = self.runtime, self.runtime.runtime
        native = strict(body(grant['native_grant']))
        authority = owner.installation.identity
        request = {'scope': 'LOCAL_ENROLLED', 'enrollment': owner.admission.enrollment, 'grant': native}
        observations, reason, result, started = 0, None, None, False
        authority.verify(request)
        if self.source.session_id != native['session_id']:
            raise ValueError('PERSONAL_COMMISSIONING_SOURCE_SESSION')
        now = authority.clock()
        if native['expires_at'] - now <= 8:
            raise ValueError('PERSONAL_NO_BOUNDED_STOP_WINDOW')
        self.images.reserve_stop_capacity(stop_commits=32, stop_bytes=256*1024)
        try:
            self._budget('RUN')
            owner.start(grant)
            started = True
            while not r.stopped.is_set() and not self.stop_requested.is_set():
                authority.verify(request)
                now = authority.clock()
                if now >= native['expires_at'] - 8:
                    break
                frame = self.source.next(timeout=0.2)
                self._verify_ports()
                # Recheck after a slow/disconnected source, before any dispatch.
                authority.verify(request)
                if r.stopped.is_set() or authority.clock() >= native['expires_at'] - 8:
                    break
                with r.ownership.lease(request, now=authority.clock()):
                    self._budget('RUN')
                    if frame is not None:
                        owner.accept(frame)
                        observations += 1
                    else:
                        with owner._action():
                            stamp = r._now()
                            r._proof('SESSION', {'enrollment': r.enrollment, 'grant': r.grant}, stamp)
                            r.engine._grant(stamp)
                            r._catch_up_report(stamp)
                if frame is None:
                    self.stop_requested.wait(0.2)
        except (ValueError, OSError, KeyError, TypeError) as exc:
            reason = str(exc)[:160]
        finally:
            r.engine.entry_admission_closed = True
            r.stopped.set()
            try:
                self._verify_ports()
                if not started:
                    raise ValueError('PERSONAL_SESSION_START_UNACKNOWLEDGED_NO_REPLAY')
                # Expiry never grants a new session or a financial exception.
                authority.verify(request)
                self.images.begin_reserved_stop()
                self._budget('STOP')
                result = owner.stop(mode='SHUTDOWN_FLATTEN', evidence=self.evidence)
            except (ValueError, OSError, KeyError, TypeError) as exc:
                reason = reason or str(exc)[:160]
                r.engine.dispatch_closed = True
                r.halted = owner.failed = True
                result = {'status': 'SHUTDOWN_INCOMPLETE', 'position_state': 'UNKNOWN',
                          'process_shutdown_allowed': False}
        return {'schema': 'PERSONAL_COMMISSIONING_RESULT_V1', 'accepted_observations': observations,
                'completed': reason is None and observations > 0 and result.get('status') == 'FLATTENED',
                'reason': reason or ('NO_ACCEPTED_CURRENT_OBSERVATIONS' if not observations else None),
                'shutdown': result, 'automatic_restart_allowed': False}
