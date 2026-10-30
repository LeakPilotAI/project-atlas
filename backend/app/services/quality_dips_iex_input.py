"""IEX cache -> existing QD_AUTO_L1_V1 and shutdown evidence ports.

Authenticated feed access is not instrument, calendar, session or trading
authority. The accepted execution verifier supplies those distinct facts.
"""

from datetime import UTC, datetime

from app.investment.alpaca_iex import FEED, IEXRefused
from app.investment.enums import DataQuality
from app.investment.models import MeasuredValue
from app.services.paper_financial_replay import body, digest, number, strict


class IEXPaperQuotes:
    def __init__(self, *, feed, execution_authority=None, session_id=None, decision_reader=None):
        self.feed, self.authority = feed, execution_authority
        self.session_id, self.decision_reader = session_id, decision_reader
        self._last_quote, self._sequence = None, 0
        self._issued_frame = None
        self._issued_shutdown = None

    def research_reference_price(self, symbol, *, instrument):
        """Current accepted ASK -> existing free-research reference-price port.

        Uses the existing research_snapshot ASK convention. No socket/provider
        refresh, decision frame, session start or financial effect. This value
        supplies ratios/scoring only; an entry needs its own fresh L1 admission.
        """
        if (type(symbol) is not str or type(instrument) is not dict or instrument.get('symbol')!=symbol
                or instrument.get('asset_class') not in ('STOCK','ETF') or instrument.get('currency')!='USD'
                or instrument.get('units')!='SHARES' or type(instrument.get('instrument_id')) is not str
                or not instrument['instrument_id']):
            raise IEXRefused('IEX_RESEARCH_INSTRUMENT_REQUIRED')
        frozen=body(instrument)
        ports=self.feed,self.authority
        packet=self.quote(instrument)  # Existing entitlement/instrument/calendar/clock lease.
        # quote() explicitly adds one second for its coarse execution contract.
        # The underlying accepted physical clock allowance remains <=1second.
        if not 1<=number(packet['clock_uncertainty_seconds'])<=2:
            raise IEXRefused('IEX_RESEARCH_CLOCK_UNCERTAINTY')
        view=self.feed.snapshot()
        quote=next((q for q in view['quotes'] if q['symbol']==symbol),None)
        if (not view['authenticated'] or not view['subscribed'] or quote is None or quote['state']!='FRESH'
                or view['feed_id']!=FEED or 'iex:'+digest([quote['symbol'],quote['timestamp'],quote['bid'],
                    quote['ask'],quote['bid_lots'],quote['ask_lots']])!=packet['sequence']):
            raise IEXRefused('IEX_RESEARCH_QUOTE_CHANGED_OR_UNAVAILABLE')
        stamp=datetime.fromtimestamp(quote['source_ns']//10**9,UTC).replace(microsecond=quote['source_ns']%10**9//1000)
        received=datetime.fromtimestamp(quote['received_at'],UTC)
        now=datetime.fromtimestamp(view['observed_at'],UTC)
        if (not stamp<=received<=now or body(instrument)!=frozen
                or self.feed is not ports[0] or self.authority is not ports[1]):
            raise IEXRefused('IEX_RESEARCH_SOURCE_TIME_OR_IDENTITY')
        result=MeasuredValue(value=float(number(packet['ask'])),source='ALPACA_IEX_ASK_RESEARCH_REFERENCE',
            timestamp=stamp,effective_timestamp=stamp,retrieved_at=received,availability=True,quality=DataQuality.FRESH,
            notes=body({'schema':'QD_IEX_RESEARCH_REFERENCE_V1','basis':'ASK_REFERENCE_NOT_FILL',
                'symbol':symbol,'instrument_id':instrument['instrument_id'],'feed_id':FEED,'scope':'SINGLE_EXCHANGE_NOT_NBBO',
                'exact_ask':packet['ask'],'source_ns':quote['source_ns'],'sequence':packet['sequence'],
                'entitlement_id':packet['entitlement_id'],'clock_uncertainty_seconds':packet['clock_uncertainty_seconds'],
                'financial_execution_authorized':False}))
        # Refuse a changed/revoked quote/lease rather than blend source cuts.
        if (body(instrument)!=frozen or self.feed is not ports[0] or self.authority is not ports[1]
                or self.quote(instrument)!=packet or self.feed is not ports[0] or self.authority is not ports[1]):
            raise IEXRefused('IEX_RESEARCH_ACCEPTANCE_CHANGED')
        return result

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
        request = {
            "quotes": [packet],
            "observation": {
                "symbol": position["symbol"],
                "instrument": position["instrument"],
                "observed_at": int(self.feed.clock()),
                "current": {},
            },
        }
        self._issued_shutdown = (body({**request,'bundles':[],'shutdown_mode':'SHUTDOWN_FLATTEN'}),
                                 strict(body(position['instrument'])), self.feed, self.authority, self.session_id)
        return request

    def verify_source_request(self, request, *, now):
        if type(request) is not dict:
            raise IEXRefused('IEX_SOURCE_REQUEST_SCHEMA')
        if set(request) == {'bundles','quotes','observation'}:
            if self._issued_frame is None:
                raise IEXRefused('IEX_NO_ISSUED_OBSERVATION')
            frame = strict(self._issued_frame[0])
            if frame['request'] != request:
                raise IEXRefused('IEX_SOURCE_REQUEST_NOT_ISSUED')
            return self.verify_observation(frame, now=now)
        if set(request) == {'bundles','quotes','observation','shutdown_mode'}:
            issued = self._issued_shutdown
            if (issued is None or request.get('shutdown_mode') != 'SHUTDOWN_FLATTEN'
                    or request['bundles'] != [] or body(request) != issued[0]
                    or self.feed is not issued[2] or self.authority is not issued[3]
                    or self.session_id != issued[4] or now != int(self.feed.clock())
                    or self.quote(issued[1]) != request['quotes'][0]):
                raise IEXRefused('IEX_SHUTDOWN_REQUEST_NOT_ISSUED_OR_STALE')
            return True
        raise IEXRefused('IEX_SOURCE_REQUEST_SCHEMA')

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
        frame = {
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
        self._issued_frame = (body(frame), strict(body(request['instrument'])),
                              self.feed, self.authority, self.decision_reader, self.session_id)
        return frame

    def verify_observation(self, frame, *, now):
        """Verify only an observation issued by this admitted reader/feed binding."""
        issued = self._issued_frame
        if (issued is None or body(frame) != issued[0] or type(now) is not int
                or now != int(self.feed.clock()) or not 0 <= now-frame['observed_at'] <= 5
                or self.feed is not issued[2] or self.authority is not issued[3]
                or self.decision_reader is not issued[4] or self.session_id != issued[5]):
            raise IEXRefused('IEX_OBSERVATION_NOT_ISSUED_OR_STALE')
        # Revalidate the actual feed and execution lease; no refresh or provider call.
        if self.quote(issued[1]) != frame['request']['quotes'][0]:
            raise IEXRefused('IEX_OBSERVATION_QUOTE_CHANGED')
        return True
