import csv
from pathlib import Path
from app.backtest.canonical_batch import run


def _write(path:Path,fields,rows):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("w",encoding="utf-8",newline="") as fh:
        w=csv.DictWriter(fh,fieldnames=fields);w.writeheader();w.writerows(rows)


def test_canonical_batch_builds_three_symbols_and_excludes_sparse_oi(tmp_path:Path):
    funded=tmp_path/"funded";oi=tmp_path/"oi";vol=tmp_path/"vol";htf=tmp_path/"htf";out=tmp_path/"canonical";manifest=tmp_path/"batch.json"
    ts=["2024-07-01T00:00:00Z","2024-07-01T00:05:00Z"]
    for symbol in ("BTC","ETH","SOL"):
        _write(funded/f"{symbol}-5m-funded.csv",["timestamp","symbol","timeframe","open","high","low","close","volume","funding_rate"],[
            {"timestamp":t,"symbol":symbol,"timeframe":"5m","open":1,"high":2,"low":1,"close":2,"volume":3,"funding_rate":0} for t in ts])
        oi_rows=[{"timestamp":ts[0],"open_interest_usd":100}]
        if symbol!="BTC":oi_rows.append({"timestamp":ts[1],"open_interest_usd":110})
        _write(oi/f"{symbol}-oi-5m.csv",["timestamp","open_interest_usd"],oi_rows)
        _write(vol/f"{symbol}-volume24h-5m.csv",["timestamp","volume_24h_usd"],[{"timestamp":t,"volume_24h_usd":1000} for t in ts])
        _write(htf/f"{symbol}-htf-5m.csv",["timestamp","htf_trend"],[{"timestamp":t,"htf_trend":"FLAT"} for t in ts])
    r=run(funded_root=funded,oi_root=oi,volume_root=vol,htf_root=htf,output_root=out,manifest_path=manifest,start="2024-07-01T00:00:00Z",end="2024-07-01T00:10:00Z")
    assert r["normalized_outputs"]==3
    assert r["status"]=="ASSEMBLED_CANONICAL_PIT_DATASETS"
    by_symbol={x["symbol"]:x for x in r["outputs"]}
    assert by_symbol["BTC"]["excluded_incomplete_rows"]==1
    assert by_symbol["ETH"]["excluded_incomplete_rows"]==0
    assert by_symbol["SOL"]["excluded_incomplete_rows"]==0
    for symbol in ("BTC","ETH","SOL"):
        assert (out/f"{symbol}-5m.csv").is_file()
        assert (out/f"{symbol}-5m.csv.manifest.json").is_file()
