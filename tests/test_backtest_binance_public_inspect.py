from pathlib import Path
import csv,zipfile
from app.backtest.binance_public_inspect import inspect_zip

HEADER=["open_time","open","high","low","close","volume","close_time","quote_volume","count","taker_buy_volume","taker_buy_quote_volume","ignore"]


def _write_zip(path:Path,interval_ms:int,rows:int=3,bad_step:bool=False,header:bool=False):
    csv_name=path.stem+".csv"
    content=[]
    if header:content.append(HEADER)
    t=1719792000000
    for i in range(rows):
        content.append([str(t),"1","2","0.5","1.5","10",str(t+interval_ms-1),"15","5","6","9","0"])
        t += interval_ms if not(bad_step and i==0) else interval_ms*2
    with zipfile.ZipFile(path,"w",compression=zipfile.ZIP_DEFLATED) as zf:
        import io
        sio=io.StringIO();w=csv.writer(sio,lineterminator="\n");w.writerows(content)
        zf.writestr(csv_name,sio.getvalue())


def test_inspect_valid_5m(tmp_path:Path):
    p=tmp_path/"BTCUSDT-5m-2024-07.zip";_write_zip(p,300_000)
    r=inspect_zip(p,provider_symbol="BTCUSDT",interval="5m")
    assert r.row_count==3
    assert r.schema_valid is True
    assert r.cadence_consistent is True
    assert r.ascending_unique is True
    assert r.header_present is False
    assert r.pit_oi_context_complete is False
    assert r.live_capital_allowed is False


def test_inspect_valid_5m_with_real_style_header(tmp_path:Path):
    p=tmp_path/"BTCUSDT-5m-2024-07.zip";_write_zip(p,300_000,header=True)
    r=inspect_zip(p,provider_symbol="BTCUSDT",interval="5m")
    assert r.row_count==3
    assert r.header_present is True
    assert r.schema_valid is True
    assert r.cadence_consistent is True
    assert r.ascending_unique is True


def test_inspect_valid_1h_with_header(tmp_path:Path):
    p=tmp_path/"BTCUSDT-1h-2024-07.zip";_write_zip(p,3_600_000,header=True)
    r=inspect_zip(p,provider_symbol="BTCUSDT",interval="1h")
    assert r.cadence_ms==3_600_000
    assert r.cadence_consistent is True
    assert r.header_present is True


def test_bad_cadence_is_reported(tmp_path:Path):
    p=tmp_path/"BTCUSDT-5m-2024-07.zip";_write_zip(p,300_000,bad_step=True,header=True)
    r=inspect_zip(p,provider_symbol="BTCUSDT",interval="5m")
    assert r.cadence_consistent is False


def test_bad_column_count_fails_closed(tmp_path:Path):
    p=tmp_path/"BTCUSDT-5m-2024-07.zip"
    with zipfile.ZipFile(p,"w") as zf:zf.writestr("x.csv","1719792000000,1,2\n")
    try:inspect_zip(p,provider_symbol="BTCUSDT",interval="5m")
    except RuntimeError as e:assert "column count" in str(e)
    else:raise AssertionError("expected schema failure")


def test_multiple_csv_members_fail_closed(tmp_path:Path):
    p=tmp_path/"BTCUSDT-5m-2024-07.zip"
    row="1719792000000,1,2,0.5,1.5,10,1719792299999,15,5,6,9,0\n"
    with zipfile.ZipFile(p,"w") as zf:
        zf.writestr("a.csv",row);zf.writestr("b.csv",row)
    try:inspect_zip(p,provider_symbol="BTCUSDT",interval="5m")
    except RuntimeError as e:assert "exactly one CSV" in str(e)
    else:raise AssertionError("expected multiple-member failure")


def test_header_only_fails_closed(tmp_path:Path):
    p=tmp_path/"BTCUSDT-5m-2024-07.zip"
    with zipfile.ZipFile(p,"w") as zf:zf.writestr("x.csv",",".join(HEADER)+"\n")
    try:inspect_zip(p,provider_symbol="BTCUSDT",interval="5m")
    except RuntimeError as e:assert "no data rows" in str(e)
    else:raise AssertionError("expected header-only failure")
