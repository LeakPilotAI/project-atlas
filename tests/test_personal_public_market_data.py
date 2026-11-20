from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
import pytest
from app.investment.yfinance_client import ProviderCallError
from app.personal_paper import create_app
from app.services.personal_public_market_data import (
    PublicMarketDataError,
    append_market_data,
    build_yahoo_public_record,
    fetch_yahoo_public_record,
    market_data_read_model,
    read_market_data,
    require_manual_refresh_spacing,
)
from fastapi.testclient import TestClient


def _frames(now: datetime, *, quote_age: int = 30, future_quote: bool = False):
    quote_at = now + timedelta(minutes=1) if future_quote else now - timedelta(seconds=quote_age)
    intraday = pd.DataFrame(
        {"Close": [101.25]},
        index=pd.DatetimeIndex([quote_at]),
    )
    daily = pd.DataFrame(
        {
            "Open": [99.0],
            "High": [103.0],
            "Low": [98.0],
            "Close": [101.0],
            "Adj Close": [100.5],
            "Volume": [10000],
        },
        index=pd.DatetimeIndex([
            now.astimezone(ZoneInfo("America/New_York")).date()
        ]),
    )
    return intraday, daily


def _record(now: datetime, *, quote_age: int = 30, future_quote: bool = False):
    intraday, daily = _frames(now, quote_age=quote_age, future_quote=future_quote)
    return build_yahoo_public_record(
        "MSFT",
        intraday,
        daily,
        request_started_at=now - timedelta(seconds=5),
        retrieved_at=now,
    )


def test_yahoo_public_record_preserves_provenance_and_distinguishes_bar_from_quote():
    now = datetime.now(UTC)
    record = _record(now)
    quote = record["quote"]
    assert quote["price"] == 101.25
    assert quote["quality"] == "LIVE"
    assert quote["price_kind"] == "TRADE_BAR_CLOSE"
    assert quote["effective_timestamp"] == (now - timedelta(seconds=30)).isoformat()
    assert record["daily_bars"][0]["source"] == "yfinance"
    assert record["data_provenance"] == "PUBLIC_PROVIDER_DATA"
    assert record["paper_entry_authorized"] is False
    assert record["private_account_accessed"] is False
    assert record["broker_order_created"] is False


def test_stale_and_future_provider_timestamps_never_become_current_prices():
    now = datetime.now(UTC)
    stale = _record(now, quote_age=1800)
    assert stale["quote"]["quality"] == "REFERENCE"
    assert stale["quote"]["price"] is not None
    future = _record(now, future_quote=True)
    assert future["quote"]["quality"] == "MISSING"
    assert future["quote"]["price"] is None
    assert future["quote"]["effective_timestamp"] is None


def test_manual_fetch_uses_only_bounded_yahoo_history_calls():
    now = datetime.now(UTC)
    intraday, daily = _frames(now)

    class FakeYahooClient:
        def __init__(self):
            self.calls = []

        async def history(self, symbol, **kwargs):
            self.calls.append((symbol, kwargs))
            return intraday if kwargs["interval"] == "1m" else daily

    client = FakeYahooClient()
    result = asyncio.run(fetch_yahoo_public_record("msft", client=client))
    assert result["symbol"] == "MSFT"
    assert len(client.calls) == 2
    assert [call[1]["interval"] for call in client.calls] == ["1m", "1d"]
    assert all(call[0] == "MSFT" for call in client.calls)
    assert client.calls[0][1] == {
        "period": "5d",
        "interval": "1m",
        "prepost": True,
    }
    assert client.calls[1][1] == {
        "period": "5y",
        "interval": "1d",
        "prepost": False,
    }


def test_provider_failures_are_persistable_and_never_reuse_old_quotes():
    class FailedYahooClient:
        async def history(self, _symbol, **kwargs):
            raise ProviderCallError(
                "RATE_LIMIT",
                "provider rate limit",
                "MSFT",
                retryable=True,
            )

    record = asyncio.run(fetch_yahoo_public_record("MSFT", client=FailedYahooClient()))
    assert record["refresh_status"] == "FAILED"
    assert record["provider_errors"] == [
        "YAHOO_INTRADAY_RATE_LIMIT",
        "YAHOO_DAILY_RATE_LIMIT",
    ]
    assert record["quote"]["price"] is None
    assert record["quote"]["effective_timestamp"] is None
    assert record["daily_bars"] == []


def test_invalid_symbol_fails_before_provider_call():
    class NoCallClient:
        async def history(self, *_args, **_kwargs):
            raise AssertionError("provider must not be called for invalid symbol")

    with pytest.raises(PublicMarketDataError):
        asyncio.run(fetch_yahoo_public_record("MSFT;PRIVATE", client=NoCallClient()))


def test_market_data_append_restart_and_digest_reconciliation(tmp_path):
    path = tmp_path / "market.jsonl"
    record = _record(datetime.now(UTC))
    append_market_data(path, record)
    assert read_market_data(path) == [record]
    read_model = market_data_read_model(path)
    assert read_model["record_count"] == 1
    assert read_model["latest_by_symbol"] == [record]
    assert read_model["paper_entry_authorized"] is False

    path.write_bytes(path.read_bytes().replace(b"101.25", b"102.25", 1))
    with pytest.raises(PublicMarketDataError, match="Unreadable"):
        read_market_data(path)


def test_manual_public_refresh_is_rate_limited_per_symbol_and_clock_rollback_refuses(tmp_path):
    path = tmp_path / "market.jsonl"
    now = datetime.now(UTC)
    append_market_data(path, _record(now))
    with pytest.raises(PublicMarketDataError, match="cooldown"):
        require_manual_refresh_spacing(path, "MSFT", now=now + timedelta(seconds=10))
    with pytest.raises(PublicMarketDataError, match="Local clock"):
        require_manual_refresh_spacing(path, "MSFT", now=now - timedelta(seconds=1))
    require_manual_refresh_spacing(path, "AAPL", now=now)


def test_incomplete_or_duplicate_field_journal_refuses_read_and_append(tmp_path):
    path = tmp_path / "market.jsonl"
    record = _record(datetime.now(UTC))
    append_market_data(path, record)
    path.write_bytes(path.read_bytes() + b'{"schema":"partial"}')
    with pytest.raises(PublicMarketDataError, match="incomplete"):
        append_market_data(path, record)

    duplicate = json.dumps(record, separators=(",", ":")).replace(
        '"schema":"ATLAS_QD_YAHOO_PUBLIC_MARKET_DATA_V1"',
        '"schema":"ATLAS_QD_YAHOO_PUBLIC_MARKET_DATA_V1","schema":"ATLAS_QD_YAHOO_PUBLIC_MARKET_DATA_V1"',
    )
    path.write_bytes((duplicate + "\n").encode())
    with pytest.raises(PublicMarketDataError, match="Unreadable"):
        read_market_data(path)


def test_dashboard_reads_public_data_separately_and_remains_read_only(tmp_path):
    journal = tmp_path / "paper.jsonl"
    market = tmp_path / "market.jsonl"
    record = _record(datetime.now(UTC))
    append_market_data(market, record)

    with TestClient(
        create_app(
            journal,
            market,
            forward_journal_path=tmp_path / "forward.jsonl",
            strategy_observations_path=tmp_path / "strategy.jsonl",
        )
    ) as client:
        response = client.get("/api/market-data/quality-dips")
        assert response.status_code == 200
        assert response.json()["latest_by_symbol"][0] == record
        assert client.post("/api/market-data/quality-dips").status_code == 405
        status = client.get("/api/paper/status").json()
        assert status["data_provenance"] == "TEST_DATA"
        assert status["genuine_forward_paper"] is False
