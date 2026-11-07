from pathlib import Path
import csv,io,zipfile
import pytest
from app.backtest.binance_public_rolling_volume import derive,WINDOW_BARS

HEADER=["open_time","open","high","low","close","volume","close_time","quote_volume","count","taker_buy_volume","taker_buy_quote_volume","ignore"]
STEP=300000


def _zip(path:Path,start_ms:int,count:int,quote_fn=lambda i:1.0):
    sio=io.StringIO();w=csv.writer(sio,lineterminator="\n");w.writerow(HEADER)
    for i in range(count):
        ts=start_ms+i*STEP;q=quote_fn(i)
        w.writerow([ts,100,101,99,100,999,ts+STEP-1,q,1,0,0,0])
    with zipfile.ZipFile(path,"w",compression=zipfile.ZIP_DEFLATED) as zf:zf.writestr(path.stem+".csv",sio.getvalue())


def test_exact_24h_quote_volume_uses_quote_not_base(tmp_path:Path):
    start=1720051200000  # 2024-07-04 00:00 UTC
    warmup=start-WINDOW_BARS*STEP
    p=tmp_path/"BTCUSDT-5m.zip";_zip(p,warmup,WINDOW_BARS+3,lambda i:float(i+1))
    out=tmp_path/"v.csv";report=tmp_path/"v.json"
    r=derive(inputs=[p],provider_symbol="BTCUSDT",start_utc="2024-07-04T00:00:00Z",end_utc="2024-07-04T00:15:00Z",output=out,report=report)
    rows=list(csv.DictReader(out.open()))
    assert r["row_count"]==3 and r["window_bars"]==288
    assert r["source_field"]=="quote_volume" and r["current_state_backfill_used"] is False
    assert float(rows[0]["volume_24h_usd"])==sum(float(i+1) for i in range(1,WINDOW_BARS+1))
    assert float(rows[0]["volume_24h_usd"])!=999*WINDOW_BARS


def test_missing_warmup_bar_fails_closed(tmp_path:Path):
    start=1720051200000;warmup=start-WINDOW_BARS*STEP
    p=tmp_path/"x.zip";_zip(p,warmup+STEP,WINDOW_BARS)
    with pytest.raises(RuntimeError,match="warm-up"):
        derive(inputs=[p],provider_symbol="BTCUSDT",start_utc="2024-07-04T00:00:00Z",end_utc="2024-07-04T00:05:00Z",output=tmp_path/"o.csv")


def test_negative_quote_volume_fails_closed(tmp_path:Path):
    start=1720051200000;warmup=start-WINDOW_BARS*STEP
    p=tmp_path/"x.zip";_zip(p,warmup,WINDOW_BARS+1,lambda i:-1 if i==10 else 1)
    with pytest.raises(RuntimeError,match="negative quote_volume"):
        derive(inputs=[p],provider_symbol="BTCUSDT",start_utc="2024-07-04T00:00:00Z",end_utc="2024-07-04T00:05:00Z",output=tmp_path/"o.csv")


def test_duplicate_timestamp_across_archives_fails_closed(tmp_path:Path):
    start=1720051200000;warmup=start-WINDOW_BARS*STEP
    a=tmp_path/"a.zip";b=tmp_path/"b.zip";_zip(a,warmup,WINDOW_BARS+1);_zip(b,warmup,1)
    with pytest.raises(RuntimeError,match="duplicate"):
        derive(inputs=[a,b],provider_symbol="BTCUSDT",start_utc="2024-07-04T00:00:00Z",end_utc="2024-07-04T00:05:00Z",output=tmp_path/"o.csv")
