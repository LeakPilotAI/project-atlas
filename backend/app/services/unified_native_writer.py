"""Source-bound FS1/FS2 writer seam; no authority discovery or startup route.

Existing FS2 test records are supported only in the explicit disposable domain.
An operational perpetual codec/enrollment is deliberately not invented here.
"""
from app.services.paper_financial_replay import (
    body,
    digest,
    number,
    strict,
    text,
    validate_manifest,
)


class NativeFinancialWriter:
    def __init__(self, *, store=None, authority=None, manifest=None, execution_domain=None):
        if store is None or authority is None or manifest is None:
            raise ValueError("NATIVE_WRITER_ACCEPTED_COMPONENTS_REQUIRED")
        validate_manifest(manifest)
        if execution_domain != "DISPOSABLE_TEST":
            raise ValueError("NATIVE_WRITER_OPERATIONAL_CODEC_NOT_ACCEPTED")
        self.store, self.authority = store, authority
        self.manifest = strict(body(manifest))
        self.binding = {"store": store, "manifest_digest": digest(manifest), "execution_domain": execution_domain}
        self._cut()

    def _cut(self):
        if self.authority.verify_components(self.binding) is not True:
            raise ValueError("NATIVE_WRITER_COMPONENT_AUTHORITY_REQUIRED")
        cut = self.store.verified_cut()
        if cut["pin_schema"] != "FS2_TEST_PIN_V1" or body(cut["manifest"]) != body(self.manifest):
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


class CanonicalWriterLane:
    """Connect existing read observer/planner/shutdown ports to the native writer.

    No strategy is invented: the injected planner must return source-bound native
    proposals and the authority must authenticate its exact identity and evidence.
    """
    def __init__(self, *, writer, observer, planner, shutdown, reports=None):
        if type(writer) is not NativeFinancialWriter or any(x is None for x in (observer, planner, shutdown, reports)):
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
        return await self.planner.next_proposal(observation, self.writer._cut())

    def verify_proposal(self, proposal, observation):
        self._verify()
        return self.writer.verify_proposal(proposal, observation)

    def dispatch(self, proposal, reservation):
        self._verify()
        return self.writer.dispatch(proposal, reservation)

    def stop(self, *, emergency):
        self._verify()
        result = self.shutdown.stop(emergency=emergency)
        cut = self.writer._cut()
        if result.get("state") == "ACKNOWLEDGED_FLAT_AND_DRAINED":
            history = self.reports.history()
            report = history[-1]["report"] if history else None
            verifier = getattr(self.writer.authority, "verify_drain", None)
            if (emergency or any(number(p["remaining"]) > 0 for p in cut["state"]["positions"].values())
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
