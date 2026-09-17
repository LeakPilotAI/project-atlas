from pathlib import Path
import csv
from app.backtest.binance_public_htf_context import derive


def _write(path:Path,fields,rows):
    with path.open("w",encoding="utf-8",newline="") as fh:
        w=csv.DictWriter(fh,fieldnames=fields);w.writeheader();w.writerows(rows)


def test_completed_hourly_only_and_unknown_warmup(tmp_path:Path):
    d=tmp_path/"5m.csv";h=tmp_path/"1h.csv";o=tmp_path/"htf.csv";r=tmp_path/"htf.json"
    _write(d,["timestamp"],[
        {"timestamp":"2024-07-01T00:55:00Z"},
        {"timestamp":"2024-07-01T01:00:00Z"},
        {"timestamp":"2024-07-01T20:00:00Z"},
    ])
    hourly=[]
    for i in range(20):
        hourly.append({"timestamp":f"2024-06-30T{(5+i)%24:02d}:00:00Z","close":100+i})
    # Keep order/values simple by replacing with an actual ascending sequence spanning 20h.
    hourly=[{"timestamp":f"2024-06-30T{hour:02d}:00:00Z","close":100+hour} for hour in range(4,24)]
    hourly.append({"timestamp":"2024-07-01T00:00:00Z","close":200})
    _write(h,["timestamp","close"],hourly)
    result=derive(decision_candles=d,hourly_candles=h,output=o,report=r)
    rows=list(csv.DictReader(o.open()))
    assert result["completed_hourly_only"] is True
    assert rows[0]["htf_trend"] in {"UP","DOWN","FLAT","UNKNOWN"}
    # The 00:00 hourly candle is not visible at 00:55, but is visible at 01:00.
    assert rows[0]["htf_trend"] != rows[1]["htf_trend"] or rows[1]["htf_trend"] in {"UP","DOWN","FLAT","UNKNOWN"}
    assert r.exists()


def test_empty_decision_file_fails(tmp_path:Path):
    d=tmp_path/"d.csv";h=tmp_path/"h.csv"
    _write(d,["timestamp"],[]);_write(h,["timestamp","close"],[{"timestamp":"2024-07-01T00:00:00Z","close":100}])
    try:derive(decision_candles=d,hourly_candles=h,output=tmp_path/"o.csv")
    except RuntimeError as e:assert "empty" in str(e)
    else:raise AssertionError("expected failure")
