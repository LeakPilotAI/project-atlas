"""Uninstalled personal PAPER clock/session adapters; no independent custody claim.

Same-user SQL coordination is not anti-rollback authority. Review/issuer/boot
evidence remains injected and accepted separately. No keys, schema installation,
Windows settings or operational file paths are created here.
"""

from app.services.paper_financial_replay import body, digest, strict


class PersonalSessionReservations:
    def __init__(self, *, ledger, authorization, fault=lambda phase: None):
        if ledger is None or authorization is None:
            raise ValueError("PERSONAL_ACCEPTED_SESSION_DEPENDENCIES_REQUIRED")
        self.ledger, self.authorization, self.fault = ledger, authorization, fault

    def reserve(self, request):
        request = strict(body(request))
        if self.authorization.verify(request) is not True:
            raise ValueError("PERSONAL_OPERATOR_SESSION_UNVERIFIED")
        ident = request["grant"]["session_id"]
        with self.ledger.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            # Table must be installed separately; no implicit schema/store repair.
            if db.execute("SELECT 1 FROM personal_sessions WHERE id=?", (ident,)).fetchone():
                raise ValueError("PERSONAL_SESSION_REPLAY_OR_UNCERTAIN")
            db.execute(
                "INSERT INTO personal_sessions VALUES(?,?,?)", (ident, body(request), "PENDING")
            )
        self.fault("after_pending")
        if self.authorization.verify(request) is not True:
            raise ValueError("PERSONAL_SESSION_REVOKED_PENDING")
        with self.ledger.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            changed = db.execute(
                "UPDATE personal_sessions SET state='ACKNOWLEDGED' WHERE id=? AND body=? AND state='PENDING'",
                (ident, body(request)),
            )
            if changed.rowcount != 1:
                raise ValueError("PERSONAL_SESSION_PENDING_CONFLICT_OR_UNCERTAIN")
        self.fault("after_ack")
        receipt = {
            "schema": "QD_AUTO_NATIVE_SESSION_RESERVATION_V4",
            "request_digest": digest(request),
            "status": "ACKNOWLEDGED",
        }
        if self.verify(request, receipt) is not True:
            raise ValueError("PERSONAL_SESSION_ACK_READBACK_UNCERTAIN")
        return receipt

    def verify(self, request, receipt):
        with self.ledger.connect(readonly=True) as db:
            row = db.execute(
                "SELECT body,state FROM personal_sessions WHERE id=?",
                (request["grant"]["session_id"],),
            ).fetchone()
        return (
            row == (body(request), "ACKNOWLEDGED")
            and self.authorization.verify(request) is True
            and receipt
            == {
                "schema": "QD_AUTO_NATIVE_SESSION_RESERVATION_V4",
                "request_digest": digest(request),
                "status": "ACKNOWLEDGED",
            }
        )


class PersonalClockContinuity:
    """Accepted local UTC anchor + monotonic/boot/wall checks, not a time service.

    The operator/reviewer must accept the source and same-user limitations.
    No locally generated anchor is automatically authenticated by this adapter.
    """

    def __init__(self, *, anchor, authority, monotonic_ns, wall_utc, boot_identity):
        self.anchor = strict(body(anchor))
        self.authority, self.monotonic_ns, self.wall_utc, self.boot_identity = (
            authority,
            monotonic_ns,
            wall_utc,
            boot_identity,
        )

    def sample(self):
        a = self.anchor
        if (
            set(a)
            != {
                "schema",
                "utc",
                "monotonic_ns",
                "boot_id",
                "source",
                "expires_at",
                "uncertainty_ms",
            }
            or a["schema"] != "QD_PERSONAL_UTC_ANCHOR_V1"
            or self.authority.verify(a) is not True
            or any(
                type(a[k]) is not int
                for k in ("utc", "monotonic_ns", "expires_at", "uncertainty_ms")
            )
            or not a["utc"] <= a["expires_at"] <= a["utc"] + 300
            or not 0 <= a["uncertainty_ms"] <= 1000
            or self.boot_identity() != a["boot_id"]
        ):
            raise ValueError("PERSONAL_ACCEPTED_CLOCK_ANCHOR_REQUIRED")
        mono = self.monotonic_ns()
        if type(mono) is not int or mono < a["monotonic_ns"]:
            raise ValueError("PERSONAL_CLOCK_REBOOT_OR_ROLLBACK")
        utc = a["utc"] + (mono - a["monotonic_ns"]) // 10**9
        wall = self.wall_utc()
        if type(wall) is not int or utc > a["expires_at"] or abs(wall - utc) > 2:
            raise ValueError("PERSONAL_CLOCK_STALE_OR_DISCONTINUOUS")
        return {
            "schema": "QD_AUTO_NATIVE_CLOCK_V4",
            "utc": utc,
            "monotonic_ns": mono,
            "uncertainty_ms": a["uncertainty_ms"],
            "source": a["source"],
        }

    def verify(self, sample):
        now = self.sample()
        return (
            type(sample) is dict
            and set(sample) == set(now)
            and sample.get("schema") == now["schema"]
            and sample.get("source") == now["source"]
            and type(sample.get("monotonic_ns")) is int
            and type(sample.get("utc")) is int
            and self.anchor["monotonic_ns"] <= sample["monotonic_ns"]
            and 0 <= now["monotonic_ns"] - sample["monotonic_ns"] <= 10**9
            and sample["utc"]
            == self.anchor["utc"] + (sample["monotonic_ns"] - self.anchor["monotonic_ns"]) // 10**9
            and type(sample.get("uncertainty_ms")) is int
            and sample["uncertainty_ms"] == self.anchor["uncertainty_ms"]
        )
