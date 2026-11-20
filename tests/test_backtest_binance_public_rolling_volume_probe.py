from pathlib import Path
from app.backtest.binance_public_rolling_volume_probe import run


def test_probe_plan_adds_exact_24h_warmup(tmp_path:Path):
    r=run(provider_symbol="BTCUSDT",start_utc="2024-07-01T00:00:00Z",end_utc="2024-07-02T00:00:00Z",raw_root=tmp_path,output=tmp_path/"o.csv",report=tmp_path/"r.json",execute=False)
    a=r["acquisition"]
    assert a["start_utc"]=="2024-06-30T00:00:00Z"
    assert a["end_utc"]=="2024-07-02T00:00:00Z"
    assert a["symbols"]==["BTC"]
    assert a["intervals"]==["5m"]
    months=sorted({x["month"] for x in a["objects"]})
    assert months==["2024-06","2024-07"]
    assert r["status"]=="PLANNED_NOT_DOWNLOADED"


def test_probe_rejects_unknown_symbol(tmp_path:Path):
    try:run(provider_symbol="DOGEUSDT",start_utc="2024-07-01T00:00:00Z",end_utc="2024-07-02T00:00:00Z",raw_root=tmp_path,output=tmp_path/"o.csv",report=tmp_path/"r.json")
    except ValueError as e:assert "unsupported provider symbol" in str(e)
    else:raise AssertionError("expected unsupported symbol failure")
