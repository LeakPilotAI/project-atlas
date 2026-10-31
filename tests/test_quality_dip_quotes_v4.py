import asyncio
from datetime import datetime, timedelta, timezone

from app.investment.board import build_quality_dips_board
from app.investment.quality_dip_quotes import QualityDipQuoteService, apply_quote_overlay, quote_health


class FakeRobinhoodMissing:
    async def get_quote(self, symbol):
        return {
            "symbol": symbol,
            "price": None,
            "display_price": None,
            "trigger_price": None,
            "effective_timestamp": None,
            "source": "robinhood",
            "error": {"code": "UNAVAILABLE", "message": "test fallback"},
        }


class FakeRobinhoodLive:
    def __init__(self, *, ts, bid=251.9, ask=252.1):
        self.ts = ts
        self.bid = bid
        self.ask = ask

    async def get_quote(self, symbol):
        mid = (self.bid + self.ask) / 2
        return {
            "symbol": symbol,
            "price": mid,
            "display_price": mid,
            "trigger_price": self.ask,
            "bid": self.bid,
            "ask": self.ask,
            "source": "robinhood_underlying_bid_ask",
            "session": "ROBINHOOD_MARKET_DATA",
            "effective_timestamp": self.ts.isoformat(),
            "raw_kind": "RHJ_UNDERLYING_BID_ASK",
            "error": None,
        }


class FakeClient:
    async def info(self, symbol):
        return {
            "marketState": "CLOSED",
            "regularMarketPrice": 249.0,
            "regularMarketTime": 1789333200,
            "postMarketPrice": 252.0,
            "postMarketTime": 1789336800,
            "previousClose": 247.0,
        }

    async def history(self, symbol, **kwargs):
        raise RuntimeError("no intraday test frame")


class _Index:
    def __init__(self, value):
        self.value = value

    def __getitem__(self, idx):
        return self.value


class _ILoc:
    def __init__(self, value):
        self.value = value

    def __getitem__(self, idx):
        return self.value


class _Series:
    empty = False

    def __init__(self, ts, price):
        self.index = _Index(ts)
        self.iloc = _ILoc(price)

    def dropna(self):
        return self


class _Frame:
    empty = False

    def __init__(self, ts, price):
        self.series = _Series(ts, price)

    def __getitem__(self, key):
        assert key == "Close"
        return self.series


class IntradayClient(FakeClient):
    def __init__(self, ts, price):
        self.ts = ts
        self.price = price

    async def history(self, symbol, **kwargs):
        assert kwargs["interval"] == "1m"
        assert kwargs["prepost"] is True
        return _Frame(self.ts, self.price)


def test_quote_service_chooses_newest_timestamped_yahoo_session_when_robinhood_missing():
    service = QualityDipQuoteService(client=FakeClient(), robinhood_client=FakeRobinhoodMissing())
    snap = asyncio.run(service._fetch("ADBE"))
    assert snap["symbol"] == "ADBE"
    assert snap["price"] == 252.0
    assert snap["session"] == "POST_MARKET"
    assert snap["source"] == "yfinance_quote"
    assert snap["effective_timestamp"] is not None


def test_intraday_minute_print_wins_and_can_be_live_when_robinhood_missing():
    now = datetime.now(timezone.utc) - timedelta(seconds=20)
    service = QualityDipQuoteService(client=IntradayClient(now, 333.25), robinhood_client=FakeRobinhoodMissing())
    snap = asyncio.run(service._fetch("ADBE"))
    assert snap["price"] == 333.25
    assert snap["source"] == "yfinance_1m"
    assert snap["quality"] == "LIVE"
    assert snap["is_live"] is True
    assert snap["tradable_for_ladder"] is True


def test_fresh_robinhood_bid_ask_is_preferred_and_ask_is_limit_trigger():
    now = datetime.now(timezone.utc) - timedelta(seconds=10)
    yahoo = IntradayClient(now - timedelta(seconds=5), 251.7)
    service = QualityDipQuoteService(
        client=yahoo,
        robinhood_client=FakeRobinhoodLive(ts=now, bid=252.0, ask=252.2),
    )
    snap = asyncio.run(service._fetch("ADBE"))
    assert snap["source"] == "robinhood_underlying_bid_ask"
    assert snap["price"] == 252.1
    assert snap["display_price"] == 252.1
    assert snap["bid"] == 252.0
    assert snap["ask"] == 252.2
    assert snap["trigger_price"] == 252.2
    assert snap["quality"] == "LIVE"
    assert snap["tradable_for_ladder"] is True


def test_overlay_preserves_research_price_and_exposes_trigger_bid_ask():
    rows = [{
        "symbol": "ADBE",
        "price": 250.0,
        "timestamp": "2026-09-12T20:00:00+00:00",
        "drawdown": {"current_drawdown": -0.5},
    }]
    quotes = {"ADBE": {
        "price": 300.0,
        "display_price": 300.0,
        "trigger_price": 300.1,
        "bid": 299.9,
        "ask": 300.1,
        "fresh_for_display": True,
        "tradable_for_ladder": True,
        "quality": "FRESH",
        "session": "ROBINHOOD_MARKET_DATA",
        "source": "robinhood_underlying_bid_ask",
    }}
    row = apply_quote_overlay(rows, quotes)[0]
    assert row["research_price"] == 250.0
    assert row["price"] == 300.0
    assert row["quote_display_price"] == 300.0
    assert row["quote_trigger_price"] == 300.1
    assert row["quote_bid"] == 299.9
    assert row["quote_ask"] == 300.1
    assert row["price_provenance"] == "CURRENT_QUOTE"
    assert row["drawdown"]["prior_high_anchor"] == 500.0
    assert round(row["drawdown"]["current_drawdown"], 4) == -0.4
    assert row["drawdown"]["research_current_drawdown"] == -0.5


def test_current_quote_recomputes_recovery_runway_before_aplus_gate():
    research = [{
        "timestamp": "2026-09-12T20:00:00+00:00",
        "symbol": "ADBE",
        "name": "Adobe",
        "asset_type": "STOCK",
        "price": 250.0,
        "classification": "ACCUMULATION",
        "opportunity_score": 82,
        "evidence_quality": "HIGH",
        "thesis": "INTACT",
        "components": {"valuation": 80, "fundamentals": 85, "drawdown": 90, "thesis_integrity": 90},
        "drawdown": {"current_drawdown": -0.5},
        "missing_critical": [],
    }]
    quotes = {"ADBE": {
        "price": 400.0,
        "display_price": 400.0,
        "fresh_for_display": True,
        "quality": "FRESH",
        "session": "REGULAR",
        "source": "yfinance_1m",
        "effective_timestamp": "2026-09-13T20:00:00+00:00",
        "age_sec": 60.0,
    }}
    board = build_quality_dips_board(apply_quote_overlay(research, quotes))
    row = board[0]
    assert row["price"] == 400.0
    assert row["research_price"] == 250.0
    assert round(row["current_drawdown"], 4) == -0.2
    assert row["recovery_runway_pct"] == 25.0
    assert row["quote_session"] == "REGULAR"
    assert row["price_provenance"] == "CURRENT_QUOTE"


def test_unusable_quote_never_overwrites_persisted_research_price_but_keeps_display_reference():
    rows = [{
        "symbol": "ADBE",
        "price": 250.0,
        "timestamp": "2026-09-12T20:00:00+00:00",
        "drawdown": {"current_drawdown": -0.5},
    }]
    quotes = {"ADBE": {
        "price": 300.0,
        "display_price": 300.0,
        "trigger_price": None,
        "fresh_for_display": False,
        "tradable_for_ladder": False,
        "quality": "STALE",
        "session": "REGULAR",
        "source": "yfinance_1m",
    }}
    row = apply_quote_overlay(rows, quotes)[0]
    assert row["price"] == 250.0
    assert row["quote_price"] is None
    assert row["quote_trigger_price"] is None
    assert row["quote_display_price"] == 300.0
    assert row["price_provenance"] == "RESEARCH_OBSERVATION"
    assert row["drawdown"]["current_drawdown"] == -0.5


def test_quote_health_separates_live_fresh_reference_stale_missing_and_robinhood():
    health = quote_health({
        "A": {"quality": "LIVE", "source": "robinhood_underlying_bid_ask"},
        "B": {"quality": "FRESH", "source": "yfinance_1m"},
        "C": {"quality": "REFERENCE", "source": "yfinance_quote"},
        "D": {"quality": "REFERENCE_ONLY", "source": "yfinance"},
        "E": {"quality": "STALE", "source": "yfinance_quote"},
        "F": {"quality": "MISSING", "source": "robinhood+yfinance"},
    })
    assert health["requested"] == 6
    assert health["live"] == 1
    assert health["fresh"] == 1
    assert health["reference"] == 2
    assert health["stale"] == 1
    assert health["missing"] == 1
    assert health["robinhood"] == 2
    assert health["source"] == "robinhood_underlying+yfinance_fallback"
    assert health["cache_ttl_sec"] == 15.0
