from pathlib import Path
import csv,hashlib,io,zipfile
from app.backtest.binance_public_metrics import plan,inspect_metrics_zip,acquire


def _write_metrics_zip(path:Path):
    fields=["create_time","symbol","sum_open_interest","sum_open_interest_value","count_toptrader_long_short_ratio","sum_toptrader_long_short_ratio","count_long_short_ratio","sum_taker_long_short_vol_ratio"]
    rows=[{"create_time":"2024-07-01 00:00:00","symbol":"BTCUSDT","sum_open_interest":"1","sum_open_interest_value":"2","count_toptrader_long_short_ratio":"1","sum_toptrader_long_short_ratio":"1","count_long_short_ratio":"1","sum_taker_long_short_vol_ratio":"1"}]
    sio=io.StringIO();w=csv.DictWriter(sio,fieldnames=fields,lineterminator="\n");w.writeheader();w.writerows(rows)
    with zipfile.ZipFile(path,"w",compression=zipfile.ZIP_DEFLATED) as zf:zf.writestr("BTCUSDT-metrics-2024-07-01.csv",sio.getvalue())


def test_plan_three_symbols_two_days(tmp_path:Path):
    p=plan(start_utc="2024-07-01T00:00:00Z",end_utc="2024-07-03T00:00:00Z",raw_root=tmp_path)
    assert len(p["objects"])==6
    assert p["pit_context_complete"] is False
    assert p["current_state_backfill_allowed"] is False
    assert p["live_capital_allowed"] is False


def test_plan_rejects_unknown_symbol(tmp_path:Path):
    try:plan(start_utc="2024-07-01T00:00:00Z",end_utc="2024-07-02T00:00:00Z",raw_root=tmp_path,symbols=("DOGE",))
    except ValueError as e:assert "unsupported representative symbols" in str(e)
    else:raise AssertionError("expected unsupported symbol failure")


def test_inspect_metrics_schema(tmp_path:Path):
    p=tmp_path/"BTCUSDT-metrics-2024-07-01.zip";_write_metrics_zip(p)
    r=inspect_metrics_zip(p)
    assert r["rows"]==1
    assert r["has_open_interest"] is True
    assert r["pit_context_complete"] is False
    assert "sum_open_interest_value" in r["fields"]


def test_inspect_missing_required_column_fails(tmp_path:Path):
    p=tmp_path/"bad.zip"
    sio=io.StringIO();w=csv.writer(sio,lineterminator="\n");w.writerow(["create_time","symbol"]);w.writerow(["2024-07-01","BTCUSDT"])
    with zipfile.ZipFile(p,"w") as zf:zf.writestr("bad.csv",sio.getvalue())
    try:inspect_metrics_zip(p)
    except RuntimeError as e:assert "missing required columns" in str(e)
    else:raise AssertionError("expected schema failure")


def test_acquire_skips_already_checksum_verified_local_object(tmp_path:Path):
    payload=plan(start_utc="2024-07-01T00:00:00Z",end_utc="2024-07-02T00:00:00Z",raw_root=tmp_path,symbols=("BTC",))
    obj=payload["objects"][0]
    zp=Path(obj["local_zip"]);cp=Path(obj["local_checksum"])
    zp.parent.mkdir(parents=True,exist_ok=True);_write_metrics_zip(zp)
    digest=hashlib.sha256(zp.read_bytes()).hexdigest();cp.write_text(f"{digest}  {zp.name}\n",encoding="utf-8")
    result=acquire(payload)
    assert result["acquisition_status"]=="ACQUIRED_RAW_METRICS_CHECKSUM_VERIFIED"
    assert result["objects"][0]["status"]=="ALREADY_ACQUIRED_CHECKSUM_VERIFIED"
    assert result["objects"][0]["sha256"]==digest
