"""Inert selected-account read boundary; supplies no enrollment or authority.

Accepted dependencies must be supplied by a separately reviewed composition
root. A Python object or a locally serialized pin is not itself trusted. The
authority's lease must cover the complete resource set for the entire read and
must reject unknown writers, rollback and loss of continuity. No default exists.
"""
from app.services.paper_daily_report import audit_daily_report, validate_scope
from app.services.paper_financial_audit import audit_financial_events
from app.services.paper_financial_replay import body, digest, replay_verified_events, strict


class CurrentReadEvidenceUnverified(ValueError):
    """Known current-pin uncertainty; carries no financial data or authority."""


class SelectedReadCapability:
    """Reader/verifier for the unregistered router, without write dependencies.

    authority.lease(enrollment, now) yields an accepted current snapshot and
    check(snapshot, now) revalidates it before return. It must provide genuine
    current high-water custody/exclusion, not caller-created assertions. Native
    port verifies bound identities before reading and never creates resources.
    """
    def __init__(self, *, enrollment, authority, clock, port):
        if authority is None or clock is None or port is None:
            raise ValueError("READ_AUTHORITY_REQUIRED")
        self.enrollment = strict(body(enrollment))
        self.authority, self.clock, self.port = authority, clock, port

    def read_committed(self, account_id, epoch):
        e = strict(body(self.enrollment))
        required = {"schema", "account_id", "epoch", "manifest_digest", "policy_digest",
                    "source_root", "projection_root", "report_root", "inception"}
        if (set(e) != required or e["schema"] != "QD_READ_ENROLLMENT_V1"
                or e["account_id"] != account_id or e["epoch"] != epoch):
            raise ValueError("READ_ENROLLMENT_MISMATCH")
        now = self.clock()
        if type(now) is not int or now <= 0:
            raise ValueError("TRUSTED_CLOCK_REQUIRED")
        with self.authority.lease(e, now) as lease:
            pin = strict(body(lease.snapshot))
            keys = {"schema", "enrollment_digest", "observed_at", "expires_at", "generation",
                    "source", "reports", "high_water", "acknowledged_revision", "status"}
            if (set(pin) != keys or pin["schema"] != "QD_READ_CURRENT_V1"
                    or pin["enrollment_digest"] != digest(e) or pin["status"] != "ACKNOWLEDGED"
                    or any(type(pin[k]) is not int for k in
                           ("observed_at", "expires_at", "generation", "high_water", "acknowledged_revision"))
                    or pin["generation"] < 1 or not 0 <= now - pin["observed_at"] <= 30
                    or not now <= pin["expires_at"] <= pin["observed_at"] + 30
                    or pin["high_water"] < 0 or pin["high_water"] != pin["acknowledged_revision"]
                    or pin["source"]["root"] != e["source_root"]
                    or pin["source"]["inception"] != e["inception"]
                    or pin["source"]["epoch"] != epoch
                    or len(pin["source"]["entries"]) != pin["high_water"]
                    or pin["reports"]["root"] != e["report_root"]):
                raise CurrentReadEvidenceUnverified("CURRENT_PIN_UNVERIFIED")
            evidence = self.port.read_verified(e, pin)
            manifest, rows = evidence["manifest"], evidence["rows"]
            if (manifest["schema"] != "PAPER_EPOCH_SELECTED_QD_V3"
                    or digest(manifest) != e["manifest_digest"]
                    or digest(manifest["account_policy"]) != e["policy_digest"]
                    or manifest["account_policy"]["account_id"] != account_id
                    or manifest["epoch"] != epoch or len(rows) != pin["high_water"]
                    or any(strict(row["receipt"])["projection_required"] is not True for row in rows)
                    or any(strict(row["command"])["timestamp"] > now for row in rows)):
                raise ValueError("SOURCE_SCOPE_UNVERIFIED")
            state, _, _ = replay_verified_events(manifest, rows)
            audit_financial_events(manifest, rows, state)
            if body(evidence["state"]) != body(state):
                raise ValueError("PROJECTION_INCONSISTENT")
            scope, documents = evidence["scope"], evidence["documents"]
            validate_scope(scope, manifest)
            if scope["account_id"] != account_id or not documents:
                raise ValueError("REPORT_SOURCE_REQUIRED")
            for document in documents:
                report = document["report"]
                n = report["source"]["revision"]
                if type(n) is not int or not 0 <= n <= len(rows) or report["observed_at"] > now:
                    raise ValueError("REPORT_REVISION_UNVERIFIED")
                subpin = {**pin["source"], "entries": pin["source"]["entries"][:n]}
                substate, _, _ = replay_verified_events(manifest, rows[:n])
                audit_daily_report(report, scope, manifest, subpin, rows[:n], substate)
            report = documents[-1]["report"]
            if report["source"]["revision"] != pin["high_water"]:
                raise ValueError("REPORT_NOT_CURRENT")
            end = self.clock()
            if type(end) is not int or not now <= end <= pin["expires_at"]:
                raise ValueError("CLOCK_DISCONTINUITY")
            if lease.check(pin, end) is not True:
                raise ValueError("READ_CONTINUITY_UNVERIFIED")
            return {"schema": "QD_COMMITTED_PROJECTION_V1", "account_id": account_id, "epoch": epoch,
                    "status": "ACKNOWLEDGED", "state": state, "observed_at": pin["observed_at"],
                    "source_revision": state["revision"], "projection_revision": state["revision"],
                    "source_identity": {"root": e["source_root"], "pin_digest": digest({
                                        "source": pin["source"], "reports": pin["reports"],
                                        "projection_root": e["projection_root"]}),
                                        "generation": pin["generation"]},
                    "policy_digest": e["policy_digest"], "report_status": report["status"],
                    "report": report, "selection": None,
                    "inception": {"schema": "QD_SELECTED_INCEPTION_VIEW_V1", "account_id": account_id,
                                  "epoch": epoch, "policy_digest": e["policy_digest"], "currency": "USD",
                                  "policy_schema": manifest["account_policy"]["schema"],
                                  "opening_cash": manifest["opening_cash"]}}

    def verify(self, payload, *, account_id, epoch, now):
        # Re-read/revalidate instead of caching an authority-granting digest.
        expected = self.read_committed(account_id, epoch)
        observed = payload.get("observed_at")
        # Freshness renewal does not change immutable financial identity. The
        # current state is independently revalidated above; only the bounded
        # earlier observation time may differ between the two reads.
        expected["observed_at"] = observed
        same = body(expected) == body(payload)
        return {"verified": same and type(now) is int and type(observed) is int
                and 0 <= now - observed <= 30, "binding": digest(expected)}
