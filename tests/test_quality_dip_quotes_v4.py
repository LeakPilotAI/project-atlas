import asyncio
from datetime import datetime, timedelta, timezone

from app.investment.board import build_quality_dips_board
from app.investment.quality_dip_quotes import QualityDipQuoteService, apply_quote_overlay, quote_health


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


def test_quote_service_chooses_newest_timestamped_session():
    service = QualityDipQuoteService(client=FakeClient())
    snap = asyncio.run(service._fetch("ADBE"))
    assert snap["symbol"] == "ADBE"
    assert snap["price"] == 252.0
    assert snap["session"] == "POST_MARKET"
    assert snap["source"] == "yfinance_quote"
    assert snap["effective_timestamp"] is not None


def test_intraday_minute_print_wins_and_can_be_live():
    now = datetime.now(timezone.utc) - timedelta(seconds=20)
    service = QualityDipQuoteService(client=IntradayClient(now, 333.25))
    snap = asyncio.run(service._fetch("ADBE"))
    assert snap["price"] == 333.25
    assert snap["source"] == "yfinance_1m"
    assert snap["quality"] == "LIVE"
    assert snap["is_live"] is True
    assert snap["tradable_for_ladder"] is True


def test_overlay_preserves_research_price_and_recomputes_drawdown_from_same_anchor():
    rows = [{
        "symbol": "ADBE",
        "price": 250.0,
        "timestamp": "2026-09-12T20:00:00+00:00",
        "drawdown": {"current_drawdown": -0.5},
    }]
    quotes = {"ADBE": {
        "price": 300.0,
        "display_price": 300.0,
        "fresh_for_display": True,
        "quality": "FRESH",
        "session": "REGULAR",
        "source": "yfinance_1m",
    }}
    row = apply_quote_overlay(rows, quotes)[0]
    assert row["research_price"] == 250.0
    assert row["price"] == 300.0
    assert row["quote_display_price"] == 300.0
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
        "fresh_for_display": False,
        "quality": "STALE",
        "session": "REGULAR",
        "source": "yfinance_1m",
    }}
    row = apply_quote_overlay(rows, quotes)[0]
    assert row["price"] == 250.0
    assert row["quote_price"] is None
    assert row["quote_display_price"] == 300.0
    assert row["price_provenance"] == "RESEARCH_OBSERVATION"
    assert row["drawdown"]["current_drawdown"] == -0.5


def test_quote_health_separates_live_fresh_reference_stale_and_missing():
    health = quote_health({
        "A": {"quality": "LIVE"},
        "B": {"quality": "FRESH"},
        "C": {"quality": "REFERENCE"},
        "D": {"quality": "REFERENCE_ONLY"},
        "E": {"quality": "STALE"},
        "F": {"quality": "MISSING"},
    })
    assert health["requested"] == 6
    assert health["live"] == 1
    assert health["fresh"] == 1
    assert health["reference"] == 2
    assert health["stale"] == 1
    assert health["missing"] == 1
    assert health["source"] == "yfinance_1m+quote_fields"
    assert health["cache_ttl_sec"] == 30.0
