from pathlib import Path
import csv,io,zipfile
from app.backtest.binance_public_metrics_normalize import normalize

HEADER=["create_time","symbol","sum_open_interest","sum_open_interest_value"]


def _zip(path:Path,rows):
    sio=io.StringIO();w=csv.writer(sio,lineterminator="\n");w.writerow(HEADER);w.writerows(rows)
    with zipfile.ZipFile(path,"w",compression=zipfile.ZIP_DEFLATED) as zf:zf.writestr(path.stem+".csv",sio.getvalue())


def test_normalize_one_day_5m(tmp_path:Path):
    p=tmp_path/"BTCUSDT-metrics-2024-07-01.zip"
    rows=[]
    for i in range(288):
        hh=(i*5)//60;mm=(i*5)%60
        rows.append([f"2024-07-01 {hh:02d}:{mm:02d}:00","BTCUSDT","100",str(100000+i)])
    _zip(p,rows)
    out=tmp_path/"BTC-oi.csv";report=tmp_path/"r.json"
    r=normalize(inputs=[p],provider_symbol="BTCUSDT",start_utc="2024-07-01T00:00:00Z",end_utc="2024-07-02T00:00:00Z",output=out,report=report)
    assert r["row_count"]==288
    assert r["cadence_seconds"]==300
    assert r["first_timestamp"]=="2024-07-01T00:00:00Z"
    assert r["last_timestamp"]=="2024-07-01T23:55:00Z"
    assert r["pit_oi_context_complete"] is True
    assert r["rolling_volume_context_complete"] is False
    assert out.exists() and report.exists()


def test_duplicate_timestamp_fails_closed(tmp_path:Path):
    p=tmp_path/"a.zip";_zip(p,[["2024-07-01 00:00:00","BTCUSDT","1","2"],["2024-07-01 00:00:00","BTCUSDT","1","3"]])
    try:normalize(inputs=[p],provider_symbol="BTCUSDT",start_utc="2024-07-01T00:00:00Z",end_utc="2024-07-01T00:10:00Z",output=tmp_path/"o.csv")
    except RuntimeError as e:assert "duplicate" in str(e)
    else:raise AssertionError("expected duplicate failure")


def test_gap_fails_closed(tmp_path:Path):
    p=tmp_path/"a.zip";_zip(p,[["2024-07-01 00:00:00","BTCUSDT","1","2"],["2024-07-01 00:10:00","BTCUSDT","1","3"]])
    try:normalize(inputs=[p],provider_symbol="BTCUSDT",start_utc="2024-07-01T00:00:00Z",end_utc="2024-07-01T00:15:00Z",output=tmp_path/"o.csv")
    except RuntimeError as e:assert "cadence gaps" in str(e)
    else:raise AssertionError("expected gap failure")


def test_negative_oi_value_fails_closed(tmp_path:Path):
    p=tmp_path/"a.zip";_zip(p,[["2024-07-01 00:00:00","BTCUSDT","1","-2"]])
    try:normalize(inputs=[p],provider_symbol="BTCUSDT",start_utc="2024-07-01T00:00:00Z",end_utc="2024-07-01T00:05:00Z",output=tmp_path/"o.csv")
    except RuntimeError as e:assert "negative" in str(e)
    else:raise AssertionError("expected negative OI failure")


def test_other_symbol_rows_are_ignored(tmp_path:Path):
    p=tmp_path/"a.zip";_zip(p,[["2024-07-01 00:00:00","ETHUSDT","1","2"],["2024-07-01 00:00:00","BTCUSDT","1","3"]])
    r=normalize(inputs=[p],provider_symbol="BTCUSDT",start_utc="2024-07-01T00:00:00Z",end_utc="2024-07-01T00:05:00Z",output=tmp_path/"o.csv")
    assert r["row_count"]==1
