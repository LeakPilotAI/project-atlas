"""Inert runtime-facing read boundary. Not registered or instantiated by Atlas.

Injected read sources are not financial authority. All mutations are refused,
including with caller-supplied approvals,environment flags or fixture receipts.
No operational storage,writer,provider,startup or recovery integration exists.
"""
from html import escape
from threading import Lock

from app.services.paper_summary_contract import body, portfolio_payload_fixture, strict


class PaperBoundaryRefused(RuntimeError):
    pass


class PaperRuntimeBoundary:
    def __init__(self, *, source=None, expected_accounts=(), clock=None, observation_ttl=30):
        self.source, self.clock = source, clock
        self.expected = frozenset(expected_accounts)
        if len(self.expected) != len(expected_accounts) or type(observation_ttl) is not int or observation_ttl < 0:
            raise ValueError("Explicit unique read bindings and bounded observation TTL required")
        if any(type(p) is not tuple or len(p) != 2 or not all(type(v) is str and v for v in p) for p in self.expected):
            raise ValueError("Exact strategy/epoch read identities required")
        self.observation_ttl, self.revisions = observation_ttl, {}
        self._reading = Lock()

    def submit(self, _command):
        raise PaperBoundaryRefused("MUTATION_DISABLED: no financial activation or registered writer")

    def snapshot(self):
        if not self._reading.acquire(blocking=False):
            raise PaperBoundaryRefused("READ_ALREADY_IN_PROGRESS")
        try:
            return self._snapshot()
        finally:
            self._reading.release()

    def _snapshot(self):
        if self.source is None or self.clock is None:
            raise PaperBoundaryRefused("READ_SOURCE_UNBOUND")
        # A failed source must not return last-good balances as current.
        try:
            candidate = self.source()
            payload = portfolio_payload_fixture(candidate["accounts"])
            if candidate != payload:
                raise ValueError("Unexpected portfolio envelope")
            now = self.clock()
            if type(now) is not int:
                raise ValueError("Explicit observation clock required")
            if frozenset((r["strategy"], r["epoch"]) for r in payload["accounts"]) != self.expected:
                raise ValueError("Missing or substituted account binding")
            updates = {}
            for row in payload["accounts"]:
                if not 0 <= now - row["observed_at"] <= self.observation_ttl:
                    raise ValueError("Stale/future read observation")
                identity = row["strategy"], row["epoch"]
                revision = row["source_revision"]
                if revision is not None:
                    head = row["source_head"]
                    if type(head) is not str or len(head) != 64 or any(c not in "0123456789abcdef" for c in head):
                        raise ValueError("Missing/malformed source head")
                    old_revision, old_head = self.revisions.get(identity, (-1, None))
                    if revision < old_revision or (revision == old_revision and row["source_head"] != old_head):
                        raise ValueError("Source revision regression")
                    updates[identity] = revision, row["source_head"]
            result = strict(body(payload))  # No mutable references shared with provider/caller.
        except Exception as error:
            # This is a read boundary: preserve the cause without leaking paths,
            # source records or credentials into the operator-facing message.
            raise PaperBoundaryRefused("READ_EVIDENCE_UNAVAILABLE_OR_INVALID") from error
        self.revisions.update(updates)  # Unknown never resets a known revision watermark.
        return result


class PaperReadOnlyPresentation:
    """Unregistered adapter outputs for offline API/UI acceptance only."""
    def __init__(self, boundary=None):
        self.boundary = boundary or PaperRuntimeBoundary()

    def json(self):
        return body(self.boundary.snapshot())

    def html(self):
        payload = self.boundary.snapshot()
        headers = ["Strategy / epoch", "State", "Opening simulated cash", "Reconciled cash", "Gross P&L",
                   "Costs", "Net P&L", "Remaining positions", "Source revision", "Financial-event freshness"]
        lines = ['<table data-paper-presentation-version="2"><thead><tr>']
        lines.extend("<th>" + escape(x) + "</th>" for x in headers)
        lines.append("</tr></thead><tbody>")
        for row in payload["accounts"]:
            positions = row["remaining_positions"]
            remaining = None if positions is None else ", ".join(p["symbol"] + ":" + p["quantity"] for p in positions) or "None in verified fixture inventory"
            values = [row["strategy"] + " / " + row["epoch"], row["state"], row["simulated_opening_cash"],
                      row["reconciled_cash"], row["realized_gross"], row["trading_costs"], row["realized_net"],
                      remaining, row["source_revision"], row["freshness"]["status"]]
            lines.append("<tr>" + "".join("<td>" + escape("Unavailable" if v is None else str(v)) + "</td>" for v in values) + "</tr>")
        return "".join(lines) + "</tbody></table><p>Separate simulated accounts; equity unavailable. No trading or startup authority.</p>"
