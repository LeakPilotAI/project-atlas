from pathlib import Path
import csv,json
from app.backtest.binance_public_htf_batch import run


def _candles(path:Path,timeframe:str,count:int):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("w",encoding="utf-8",newline="") as fh:
        w=csv.writer(fh);w.writerow(["timestamp","symbol","timeframe","open","high","low","close","volume"])
        step=300 if timeframe=="5m" else 3600
        start=1719792000
        for i in range(count):
            from datetime import datetime,timezone
            ts=datetime.fromtimestamp(start+i*step,tz=timezone.utc).isoformat().replace("+00:00","Z")
            w.writerow([ts,"BTC",timeframe,100,101,99,100+i*0.01,1])


def test_batch_three_symbols(tmp_path:Path):
    candle_root=tmp_path/"candles";out=tmp_path/"htf"
    for symbol in ("BTC","ETH","SOL"):
        _candles(candle_root/f"{symbol}-5m-2024-07-01_2024-07-02.csv","5m",288)
        _candles(candle_root/f"{symbol}-1h-2024-07-01_2024-07-02.csv","1h",24)
    r=run(candle_root=candle_root,output_root=out,start_utc="2024-07-01T00:00:00Z",end_utc="2024-07-02T00:00:00Z")
    assert r["normalized_output_count"]==3
    assert r["status"]=="DERIVED_COMPLETED_1H_HTF_CONTEXT"
    assert r["completed_hourly_only"] is True
    for symbol in ("BTC","ETH","SOL"):
        assert (out/f"{symbol}-htf-5m.csv").exists()
        payload=json.loads((out/f"{symbol}-htf-5m.normalization.json").read_text())
        assert payload["row_count"]==288


def test_missing_hourly_fails_closed(tmp_path:Path):
    candle_root=tmp_path/"candles";out=tmp_path/"htf"
    _candles(candle_root/"BTC-5m-2024-07-01_2024-07-02.csv","5m",288)
    try:
        run(candle_root=candle_root,output_root=out,start_utc="2024-07-01T00:00:00Z",end_utc="2024-07-02T00:00:00Z",symbols=("BTC",))
    except FileNotFoundError as e:
        assert "hourly" in str(e)
    else:raise AssertionError("expected missing-hourly failure")
