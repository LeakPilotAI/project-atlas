"""Read-only adapters for the existing IEX and Hyperliquid caches.

Neither observer starts a scanner, opens a provider, submits a financial command
or turns mark/mid prices into executable quotes. Strategy decisions stay in the
existing strategy engine and require a separately verified financial adapter.
"""

from datetime import datetime

from app.investment.alpaca_iex import IEXFeed
from app.services.paper_financial_replay import body, digest, strict


def _iex_cut(view):
    return digest({k: v for k, v in view.items() if k != "observed_at"})


class IEXMarketObserver:
    def __init__(self, feed, *, calendar, clock):
        if type(feed) is not IEXFeed or calendar is None:
            raise ValueError("MARKET_EXISTING_IEX_AND_CALENDAR_REQUIRED")
        self.feed, self.calendar, self.clock = feed, calendar, clock
        self.last = None

    async def observe(self):
        view = self.feed.snapshot()
        session = self.calendar.read(self.clock())
        if session not in ("OPEN", "CLOSED", "UNKNOWN"):
            raise ValueError("MARKET_CALENDAR_UNVERIFIED")
        self.last = {"lane": "QUALITY_DIPS", "at": self.clock(),
                     "connection": "CONNECTED" if view["authenticated"] and view["subscribed"] else "DISCONNECTED",
                     "session": session, "signal": None, "source": {"feed": view["feed_id"], "cut": _iex_cut(view)}}
        return strict(body(self.last))

    def verify_observation(self, value):
        # Cache digest binds the read, not execution entitlement or startup authority.
        return (value == self.last and value["source"]["cut"] == _iex_cut(self.feed.snapshot()))


class HyperliquidMarketObserver:
    def __init__(self, adapter, *, clock, source=None):
        from app.adapters.hyperliquid import HyperliquidAdapter

        if type(adapter) is not HyperliquidAdapter:
            raise ValueError("MARKET_EXISTING_HYPERLIQUID_ADAPTER_REQUIRED")
        self.adapter, self.clock, self.last = adapter, clock, None
        if source is not None:
            from app.services.paper_source_publication import PerpSourcePublication
            if type(source) is not PerpSourcePublication or source.adapter is not adapter:
                raise ValueError('MARKET_AUTHENTICATED_ORIGINAL_SOURCE_REQUIRED')
        self.source=source

    async def observe(self):
        if self.source is not None:
            packet=self.source.read_cut()
            self.last={'lane':'HYPERLIQUID','at':packet['observed_at'],'connection':'CONNECTED','session':'OPEN',
                'signal':None,'source':{'feed':'HYPERLIQUID_AUTHENTICATED_SOURCE','cut':digest(packet)}}
            return strict(body(self.last))
        view = self.adapter.monitor_snapshot()
        # Receipt-based research marks are not exchange bid/ask timestamps.
        at = int(datetime.fromisoformat(view["observed_at"]).timestamp()) if view["observed_at"] else self.clock()
        self.last = {"lane": "HYPERLIQUID", "at": at,
                     "connection": "CONNECTED" if view["connection"] == "CONNECTED" else "DISCONNECTED",
                     "session": "OPEN" if view["connection"] == "CONNECTED" else "UNKNOWN",
                     "signal": None, "source": {"feed": "HYPERLIQUID_RESEARCH_MARK_NOT_EXECUTABLE", "cut": digest(view)}}
        return strict(body(self.last))

    def verify_observation(self, value):
        if self.source is not None:
            return (value==self.last and self.source.adapter is self.adapter
                    and value['source']['cut']==digest(self.source.read_cut()))
        return value == self.last and value["source"]["cut"] == digest(self.adapter.monitor_snapshot())
