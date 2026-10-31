"""One-shot bounded driver of the existing installed personal runtime.

No provider, account, authority or process defaults. The 60-second grant includes
an eight-second Stop reserve: this never extends expired financial authority.
No successful zero-trade claim can be made without accepted observations.
"""
from contextlib import nullcontext
from threading import Event, RLock
from time import perf_counter

from app.investment.alpaca_iex import IEXFeed
from app.services.paper_financial_replay import body, strict
from app.services.personal_paper_runtime import PersonalEnrolledRuntime
from app.services.quality_dips_iex_input import IEXPaperQuotes
from app.services.quality_dips_publication_reader import QualityDipsPublicationReader

from scripts.observation_runtime.personal_coordination_store import NativePersonalCoordinationImages
from scripts.observation_runtime.personal_local_authority import (
    NativePersonalOperatorAuthority,
    NativePersonalRuntimeAuthority,
)
from scripts.observation_runtime.personal_market_inputs import NativePersonalMarketInputs
from scripts.observation_runtime.personal_writer_ownership import NativePersonalWriterOwnership


class PersonalCommissioningRunner:
    def __init__(self, *, runtime=None, source=None, shutdown_evidence=None):
        if (type(runtime) is not PersonalEnrolledRuntime or type(source) is not IEXPaperQuotes
                or type(source.feed) is not IEXFeed
                or type(source.decision_reader) is not QualityDipsPublicationReader
                or source.authority is None
                or type(runtime.runtime.authority) is not NativePersonalRuntimeAuthority
                or runtime.runtime.authority.source is not source
                or type(runtime.runtime.engine.source_authority) is not NativePersonalMarketInputs
                or runtime.runtime.engine.source_authority.source is not source
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
                       runtime.installation.identity, runtime.runtime.ownership, self.images, runtime.runtime.authority,
                       runtime.runtime.engine.source_authority)
        self.used = False
        self.stop_requested = Event()
        self.control = None
        self._control = None
        self.status_lock = RLock()
        self.stop_mode = 'SHUTDOWN_FLATTEN'
        self.control_refused = False
        self.progress = {'schema': 'QD_CONTROL_STOP_V1', 'phase': 'IDLE', 'outcome': None}

    def bind_control(self, bridge):
        from app.services.quality_dips_stop_bridge import PaperStopBridge
        if (self.used or self.control is not None or type(bridge) is not PaperStopBridge
                or bridge.runtime is not self.runtime or bridge.runner is not self
                or bridge.evidence is not self.evidence):
            raise ValueError('PERSONAL_DRIVER_CONTROL_BINDING')
        self.control = self._control = bridge

    def control_status(self):
        self._verify_ports()
        with self.status_lock:
            return strict(body(self.progress))

    def refuse_control(self):
        """Latch failed action verification without publishing financial effects."""
        with self.status_lock:
            self.control_refused = True
            self.progress = {'schema': 'QD_CONTROL_STOP_V1', 'phase': 'REFUSED', 'outcome': None}
        self.runtime.runtime.engine.entry_admission_closed = True
        self.runtime.runtime.engine.dispatch_closed = True
        self.stop_requested.set()
        self.runtime.runtime.stopped.set()

    def request_stop(self, mode='SHUTDOWN_FLATTEN'):
        """UI thread closes admission; only the running driver performs writes."""
        self._verify_ports()
        if mode not in ('SHUTDOWN_FLATTEN', 'EMERGENCY'):
            raise ValueError('PERSONAL_DRIVER_STOP_MODE')
        with self.status_lock:
            if self.control_refused:
                raise ValueError('PERSONAL_DRIVER_CONTROL_REFUSED')
            if self.progress['phase'] == 'FINISHED':
                return 'STOP_REQUESTED'
            if mode == 'EMERGENCY':
                self.stop_mode = mode
                self.runtime.runtime.engine.dispatch_closed = True
            self.progress = {'schema': 'QD_CONTROL_STOP_V1', 'phase': 'IN_PROGRESS', 'outcome': None}
        self.stop_requested.set()
        self.runtime.runtime.engine.entry_admission_closed = True
        self.runtime.runtime.stopped.set()
        return 'STOP_REQUESTED'

    def _verify_ports(self):
        if self.control is not self._control or self.evidence is not self.source or any(a is not b for a, b in zip(self._ports,
                (self.runtime, self.source, self.source.feed, self.source.decision_reader,
                 self.source.authority, self.runtime.installation.identity,
                 self.runtime.runtime.ownership, self.runtime.runtime.engine.ledger.images,
                 self.runtime.runtime.authority, self.runtime.runtime.engine.source_authority), strict=True)):
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
        stop_elapsed = None
        authority.verify(request)
        if self.source.session_id != native['session_id']:
            raise ValueError('PERSONAL_COMMISSIONING_SOURCE_SESSION')
        market = r.engine.source_authority
        market.bind_session(grant['runtime_grant']['engine_grant'])
        self.input_preflight = strict(body(market.preflight()))
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
            stop_started = perf_counter()
            r.engine.entry_admission_closed = True
            r.stopped.set()
            try:
                self._verify_ports()
                if self.control_refused:
                    raise ValueError('PERSONAL_DRIVER_CONTROL_REFUSED')
                if not started:
                    raise ValueError('PERSONAL_SESSION_START_UNACKNOWLEDGED_NO_REPLAY')
                # Expiry never grants a new session or a financial exception.
                authority.verify(request)
                self.images.begin_reserved_stop()
                self._budget('STOP')
                # HTTP/UI requests never execute financial work on their worker.
                # Recheck the same existing action lease on the driver thread.
                mode = self.stop_mode
                with self.control.authorized(mode) if self.control is not None else nullcontext():
                    if mode == 'EMERGENCY':
                        result = {'status': owner.stop(mode=mode), 'position_state': 'UNVERIFIED'}
                    else:
                        kwargs = {'owned_close': self.control.owned_close} if self.control is not None else {}
                        result = owner.stop(mode=mode, evidence=self.evidence, **kwargs)
                    authority.verify(request)
            except (ValueError, OSError, KeyError, TypeError) as exc:
                reason = reason or str(exc)[:160]
                r.engine.dispatch_closed = True
                r.halted = owner.failed = True
                result = {'status': 'SHUTDOWN_INCOMPLETE', 'position_state': 'UNKNOWN',
                          'process_shutdown_allowed': False}
            stop_elapsed = perf_counter()-stop_started
            if not 0 <= stop_elapsed <= 8:
                reason = reason or 'PERSONAL_STOP_EIGHT_SECOND_BUDGET_EXCEEDED'
                r.engine.dispatch_closed = True
                r.halted = owner.failed = True
                # A timing failure cannot undo an acknowledged financial exit.
                # Preserve its fields and classify the overall shutdown honestly.
                result = {**result, 'financial_status':result['status'], 'status':'SHUTDOWN_INCOMPLETE',
                          'reason':'PERSONAL_STOP_EIGHT_SECOND_BUDGET_EXCEEDED'}
            with self.status_lock:
                self.progress = {'schema': 'QD_CONTROL_STOP_V1', 'phase': 'FINISHED',
                                 'outcome': strict(body(result))}
        return {'schema': 'PERSONAL_COMMISSIONING_RESULT_V1', 'accepted_observations': observations,
                'completed': reason is None and observations > 0 and result.get('status') == 'FLATTENED',
                'reason': reason or ('NO_ACCEPTED_CURRENT_OBSERVATIONS' if not observations else None),
                'shutdown': result, 'stop_elapsed_seconds':stop_elapsed, 'stop_budget_seconds':8,
                'stop_measurement_scope':'DRIVER_THROUGH_POST_STOP_AUTHORITY', 'automatic_restart_allowed': False}
