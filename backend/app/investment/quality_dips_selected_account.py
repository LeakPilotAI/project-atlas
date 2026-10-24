"""Unregistered selected-account dispatcher over injected FS2/FS3 interfaces.

The owner lease must exclude financial writers AND candidate invalidation.
Admission prepare/finish/UNKNOWN records and manual reservations must be durable
in a future accepted implementation. No default authority/storage is provided.
"""
from app.services.paper_financial_replay import (
    apply_event,
    body,
    digest,
    strict,
    text,
    validate_manifest,
)


class FinancialStorePublisher:
    """Bridge an injected FS2 store, with separately verified scope custody.

    Scope verifier must independently bind the store resource to the inception;
    the manifest hash itself supplies no authority. Nothing is provisioned here.
    """
    def __init__(self, *, store, manifest, scope_verifier):
        self.store, self.manifest, self.scope_verifier = store, strict(body(manifest)), scope_verifier

    def _verify(self):
        if self.scope_verifier(self.store, digest(self.manifest)) is not True:
            raise ValueError("FINANCIAL_RESOURCE_SCOPE_UNVERIFIED")

    def snapshot(self):
        self._verify()
        view = self.store.snapshot()
        if view.get("schema") != "FS2_ACKNOWLEDGED_VIEW_V1" or view.get("status") != "ACKNOWLEDGED":
            raise ValueError("FINANCIAL_SOURCE_UNKNOWN")
        return strict(body(view["state"]))

    def execute(self, command, *, projection_required):
        self._verify()
        return self.store.execute(command, projection_required=projection_required)


class SelectedAccountDispatcher:
    def __init__(self, *, manifest, owner, evidence, admission, manual, publisher, projection, clock):
        validate_manifest(manifest)
        if manifest["schema"] != "PAPER_EPOCH_SELECTED_QD_V3":
            raise ValueError("EXPLICIT_INTEGRATION_VERSION_REQUIRED")
        self.manifest, self.owner = strict(body(manifest)), strict(body(owner))
        self.evidence, self.admission, self.manual = evidence, admission, manual
        self.publisher, self.projection, self.clock = publisher, projection, clock
        self.account, self.epoch = manifest["account_policy"]["account_id"], manifest["epoch"]
        self.poisoned = False

    def _command(self, request, now):
        common = {"kind", "operation_id", "quantity", "expected_source_revision", "timestamp", "approval"}
        fields = {"candidate"} if request.get("kind") == "ENTRY" else {"position_id", "expected_position_revision", "instrument", "quote"}
        if (set(request) != common | fields or request["kind"] not in ("ENTRY", "EXIT")
                or type(now) is not int or type(request["timestamp"]) is not int
                or not 0 <= now - request["timestamp"] <= 15):
            raise ValueError("COMMAND_REQUEST_INVALID_OR_STALE")
        candidate = None
        if request["kind"] == "ENTRY":
            candidate = strict(request["candidate"])
            # Reverify original sources under exclusion, never trust a supplied
            # candidate class/hash or the verification result from UI preparation.
            fresh = self.evidence.candidate(candidate["source_bundle"], level=candidate["ranking"]["level"], now=now)
            if fresh != request["candidate"]:
                raise ValueError("CANDIDATE_REPLACED")
            if candidate["ranking"]["source_id"] != self.manifest["account_policy"]["ranking_authority"]:
                raise ValueError("RANKING_ISSUER_MISMATCH")
            execution = candidate["execution"]
        else:
            execution = self.evidence.execution(request["instrument"], request["quote"], now=now)
        instrument = execution["instrument"]
        policy_instrument = self.manifest["account_policy"]["instruments"].get(instrument["symbol"])
        expected_instrument = {"instrument_id": instrument["instrument_id"], "asset_class": instrument["asset_class"],
                               "fractional": instrument["fractional"], "quote_source": execution["quote"]["source_id"]}
        if body(policy_instrument) != body(expected_instrument):
            raise ValueError("INCEPTION_EXECUTION_RULE_MISMATCH")
        command = {"schema": "PAPER_COMMAND_SELECTED_QD_V3", "epoch": self.epoch,
                   "operation_id": request["operation_id"], "kind": request["kind"], "quantity": request["quantity"],
                   "expected_source_revision": request["expected_source_revision"], "timestamp": request["timestamp"],
                   "manual": True, "quote": execution["quote"], "eligibility": {"instrument_id": instrument["instrument_id"]}}
        if candidate:
            command.update(symbol=instrument["symbol"], side="LONG", risk_price=None,
                           origin_ref=candidate["ranking"]["observation_id"] + ":" + candidate["ranking"]["level"])
            command["eligibility"]["ranking"] = candidate["ranking"]
        else:
            command.update(position_id=request["position_id"], expected_position_revision=request["expected_position_revision"])
        context = {"account_id": self.account, "epoch": self.epoch, "operation_id": command["operation_id"],
                   "policy_digest": digest(self.manifest["account_policy"]), "instrument_id": instrument["instrument_id"],
                   "kind": command["kind"], "quantity": command["quantity"], "source_revision": command["expected_source_revision"],
                   "position_id": command.get("position_id"), "position_revision": command.get("expected_position_revision"),
                   "quote_digest": digest(command["quote"]), "candidate_digest": digest(request.get("candidate")),
                   "execution_digest": digest(execution),
                   "timestamp": command["timestamp"]}
        return command, context, execution

    def approval_context(self, request):
        """Read/preparation only. It reserves no approval and permits no effect."""
        with self.admission.lease(self.account, self.epoch):
            self._owner()
            _, context, _ = self._command(strict(body(request)), self.clock())
            return body(context)

    def _owner(self):
        proof = self.admission.verify_owner(self.owner, self.account, self.epoch)
        expected = {"owner": self.owner, "account_id": self.account, "epoch": self.epoch}
        if type(proof) is not dict or proof.get("verified") is not True or proof.get("binding") != digest(expected):
            raise ValueError("WRITER_OWNERSHIP_UNVERIFIED")

    def _unknown(self, request, reason):
        self.poisoned = True
        try:
            self.admission.mark_unknown(request["operation_id"], digest(request), reason)
        except (OSError, ValueError, KeyError, TypeError, RuntimeError):
            return {"status": "UNKNOWN", "durable_refusal_recorded": False, "startup_authorized": False}
        return {"status": "UNKNOWN", "durable_refusal_recorded": True, "startup_authorized": False}

    def execute(self, request):
        raw = body(request)
        if len(raw.encode()) > 49152:
            raise ValueError("COMMAND_CAPACITY")
        request = strict(raw)
        text(request["operation_id"])
        with self.admission.lease(self.account, self.epoch):
            self._owner()
            if self.poisoned:
                return {"status": "UNKNOWN", "startup_authorized": False}
            previous = self.admission.lookup(request["operation_id"], digest(request))
            if previous is not None:
                if type(previous) is not dict:
                    return self._unknown(request, "ADMISSION_RECORD_INVALID")
                if previous.get("request_digest") != digest(request):
                    raise ValueError("OPERATION_ID_CONFLICT")
                if previous.get("status") != "ACKNOWLEDGED":
                    self.poisoned = True
                    return {"status": "UNKNOWN", "startup_authorized": False}
                receipt = previous.get("receipt")
                if (type(receipt) is not dict or previous.get("account_id") != self.account or previous.get("epoch") != self.epoch
                        or receipt.get("epoch") != self.epoch or receipt.get("operation_id") != request["operation_id"]
                        or receipt.get("policy_digest") != digest(self.manifest["account_policy"])):
                    return self._unknown(request, "ACKNOWLEDGED_SCOPE_UNVERIFIED")
                try:
                    valid = self.projection.verify(receipt)
                except (OSError, ValueError, KeyError, TypeError, RuntimeError):
                    return self._unknown(request, "PROJECTION_ACKNOWLEDGEMENT_UNAVAILABLE")
                if valid is not True:
                    return self._unknown(request, "PROJECTION_ACKNOWLEDGEMENT_UNVERIFIED")
                return strict(body(previous))
            unresolved = self.admission.has_unresolved()
            if type(unresolved) is not bool:
                return self._unknown(request, "ADMISSION_STATE_UNVERIFIED")
            if unresolved:
                return {"status": "UNKNOWN", "startup_authorized": False}
            now = self.clock()
            command, context, execution = self._command(request, now)
            approval = self.manual.verify_and_reserve(request["approval"], context, now=now)
            if (type(approval) is not dict or approval.get("approved") is not True
                    or approval.get("binding") != digest(context) or not approval.get("receipt_id")
                    or type(approval.get("expires_at")) is not int or now >= approval["expires_at"]):
                raise ValueError("MANUAL_APPROVAL_UNVERIFIED")
            command["authority_evidence"] = {"candidate": request.get("candidate"), "execution": execution,
                                             "approval": approval, "context": context}
            state = self.publisher.snapshot()
            # Validate under the same admission/evidence exclusion BEFORE intent.
            expected_state, expected_receipt = apply_event(self.manifest, state, command)
            expected_receipt["projection_required"] = True
            if self.clock() != now:
                raise ValueError("CLOCK_CHANGED_REAPPROVAL_REQUIRED")
            try:
                self.admission.prepare(request["operation_id"], digest(request), context)
                if self.clock() != now:
                    raise ValueError("CLOCK_CHANGED_DURING_INTENT_PREPARATION")
                receipt = self.publisher.execute(command, projection_required=True)
                if (body(receipt) != body(expected_receipt) or receipt["state_digest"] != digest(expected_state)
                        or self.projection.verify(receipt) is not True):
                    raise ValueError("PUBLICATION_OR_PROJECTION_UNACKNOWLEDGED")
                result = {"status": "ACKNOWLEDGED", "request_digest": digest(request), "receipt": receipt,
                          "account_id": self.account, "epoch": self.epoch, "startup_authorized": False}
                self.admission.finish(request["operation_id"], result)
                return strict(body(result))
            except (OSError, ValueError, KeyError, TypeError, RuntimeError) as exc:
                return self._unknown(request, type(exc).__name__)
