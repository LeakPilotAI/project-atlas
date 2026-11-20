from pathlib import Path
import csv,zipfile
from app.backtest.binance_public_normalize import normalize

HEADER=["open_time","open","high","low","close","volume","close_time","quote_volume","count","taker_buy_volume","taker_buy_quote_volume","ignore"]


def _zip(path:Path,start:int,step:int,count:int,header:bool=True,skip_index:int|None=None):
    rows=[]
    if header:rows.append(HEADER)
    for i in range(count):
        if skip_index is not None and i==skip_index:continue
        t=start+i*step
        rows.append([str(t),"100","110","90","105","12",str(t+step-1),"1260","5","6","630","0"])
    with zipfile.ZipFile(path,"w",compression=zipfile.ZIP_DEFLATED) as zf:
        import io
        s=io.StringIO();w=csv.writer(s,lineterminator="\n");w.writerows(rows);zf.writestr(path.stem+".csv",s.getvalue())


def test_normalize_headered_5m_exact_half_open_window(tmp_path:Path):
    start=1719792000000;step=300_000
    z=tmp_path/"BTCUSDT-5m-2024-07.zip";_zip(z,start,step,3,header=True)
    out=tmp_path/"BTC-5m.csv";report=tmp_path/"report.json"
    r=normalize(inputs=[z],provider_symbol="BTCUSDT",interval="5m",start_utc="2024-07-01T00:00:00Z",end_utc="2024-07-01T00:15:00Z",output=out,report=report)
    assert r["row_count"]==3
    assert r["symbol"]=="BTC"
    assert r["pit_context_complete"] is False
    rows=list(csv.DictReader(out.open(encoding="utf-8")))
    assert [x["timestamp"] for x in rows]==["2024-07-01T00:00:00Z","2024-07-01T00:05:00Z","2024-07-01T00:10:00Z"]
    assert all(x["symbol"]=="BTC" and x["timeframe"]=="5m" for x in rows)
    assert report.is_file()


def test_normalize_headerless_1h(tmp_path:Path):
    start=1719792000000;step=3_600_000
    z=tmp_path/"ETHUSDT-1h-2024-07.zip";_zip(z,start,step,2,header=False)
    r=normalize(inputs=[z],provider_symbol="ETHUSDT",interval="1h",start_utc="2024-07-01T00:00:00Z",end_utc="2024-07-01T02:00:00Z",output=tmp_path/"ETH-1h.csv")
    assert r["row_count"]==2 and r["symbol"]=="ETH"


def test_gap_fails_closed(tmp_path:Path):
    start=1719792000000;step=300_000
    z=tmp_path/"BTCUSDT-5m-2024-07.zip";_zip(z,start,step,3,skip_index=1)
    try:normalize(inputs=[z],provider_symbol="BTCUSDT",interval="5m",start_utc="2024-07-01T00:00:00Z",end_utc="2024-07-01T00:15:00Z",output=tmp_path/"x.csv")
    except RuntimeError as e:assert "gaps" in str(e)
    else:raise AssertionError("expected gap failure")


def test_duplicate_across_archives_fails_closed(tmp_path:Path):
    start=1719792000000;step=300_000
    a=tmp_path/"a.zip";b=tmp_path/"b.zip";_zip(a,start,step,2);_zip(b,start+step,step,2)
    try:normalize(inputs=[a,b],provider_symbol="BTCUSDT",interval="5m",start_utc="2024-07-01T00:00:00Z",end_utc="2024-07-01T00:15:00Z",output=tmp_path/"x.csv")
    except RuntimeError as e:assert "duplicate candle" in str(e)
    else:raise AssertionError("expected duplicate failure")


def test_unaligned_window_fails_closed(tmp_path:Path):
    z=tmp_path/"x.zip";_zip(z,1719792000000,300_000,1)
    try:normalize(inputs=[z],provider_symbol="BTCUSDT",interval="5m",start_utc="2024-07-01T00:01:00Z",end_utc="2024-07-01T00:06:00Z",output=tmp_path/"x.csv")
    except ValueError as e:assert "align" in str(e)
    else:raise AssertionError("expected alignment failure")


def test_unsupported_symbol_fails_closed(tmp_path:Path):
    try:normalize(inputs=[],provider_symbol="DOGEUSDT",interval="5m",start_utc="2024-07-01T00:00:00Z",end_utc="2024-07-01T00:05:00Z",output=tmp_path/"x.csv")
    except ValueError as e:assert "unsupported provider symbol" in str(e)
    else:raise AssertionError("expected unsupported-symbol failure")
