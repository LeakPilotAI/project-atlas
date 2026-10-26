"""Source-bound FS1/FS2 writer seam; no authority discovery or startup route.

Existing FS2 test records are supported only in the explicit disposable domain.
An operational perpetual codec/enrollment is deliberately not invented here.
"""
from app.services.paper_financial_replay import (
    FinancialSourceUncertain,
    body,
    digest,
    number,
    strict,
    text,
    validate_manifest,
)
from app.services.quality_dips_unified_writer import EnrolledQualityDipsWriter


class NativeFinancialWriter:
    execution_domain = "DISPOSABLE_TEST"
    pin_schema = "FS2_TEST_PIN_V1"
    def __init__(self, *, store=None, authority=None, manifest=None, execution_domain=None):
        if store is None or authority is None or manifest is None:
            raise ValueError("NATIVE_WRITER_ACCEPTED_COMPONENTS_REQUIRED")
        validate_manifest(manifest)
        if manifest['schema'] == 'PAPER_EPOCH_PERP_OPERATIONAL_V1' and self.execution_domain != 'LOCAL_ENROLLED':
            raise ValueError('NATIVE_WRITER_OPERATIONAL_PARAMETERS_CANNOT_USE_TEST_DOMAIN')
        if execution_domain != self.execution_domain:
            raise ValueError("NATIVE_WRITER_OPERATIONAL_CODEC_NOT_ACCEPTED")
        self.store, self.authority = store, authority
        self.manifest = strict(body(manifest))
        self.binding = {"store": store, "manifest_digest": digest(manifest), "execution_domain": execution_domain}
        self._cut()

    def _cut(self):
        if self.authority.verify_components(self.binding) is not True:
            raise ValueError("NATIVE_WRITER_COMPONENT_AUTHORITY_REQUIRED")
        cut = self.store.verified_cut()
        if cut["pin_schema"] != self.pin_schema or body(cut["manifest"]) != body(self.manifest):
            raise ValueError("NATIVE_WRITER_DOMAIN_OR_ACCOUNT_SUBSTITUTION")
        if self.authority.verify_cut(self.binding, cut) is not True:
            raise ValueError("NATIVE_WRITER_SOURCE_CUT_UNVERIFIED")
        return cut

    def _shape(self, proposal):
        if (type(proposal) is not dict or set(proposal) != {"operation_id", "kind", "command", "source_head", "strategy_ref"}
                or type(proposal["command"]) is not dict):
            raise ValueError("NATIVE_WRITER_EXACT_PROPOSAL_REQUIRED")
        text(proposal["strategy_ref"])
        c = proposal["command"]
        if proposal["operation_id"] != c.get("operation_id") or proposal["kind"] != c.get("kind") or c.get("epoch") != self.manifest["epoch"]:
            raise ValueError("NATIVE_WRITER_COMMAND_SUBSTITUTION")
        return c

    def _margin_authority(self, proposal, cut):
        if proposal["command"].get("schema") in ("PAPER_PERP_MARGIN_ENTRY_V1", "PAPER_PERP_MARGIN_MARK_V1", "PAPER_PERP_IOC_MARGIN_ENTRY_V1"):
            verifier = getattr(self.authority, "verify_margin_policy", None)
            if verifier is None or verifier(self.binding, proposal, cut) is not True:
                raise ValueError("NATIVE_WRITER_ACCEPTED_MARGIN_AUTHORITY_REQUIRED")
        if proposal["command"].get("schema") in ("PAPER_PERP_IOC_ENTRY_V1", "PAPER_PERP_IOC_MARGIN_ENTRY_V1"):
            verifier = getattr(self.authority, "verify_execution_policy", None)
            if verifier is None or verifier(self.binding, proposal, cut) is not True:
                raise ValueError("NATIVE_WRITER_ACCEPTED_EXECUTION_POLICY_REQUIRED")
        if proposal["command"].get("schema") == "PAPER_PERP_LIQUIDATION_V1":
            verifier = getattr(self.authority, "verify_liquidation", None)
            if verifier is None or verifier(self.binding, proposal, cut) is not True:
                raise ValueError("NATIVE_WRITER_ACCEPTED_LIQUIDATION_EVIDENCE_REQUIRED")
        if proposal["command"].get("schema") == "PAPER_PERP_MAKER_FILL_V1":
            verifier = getattr(self.authority, "verify_maker_execution", None)
            if verifier is None or verifier(self.binding, proposal, cut) is not True:
                raise ValueError("NATIVE_WRITER_ACCEPTED_MAKER_QUEUE_EVIDENCE_REQUIRED")

    def preview(self, proposal, observation):
        c = self._shape(proposal)
        cut = self._cut()
        self._margin_authority(proposal, cut)
        if c.get("schema") == "PAPER_PERP_FUNDING_RECOVERY_V1":
            verifier = getattr(self.authority, "verify_recovery", None)
            if verifier is None or verifier(self.binding, proposal, cut) is not True:
                raise ValueError("NATIVE_WRITER_INDEPENDENT_RECOVERY_AUTHORITY_REQUIRED")
        if (proposal["operation_id"] != c.get("operation_id") or proposal["kind"] != c.get("kind")
                or c.get("epoch") != self.manifest["epoch"] or proposal["source_head"] != cut["head"]
                or self.authority.verify_proposal(self.binding, proposal, observation, cut) is not True):
            raise ValueError("NATIVE_WRITER_STRATEGY_OR_SOURCE_UNVERIFIED")
        preview = self.store.preview(c)
        if preview["head"] != cut["head"] or preview["root"] != cut["root"]:
            raise ValueError("NATIVE_WRITER_SOURCE_CHANGED_DURING_PREVIEW")
        return preview

    def verify_proposal(self, proposal, observation):
        command = self._shape(proposal)
        cut = self._cut()
        acknowledged = cut["acknowledged_operations"].get(proposal["operation_id"])
        if acknowledged is not None:
            if acknowledged != digest(command) or self.authority.verify_proposal(self.binding, proposal, observation, cut) is not True:
                raise ValueError("NATIVE_WRITER_CONFLICTING_RETRY")
            return True
        self.preview(proposal, observation)
        return True

    def dispatch(self, proposal, reservation):
        self._shape(proposal)
        cut = self._cut()
        self._margin_authority(proposal, cut)
        if proposal["command"].get("schema") == "PAPER_PERP_FUNDING_RECOVERY_V1":
            verifier = getattr(self.authority, "verify_recovery", None)
            if verifier is None or verifier(self.binding, proposal, cut) is not True:
                raise ValueError("NATIVE_WRITER_INDEPENDENT_RECOVERY_AUTHORITY_REQUIRED")
        if (proposal["source_head"] != cut["head"]
                or self.authority.verify_reservation(self.binding, proposal, reservation, cut) is not True):
            raise ValueError("NATIVE_WRITER_DURABLE_RESERVATION_REQUIRED")
        # Native execution independently rechecks revision and replay arithmetic.
        # Any effect before a missing acknowledgement remains UNKNOWN at custody.
        receipt = self.store.execute(proposal["command"], projection_required=True)
        if receipt.get("fully_acknowledged") is False or receipt.get("status") == "UNKNOWN":
            raise ValueError("NATIVE_WRITER_PUBLICATION_UNKNOWN")
        if self.store.operation_receipt(proposal["operation_id"], digest(proposal["command"])) != receipt:
            raise ValueError("NATIVE_WRITER_ACKNOWLEDGEMENT_MISMATCH")
        if digest(self._cut()["state"]) != receipt["state_digest"]:
            raise ValueError("NATIVE_WRITER_SOURCE_CHANGED_AFTER_ACK")
        return receipt


class OperationalPerpFinancialWriter(NativeFinancialWriter):
    """Explicit operational codec port; no default authority or installation.

    Both the native store's admission lease and the unified portfolio/component
    authority must authenticate every action. A valid schema grants neither.
    """
    execution_domain = "LOCAL_ENROLLED"
    pin_schema = "PERP_AUTO_OP_PIN_V1"

    def __init__(self, **kwargs):
        manifest = kwargs.get("manifest")
        if type(manifest) is not dict or manifest.get("schema") != "PAPER_EPOCH_PERP_OPERATIONAL_V1":
            raise ValueError("OPERATIONAL_PERP_PARAMETERS_REQUIRED")
        super().__init__(**kwargs)


class PerpShutdownCoordinator:
    """Native remaining-quantity exits and FS3 session cut, never process killing.

    The quote port is an accepted bounded cache read, not an implicit provider
    connection. Unified custody must independently verify each shutdown exit.
    Ownership/drain remains external accepted evidence, never inferred from PID.
    """
    def __init__(self, *, writer, books, reports, clock, session_id, started_at):
        from app.services.perp_resting_writer import RestingPerpWriter
        if (type(writer) not in (NativeFinancialWriter, OperationalPerpFinancialWriter, RestingPerpWriter)
                or reports.store is not writer.store or books is None or clock is None
                or type(started_at) is not int or started_at <= 0):
            raise ValueError('PERP_SHUTDOWN_EXACT_COMPONENTS_REQUIRED')
        text(session_id)
        self.writer, self.books, self.reports, self.clock = writer, books, reports, clock
        self.session_id, self.started_at, self.runtime, self.completed = session_id, started_at, None, None

    def bind(self, runtime):
        from app.services.unified_paper_runtime import UnifiedPaperRuntime
        if self.runtime is not None or type(runtime) is not UnifiedPaperRuntime:
            raise ValueError('PERP_SHUTDOWN_SINGLE_RUNTIME_BINDING_REQUIRED')
        self.runtime = runtime
        self._verify()

    def _verify(self):
        if self.runtime is None:
            raise ValueError('PERP_SHUTDOWN_RUNTIME_REQUIRED')
        lane = self.runtime.lanes['HYPERLIQUID']
        binding = {"writer": self.writer, "books": self.books, "reports": self.reports, "clock": self.clock,
                       "runtime": self.runtime, "session_id": self.session_id, "started_at": self.started_at}
        verifier = getattr(self.writer.authority, 'verify_shutdown_components', None)
        if (lane.writer is not self.writer or lane.shutdown is not self or lane.reports is not self.reports
                or self.runtime.clock is not self.clock or verifier is None or verifier(self.writer.binding, binding) is not True):
            raise ValueError('PERP_SHUTDOWN_OWNERSHIP_OR_COMPONENTS_UNVERIFIED')

    def stop(self, *, emergency):
        self._verify()
        if self.runtime.state != 'STOPPING' or not self.runtime.entry_closed.is_set():
            raise ValueError('PERP_SHUTDOWN_ADMISSION_NOT_CLOSED')
        if emergency:
            return {"state": 'INCOMPLETE', "reason": 'EMERGENCY_POSITIONS_PRESERVED'}
        try:
            if hasattr(self.writer, 'orders'):
                for key, row in self.writer._control()['state']['orders'].items():
                    if row['state'] == 'FILL_PENDING':
                        raise ValueError('PERP_RESTING_FILL_UNKNOWN')
                    if row['state'] == 'RESERVED':
                        self.runtime.cancel_resting({'operation_id': 'perp-cancel:' + digest([self.session_id, key]),
                            'kind': 'CANCEL_RESTING_ORDER', 'order': row['order']})
            cut = self.writer._cut()
            if self.completed is not None:
                if cut['head'] != self.completed['source_head']:
                    raise ValueError('PERP_SOURCE_CHANGED_AFTER_SHUTDOWN')
                return strict(body(self.completed))
            initial = [key for key, p in cut['state']['positions'].items() if number(p['remaining']) > 0]
            if len(initial) > 3:
                raise ValueError('PERP_SHUTDOWN_POSITION_BOUND_EXCEEDED')
            for key in sorted(initial):
                cut = self.writer._cut()
                p = cut['state']['positions'][key]
                if number(p['remaining']) <= 0:
                    raise ValueError('PERP_SHUTDOWN_POSITION_CHANGED')
                at = self.clock()
                if type(at) is not int or at < self.started_at:
                    raise ValueError('PERP_SHUTDOWN_CLOCK_UNVERIFIED')
                evidence = self.books.shutdown_evidence(strict(body(p)), cut, at)
                operation_id = 'perp-stop:' + digest([self.session_id, cut['manifest']['epoch'], key, p['revision']])
                command = {"schema": 'PAPER_PERP_COMMAND_V2', "epoch": cut['manifest']['epoch'], "operation_id": operation_id,
                    "kind": 'EXIT', "expected_source_revision": cut['state']['revision'], "timestamp": at,
                    "position_id": key, "expected_position_revision": p['revision'], "quantity": p['remaining'],
                    "liquidity": 'TAKER', "evidence": evidence}
                proposal = {"operation_id": operation_id, "kind": 'EXIT', "command": command,
                                "source_head": cut['head'], "strategy_ref": 'SHUTDOWN_FLATTEN:' + self.session_id}
                self.runtime.dispatch_shutdown_exit('HYPERLIQUID', proposal)
            cut = self.writer._cut()
            if self.runtime.uncertain or any(number(p['remaining']) > 0 for p in cut['state']['positions'].values()):
                raise ValueError('PERP_SHUTDOWN_FINANCIAL_CUT_UNRESOLVED')
            if hasattr(self.writer, 'verify_order_drain') and self.writer.verify_order_drain() is not True:
                raise ValueError('PERP_RESTING_CONTROL_DRAIN_UNRESOLVED')
            cutoff = self.clock()
            document = self.reports.publish_session(session_id=self.session_id, started_at=self.started_at,
                                                     cutoff_at=cutoff, observed_at=cutoff)
            final = self.writer._cut()
            report = document['report']
            outcome = {"state": 'ACKNOWLEDGED_FLAT_AND_DRAINED', "session_id": self.session_id, "cutoff_at": cutoff,
                           "source_head": final['head'], "report_id": document['report_id'], "cash": final['state']['cash']}
            verifier = getattr(self.writer.authority, 'verify_drain', None)
            if (final['head'] != cut['head'] or report['status'] != 'COMPLETE'
                    or report['source']['head'] != final['head'] or report['source']['root'] != final['root']
                    or report['source']['cutoff_revision'] != final['state']['revision']
                    or report['open_positions'] or number(report['cash']['closing']) != number(final['state']['cash'])
                    or verifier is None or verifier(self.writer.binding, final, {'shutdown': outcome, 'report': report}) is not True):
                raise ValueError('PERP_SHUTDOWN_REPORT_OR_WRITER_DRAIN_UNVERIFIED')
            self.completed = outcome
            return strict(body(outcome))
        except (ValueError, OSError, TimeoutError, KeyError, TypeError):
            return {"state": 'INCOMPLETE', "reason": 'PERP_POSITION_PRICE_PUBLICATION_REPORT_OR_DRAIN_UNRESOLVED'}


class CanonicalWriterLane:
    """Connect existing read observer/planner/shutdown ports to the native writer.

    No strategy is invented: the injected planner must return source-bound native
    proposals and the authority must authenticate its exact identity and evidence.
    """
    def __init__(self, *, writer, observer, planner, shutdown, reports=None):
        from app.services.perp_resting_writer import RestingPerpWriter
        if type(writer) not in (NativeFinancialWriter, OperationalPerpFinancialWriter, EnrolledQualityDipsWriter, RestingPerpWriter) or any(x is None for x in (observer, planner, shutdown, reports)):
            raise ValueError("CANONICAL_EXISTING_LANE_COMPONENTS_REQUIRED")
        self.writer, self.observer, self.planner, self.shutdown = writer, observer, planner, shutdown
        self.reports = reports
        if reports.store is not writer.store:
            raise ValueError("CANONICAL_LANE_REPORT_SOURCE_SUBSTITUTED")
        self.components = {"writer": writer, "observer": observer, "planner": planner, "shutdown": shutdown, "reports": reports}
        self._verify()

    def _verify(self):
        if any(getattr(self, key) is not value for key, value in self.components.items()):
            raise ValueError("CANONICAL_LANE_COMPONENT_REPLACED")
        verifier = getattr(self.writer.authority, "verify_lane", None)
        if verifier is None or verifier(self.writer.binding, self.components) is not True:
            raise ValueError("CANONICAL_LANE_OWNERSHIP_UNVERIFIED")

    @property
    def requires_portfolio_drain(self):
        return True

    async def observe(self):
        self._verify()
        return await self.observer.observe()

    def verify_observation(self, value):
        self._verify()
        return self.observer.verify_observation(value)

    async def next_proposal(self, observation):
        self._verify()
        from app.services.paper_financial_replay import ControlCapacityReached
        needed=4 if type(self.writer) is EnrolledQualityDipsWriter else 2
        if self.reports.archive.remaining_reports()<needed:
            raise ControlCapacityReached('REPORT_CAPACITY_RESERVED_FOR_FINAL_DRAIN')
        try:
            cut = self.writer._cut()
        except (OSError, ValueError) as error:
            raise FinancialSourceUncertain('CANONICAL_CURRENT_FINANCIAL_SOURCE_UNCERTAIN') from error
        return await self.planner.next_proposal(observation, cut)

    def verify_proposal(self, proposal, observation):
        self._verify()
        return self.writer.verify_proposal(proposal, observation)

    def dispatch(self, proposal, reservation):
        self._verify()
        return self.writer.dispatch(proposal, reservation)

    def verify_resting(self, proposal, observation):
        self._verify()
        return self.writer.verify_resting(proposal, observation)

    def dispatch_resting(self, proposal, reservation):
        self._verify()
        return self.writer.dispatch_resting(proposal, reservation)

    def stop(self, *, emergency):
        self._verify()
        result = self.shutdown.stop(emergency=emergency)
        cut = self.writer._cut()
        if result.get("state") == "ACKNOWLEDGED_FLAT_AND_DRAINED":
            history = self.reports.history()
            if type(self.writer) is EnrolledQualityDipsWriter:
                history = [doc for doc in history if doc['report']['schema'] == 'FS3_QD_SESSION_REPORT_V1'
                           and doc['report']['session_id'] == result.get('session_id')]
            report = history[-1]["report"] if history else None
            verifier = getattr(self.writer.authority, "verify_drain", None)
            session_mismatch = (report is not None and report.get('schema') in ('FS3_PERP_SESSION_REPORT_V1', 'FS3_QD_SESSION_REPORT_V1')
                                and (report['session_id'] != result.get('session_id')
                                     or report['period']['cutoff_inclusive'] != result.get('cutoff_at')))
            if (emergency or any(number(p["remaining"]) > 0 for p in cut["state"]["positions"].values())
                    or session_mismatch
                    or report is None or report["status"] != "COMPLETE"
                    or report["source"]["root"] != cut["root"] or report["source"]["head"] != cut["head"]
                    or report["source"]["revision"] != cut["state"]["revision"]
                    or report["source"]["cutoff_revision"] != cut["state"]["revision"]
                    or number(report["cash"]["closing"]) != number(cut["state"]["cash"])
                    or report["open_positions"] != {} or report["epoch"] != cut["manifest"]["epoch"]
                    or report["policy_digest"] != digest(cut["manifest"]) or report["currency"] != cut["manifest"]["currency"]
                    or verifier is None or verifier(self.writer.binding, cut, {"shutdown": result, "report": report}) is not True):
                return {"state": "INCOMPLETE", "reason": "NATIVE_POSITION_OR_DRAIN_UNRESOLVED"}
        return result
