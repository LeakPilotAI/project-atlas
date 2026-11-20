from pathlib import Path
import csv
from app.backtest.funding_pit_merge_batch import run_batch


def _bars(path:Path,symbol:str):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("w",newline="",encoding="utf-8") as fh:
        w=csv.DictWriter(fh,fieldnames=["timestamp","symbol","timeframe","open","high","low","close","volume"]);w.writeheader()
        for i in range(3):
            w.writerow({"timestamp":f"2024-07-01T00:{i*5:02d}:00Z","symbol":symbol,"timeframe":"5m","open":1,"high":1,"low":1,"close":1,"volume":1})


def _funding(path:Path):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("w",newline="",encoding="utf-8") as fh:
        w=csv.DictWriter(fh,fieldnames=["timestamp","funding_rate"]);w.writeheader()
        w.writerow({"timestamp":"2024-07-01T00:00:00.100000Z","funding_rate":"0.001"})


def test_batch_merges_all_three_symbols(tmp_path:Path):
    bars_root=tmp_path/"bars";funding_root=tmp_path/"funding";out=tmp_path/"out"
    for s in ("BTC","ETH","SOL"):
        _bars(bars_root/f"{s}-5m-2024-07-01_2024-07-01.csv",s)
        _funding(funding_root/f"{s}-funding.csv")
    manifest=tmp_path/"manifest.json"
    r=run_batch(bars_root=bars_root,funding_root=funding_root,output_root=out,start_utc="2024-07-01T00:00:00Z",end_utc="2024-07-01T00:15:00Z",manifest=manifest)
    assert r["status"]=="MERGED_FIRST_PARTY_FUNDING_INTO_5M_BARS"
    assert len(r["normalized_outputs"])==3
    assert all(x["bar_count"]==3 for x in r["normalized_outputs"])
    assert all(x["funding_events_merged"]==1 for x in r["normalized_outputs"])
    assert manifest.exists()


def test_batch_missing_symbol_source_fails(tmp_path:Path):
    bars_root=tmp_path/"bars";funding_root=tmp_path/"funding"
    _bars(bars_root/"BTC-5m-2024-07-01_2024-07-01.csv","BTC")
    _funding(funding_root/"BTC-funding.csv")
    try:
        run_batch(bars_root=bars_root,funding_root=funding_root,output_root=tmp_path/"out",start_utc="2024-07-01T00:00:00Z",end_utc="2024-07-01T00:15:00Z",manifest=tmp_path/"m.json")
        assert False,"expected failure"
    except RuntimeError as exc:
        assert "missing" in str(exc)
