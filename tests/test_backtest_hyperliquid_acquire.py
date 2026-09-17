import asyncio
from pathlib import Path
from app.backtest.hyperliquid_acquire import (
    _ms,fetch_candles,fetch_funding,acquire,candle_retention_floor_ms,candle_request_within_retention,
)

class FakeResponse:
    def __init__(self,data):self._data=data
    def raise_for_status(self):pass
    def json(self):return self._data

class FakeClient:
    def __init__(self):self.calls=[]
    async def post(self,url,json):
        self.calls.append(json)
        if json["type"]=="candleSnapshot":
            req=json["req"];step=300_000 if req["interval"]=="5m" else 3_600_000
            rows=[];t=req["startTime"]
            while t<=req["endTime"]:
                rows.append({"t":t,"o":"1","h":"2","l":"1","c":"2","v":"3","n":1});t+=step
            return FakeResponse(rows)
        start=json["startTime"]
        return FakeResponse([{"time":start,"fundingRate":"0.0001"}])


def test_ms_is_explicit_utc():
    assert _ms("2024-07-01T00:00:00Z")==1719792000000


def test_candle_retention_floor_matches_5000_rows():
    now=_ms("2026-09-16T00:00:00Z")
    assert candle_retention_floor_ms("5m",now_ms=now)==now-(5000*300_000)
    assert candle_retention_floor_ms("1h",now_ms=now)==now-(5000*3_600_000)


def test_old_locked_window_is_outside_candle_snapshot_retention():
    now=_ms("2026-09-16T00:00:00Z")
    old_end=_ms("2025-01-01T00:00:00Z")
    assert candle_request_within_retention(interval="5m",end_ms=old_end,now_ms=now) is False
    assert candle_request_within_retention(interval="1h",end_ms=old_end,now_ms=now) is False


def test_candle_acquisition_is_half_open_and_deterministic_when_in_retention():
    client=FakeClient();now=_ms("2026-09-16T00:00:00Z");start=now-900_000;end=now
    rows=asyncio.run(fetch_candles(client,symbol="BTC",interval="5m",start_ms=start,end_ms=end,now_ms=now))
    assert [r["t"] for r in rows]==[start,start+300_000,start+600_000]
    assert all(c["type"]=="candleSnapshot" for c in client.calls)


def test_old_candle_acquisition_fails_closed_without_http_call():
    client=FakeClient();now=_ms("2026-09-16T00:00:00Z");start=_ms("2024-07-01T00:00:00Z");end=_ms("2025-01-01T00:00:00Z")
    try:asyncio.run(fetch_candles(client,symbol="BTC",interval="5m",start_ms=start,end_ms=end,now_ms=now))
    except RuntimeError as e:assert "retention" in str(e).lower()
    else:raise AssertionError("expected old candle request to fail closed")
    assert client.calls==[]


def test_funding_is_timestamped_and_half_open():
    client=FakeClient();start=_ms("2024-07-01T00:00:00Z");end=start+3_600_000
    rows=asyncio.run(fetch_funding(client,symbol="BTC",start_ms=start,end_ms=end))
    assert rows==[{"time":start,"fundingRate":"0.0001"}]
    assert client.calls[0]["type"]=="fundingHistory"


def test_acquisition_rejects_non_representative_symbol(tmp_path:Path):
    try:asyncio.run(acquire(start_utc="2024-07-01T00:00:00Z",end_utc="2025-01-01T00:00:00Z",raw_root=tmp_path,symbols=("DOGE",)))
    except ValueError as e:assert "unsupported representative symbols" in str(e)
    else:raise AssertionError("expected fail-closed symbol validation")
