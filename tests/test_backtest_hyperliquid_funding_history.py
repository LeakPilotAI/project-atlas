import io,json
from pathlib import Path
import pytest
from app.backtest import hyperliquid_funding_history as mod

class _Resp:
    def __init__(self,payload):self.payload=payload
    def __enter__(self):return self
    def __exit__(self,*args):return False
    def read(self):return json.dumps(self.payload).encode()


def test_acquire_preserves_exact_events(monkeypatch,tmp_path:Path):
    rows=[
        {"time":1719792000000,"fundingRate":"0.00001"},
        {"time":1719795600000,"fundingRate":"-0.00002"},
    ]
    monkeypatch.setattr(mod.urllib.request,"urlopen",lambda *a,**k:_Resp(rows))
    out=tmp_path/"f.csv";report=tmp_path/"f.json"
    r=mod.acquire(symbol="BTC",start_utc="2024-07-01T00:00:00Z",end_utc="2024-07-01T02:00:00Z",output=out,report=report)
    text=out.read_text()
    assert "2024-07-01T00:00:00Z,1e-05" in text
    assert "2024-07-01T01:00:00Z,-2e-05" in text
    assert r["row_count"]==2
    assert r["exact_event_timestamps"] is True
    assert r["interpolation_used"] is False
    assert r["current_state_backfill_used"] is False


def test_duplicate_timestamp_fails(monkeypatch,tmp_path:Path):
    rows=[{"time":1719792000000,"fundingRate":"0.1"},{"time":1719792000000,"fundingRate":"0.2"}]
    monkeypatch.setattr(mod.urllib.request,"urlopen",lambda *a,**k:_Resp(rows))
    with pytest.raises(RuntimeError,match="duplicate funding timestamp"):
        mod.acquire(symbol="BTC",start_utc="2024-07-01T00:00:00Z",end_utc="2024-07-01T02:00:00Z",output=tmp_path/"f.csv")


def test_empty_window_fails(monkeypatch,tmp_path:Path):
    monkeypatch.setattr(mod.urllib.request,"urlopen",lambda *a,**k:_Resp([]))
    with pytest.raises(RuntimeError,match="no Hyperliquid funding events"):
        mod.acquire(symbol="ETH",start_utc="2024-07-01T00:00:00Z",end_utc="2024-07-01T02:00:00Z",output=tmp_path/"f.csv")
