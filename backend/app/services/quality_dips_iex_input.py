"""IEX cache -> existing QD_AUTO_L1_V1 and shutdown evidence ports.

Authenticated feed access is not instrument, calendar, session or trading
authority. The accepted execution verifier supplies those distinct facts.
"""

from app.investment.alpaca_iex import FEED, IEXRefused
from app.services.paper_financial_replay import body, digest, number, strict


class IEXPaperQuotes:
    def __init__(self, *, feed, execution_authority=None, session_id=None, decision_reader=None):
        self.feed, self.authority = feed, execution_authority
        self.session_id, self.decision_reader = session_id, decision_reader
        self._last_quote, self._sequence = None, 0

    def quote(self, instrument):
        if self.authority is None:
            raise IEXRefused("IEX_EXECUTION_AUTHORITY_REQUIRED")
        view = self.feed.snapshot()
        q = next((q for q in view["quotes"] if q["symbol"] == instrument["symbol"]), None)
        if (
            not view["authenticated"]
            or not view["subscribed"]
            or q is None
            or q["state"] != "FRESH"
        ):
            raise IEXRefused("IEX_EXECUTABLE_QUOTE_UNAVAILABLE")
        now = int(view["observed_at"])
        request = {"feed": FEED, "quote": q, "instrument": instrument}
        with self.authority.lease(request, now=now) as lease:
            accepted = strict(body(lease.snapshot))
            lot = accepted.get("round_lot_shares")
            if (
                lease.check(accepted, now) is not True
                or accepted.get("instrument") != instrument
                or accepted.get("feed_id") != FEED
                or accepted.get("verified") is not True
                or type(lot) is not int
                or not 0 < lot <= 10000
                or accepted.get("market_status") != "TRADING"
                or not accepted.get("entitlement_id")
                or accepted.get("calendar", {}).get("is_open") is not True
            ):
                raise IEXRefused("IEX_INSTRUMENT_ENTITLEMENT_CALENDAR_UNVERIFIED")
            uncertainty = number(accepted["clock_uncertainty_seconds"])
            if uncertainty < 0:
                raise IEXRefused("IEX_CLOCK_UNCERTAINTY_REFUSED")
            packet = {
                "schema": "QD_AUTO_L1_V1",
                "provider_id": "ALPACA",
                "feed_id": FEED,
                "entitlement_id": accepted["entitlement_id"],
                "feed_scope": "VENUE",
                "delay_status": "REALTIME",
                "symbol": instrument["symbol"],
                "instrument_id": instrument["instrument_id"],
                "asset_class": instrument["asset_class"],
                "currency": instrument["currency"],
                "bid": q["bid"],
                "ask": q["ask"],
                "bid_size": str(q["bid_lots"] * lot),
                "ask_size": str(q["ask_lots"] * lot),
                "size_units": "SHARES",
                "source_timestamp": q["source_ns"] // 10**9,
                "received_timestamp": int(q["received_at"]),
                "sequence": "iex:"
                + digest(
                    [q["symbol"], q["timestamp"], q["bid"], q["ask"], q["bid_lots"], q["ask_lots"]]
                ),
                "session": "REGULAR",
                "calendar": accepted["calendar"],
                "market_status": "TRADING",
                "connection_status": "CONNECTED",
                # The existing engine uses whole seconds; budget the loss of
                # subsecond precision conservatively instead of overstating age.
                "clock_uncertainty_seconds": str(uncertainty + 1),
            }
            if lease.check(accepted, now) is not True:
                raise IEXRefused("IEX_EXECUTION_AUTHORITY_CHANGED")
            return packet

    def observe(self, position, timeout):
        if not 0 < timeout <= 2:
            raise IEXRefused("IEX_BOUNDED_READ_REQUIRED")
        packet = self.quote(position["instrument"])
        return {
            "quotes": [packet],
            "observation": {
                "symbol": position["symbol"],
                "instrument": position["instrument"],
                "observed_at": int(self.feed.clock()),
                "current": {},
            },
        }

    def frame(self, *, session_id, sequence, bundles, instrument, observation=None):
        """Accepted ranking bundles remain external; no rankings are manufactured."""
        return {
            "schema": "QD_AUTO_OBSERVATION_V3",
            "session_id": session_id,
            "sequence": sequence,
            "observed_at": int(self.feed.clock()),
            "connected": True,
            "request": {
                "bundles": bundles,
                "quotes": [self.quote(instrument)],
                "observation": observation,
            },
        }

    def next(self, timeout):
        """Existing V3/V5 observation-source protocol; no invented rankings/signals.

        The admitted ranking/monitor reader is separately injected. A feed loss
        raises refusal so the existing runtime preserves holdings and halts.
        """
        if not self.session_id or self.decision_reader is None or not 0 < timeout <= 0.2:
            raise IEXRefused("IEX_ACCEPTED_DECISION_SOURCE_REQUIRED")
        request = self.decision_reader.read_request(timeout=timeout)
        if request is None:
            return None
        if set(request) != {"instrument", "bundles", "observation"}:
            raise IEXRefused("IEX_DECISION_REQUEST_REFUSED")
        packet = self.quote(request["instrument"])
        if packet["sequence"] == self._last_quote:
            from threading import Event

            Event().wait(timeout)
            return None
        self._last_quote = packet["sequence"]
        self._sequence += 1
        return {
            "schema": "QD_AUTO_OBSERVATION_V3",
            "session_id": self.session_id,
            "sequence": self._sequence,
            "observed_at": int(self.feed.clock()),
            "connected": True,
            "request": {
                "bundles": request["bundles"],
                "observation": request["observation"],
                "quotes": [packet],
            },
        }
