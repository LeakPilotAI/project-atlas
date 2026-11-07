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
    assert r["page_count"]==1
    assert r["exact_event_timestamps"] is True
    assert r["interpolation_used"] is False
    assert r["current_state_backfill_used"] is False


def test_paginates_500_row_pages_without_fabrication(monkeypatch,tmp_path:Path):
    start=1719792000000
    first=[{"time":start+i*3600000,"fundingRate":"0.00001"} for i in range(500)]
    second=[{"time":start+500*3600000+i*3600000,"fundingRate":"0.00002"} for i in range(3)]
    pages=[first,second];calls=[]
    def fake(req,*a,**k):
        calls.append(json.loads(req.data.decode()))
        return _Resp(pages.pop(0))
    monkeypatch.setattr(mod.urllib.request,"urlopen",fake)
    end=start+504*3600000
    r=mod.acquire(symbol="BTC",start_utc=mod._iso(start),end_utc=mod._iso(end),output=tmp_path/"f.csv")
    assert r["row_count"]==503
    assert r["page_count"]==2
    assert calls[1]["startTime"]==first[-1]["time"]+1
    lines=(tmp_path/"f.csv").read_text().splitlines()
    assert len(lines)==504


def test_overlap_at_page_boundary_is_deduped(monkeypatch,tmp_path:Path):
    start=1719792000000
    first=[{"time":start+i*3600000,"fundingRate":"0.1"} for i in range(500)]
    second=[{"time":first[-1]["time"],"fundingRate":"0.1"},{"time":first[-1]["time"]+3600000,"fundingRate":"0.2"}]
    pages=[first,second]
    monkeypatch.setattr(mod.urllib.request,"urlopen",lambda *a,**k:_Resp(pages.pop(0)))
    r=mod.acquire(symbol="SOL",start_utc=mod._iso(start),end_utc=mod._iso(first[-1]["time"]+7200000),output=tmp_path/"f.csv")
    assert r["row_count"]==501
    assert r["page_count"]==2


def test_nonascending_within_page_fails(monkeypatch,tmp_path:Path):
    rows=[{"time":1719795600000,"fundingRate":"0.1"},{"time":1719792000000,"fundingRate":"0.2"}]
    monkeypatch.setattr(mod.urllib.request,"urlopen",lambda *a,**k:_Resp(rows))
    with pytest.raises(RuntimeError,match="not ascending"):
        mod.acquire(symbol="BTC",start_utc="2024-07-01T00:00:00Z",end_utc="2024-07-01T02:00:00Z",output=tmp_path/"f.csv")


def test_empty_window_fails(monkeypatch,tmp_path:Path):
    monkeypatch.setattr(mod.urllib.request,"urlopen",lambda *a,**k:_Resp([]))
    with pytest.raises(RuntimeError,match="no Hyperliquid funding events"):
        mod.acquire(symbol="ETH",start_utc="2024-07-01T00:00:00Z",end_utc="2024-07-01T02:00:00Z",output=tmp_path/"f.csv")
