from pathlib import Path
import csv,io,zipfile
from app.backtest.binance_public_metrics_inspect import inspect_zip

HEADER=["create_time","symbol","sum_open_interest","sum_open_interest_value","count_toptrader_long_short_ratio","sum_toptrader_long_short_ratio","count_long_short_ratio","sum_taker_long_short_vol_ratio"]


def _write(path:Path,rows:list[list[str]],header:list[str]=HEADER):
    sio=io.StringIO();w=csv.writer(sio,lineterminator="\n");w.writerow(header);w.writerows(rows)
    with zipfile.ZipFile(path,"w",compression=zipfile.ZIP_DEFLATED) as zf:zf.writestr(path.stem+".csv",sio.getvalue())


def test_valid_metrics_archive(tmp_path:Path):
    p=tmp_path/"BTCUSDT-metrics-2024-07-01.zip"
    _write(p,[
        ["2024-07-01 00:05:00","BTCUSDT","100","6500000","1","1","1","1"],
        ["2024-07-01 00:10:00","BTCUSDT","101","6510000","1","1","1","1"],
        ["2024-07-01 00:15:00","BTCUSDT","102","6520000","1","1","1","1"],
    ])
    r=inspect_zip(p,provider_symbol="BTCUSDT")
    assert r.row_count==3
    assert r.required_columns_present is True
    assert r.ascending_unique is True
    assert r.cadence_seconds==300
    assert r.cadence_consistent is True
    assert r.pit_oi_context_complete is False


def test_other_symbols_are_filtered(tmp_path:Path):
    p=tmp_path/"BTCUSDT-metrics-2024-07-01.zip"
    _write(p,[
        ["2024-07-01 00:05:00","ETHUSDT","100","6500000","1","1","1","1"],
        ["2024-07-01 00:10:00","BTCUSDT","101","6510000","1","1","1","1"],
    ])
    r=inspect_zip(p,provider_symbol="BTCUSDT")
    assert r.row_count==1
    assert r.cadence_consistent is True


def test_missing_required_column_fails_closed(tmp_path:Path):
    p=tmp_path/"x.zip"
    _write(p,[["2024-07-01 00:05:00","BTCUSDT","100"]],header=["create_time","symbol","sum_open_interest"])
    try:inspect_zip(p,provider_symbol="BTCUSDT")
    except RuntimeError as e:assert "missing required columns" in str(e)
    else:raise AssertionError("expected required-column failure")


def test_duplicate_or_nonascending_time_fails_gate(tmp_path:Path):
    p=tmp_path/"x.zip"
    _write(p,[
        ["2024-07-01 00:05:00","BTCUSDT","100","6500000","1","1","1","1"],
        ["2024-07-01 00:05:00","BTCUSDT","101","6510000","1","1","1","1"],
    ])
    r=inspect_zip(p,provider_symbol="BTCUSDT")
    assert r.ascending_unique is False
    assert r.cadence_consistent is False


def test_negative_oi_fails_closed(tmp_path:Path):
    p=tmp_path/"x.zip"
    _write(p,[["2024-07-01 00:05:00","BTCUSDT","-1","6500000","1","1","1","1"]])
    try:inspect_zip(p,provider_symbol="BTCUSDT")
    except RuntimeError as e:assert "negative" in str(e)
    else:raise AssertionError("expected negative OI failure")
