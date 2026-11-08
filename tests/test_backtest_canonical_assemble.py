import csv,json
from pathlib import Path
from app.backtest.canonical_assemble import assemble
from app.backtest.source_audit import audit_dataset


def _write(path:Path,fields,rows):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("w",encoding="utf-8",newline="") as fh:
        w=csv.DictWriter(fh,fieldnames=fields);w.writeheader();w.writerows(rows)


def test_canonical_assembly_excludes_missing_oi_without_fill(tmp_path:Path):
    bars=tmp_path/"bars.csv";oi=tmp_path/"oi.csv";vol=tmp_path/"vol.csv";htf=tmp_path/"htf.csv";out=tmp_path/"BTC-5m.csv";manifest=tmp_path/"BTC-5m.csv.manifest.json"
    ts=["2024-07-01T00:00:00Z","2024-07-01T00:05:00Z","2024-07-01T00:10:00Z"]
    _write(bars,["timestamp","symbol","timeframe","open","high","low","close","volume","funding_rate"],[
        {"timestamp":t,"symbol":"BTC","timeframe":"5m","open":1,"high":2,"low":1,"close":2,"volume":3,"funding_rate":0} for t in ts])
    _write(oi,["timestamp","open_interest_usd"],[{"timestamp":ts[0],"open_interest_usd":100},{"timestamp":ts[2],"open_interest_usd":120}])
    _write(vol,["timestamp","volume_24h_usd"],[{"timestamp":t,"volume_24h_usd":1000} for t in ts])
    _write(htf,["timestamp","htf_trend"],[{"timestamp":t,"htf_trend":"UP"} for t in ts])
    r=assemble(symbol="BTC",bars=bars,oi=oi,volume=vol,htf=htf,output=out,manifest=manifest)
    assert r["row_count"]==2
    assert r["excluded_incomplete_rows"]==1
    assert r["excluded_timestamps"]==[ts[1]]
    text=out.read_text();assert ts[1] not in text
    payload=json.loads(manifest.read_text())
    assert payload["pit_aligned"] is True
    assert payload["current_state_backfill_used"] is False
    assert "raw_sha256=" in payload["notes"]
    audit=audit_dataset("BTC",out,manifest)
    assert audit.ready is True


def test_canonical_assembly_keeps_funding_and_htf(tmp_path:Path):
    bars=tmp_path/"bars.csv";oi=tmp_path/"oi.csv";vol=tmp_path/"vol.csv";htf=tmp_path/"htf.csv";out=tmp_path/"BTC-5m.csv";manifest=tmp_path/"BTC-5m.csv.manifest.json"
    t="2024-07-01T00:00:00Z"
    _write(bars,["timestamp","symbol","timeframe","open","high","low","close","volume","funding_rate"],[{"timestamp":t,"symbol":"BTC","timeframe":"5m","open":1,"high":2,"low":1,"close":2,"volume":3,"funding_rate":"0.00001"}])
    _write(oi,["timestamp","open_interest_usd"],[{"timestamp":t,"open_interest_usd":100}]);_write(vol,["timestamp","volume_24h_usd"],[{"timestamp":t,"volume_24h_usd":1000}]);_write(htf,["timestamp","htf_trend"],[{"timestamp":t,"htf_trend":"DOWN"}])
    assemble(symbol="BTC",bars=bars,oi=oi,volume=vol,htf=htf,output=out,manifest=manifest)
    row=list(csv.DictReader(out.open()))[0]
    assert row["funding_rate"]=="0.00001"
    assert row["htf_trend"]=="DOWN"
