import csv,json
from pathlib import Path
from app.backtest.import_cli import import_dataset
from app.backtest.io import load_historical_contexts
from app.backtest.manifest import load_manifest


def _write(path:Path,fields,rows):
    with path.open("w",encoding="utf-8",newline="") as fh:
        w=csv.DictWriter(fh,fieldnames=fields);w.writeheader();w.writerows(rows)


def sources(tmp_path:Path):
    candles=tmp_path/"candles.csv";funding=tmp_path/"funding.csv";context=tmp_path/"context.csv"
    ts=[1767225600000,1767225900000]
    _write(candles,["time","open","high","low","close","volume"],[{"time":ts[0],"open":100,"high":101,"low":99,"close":100,"volume":10},{"time":ts[1],"open":100,"high":102,"low":99,"close":101,"volume":12}])
    _write(funding,["time","funding_rate"],[{"time":ts[0],"funding_rate":0.0001}])
    _write(context,["timestamp","open_interest_usd","volume_24h_usd","htf_regime_aligned"],[{"timestamp":"2026-01-01T00:00:00Z","open_interest_usd":80000,"volume_24h_usd":200000,"htf_regime_aligned":"true"},{"timestamp":"2026-01-01T00:05:00Z","open_interest_usd":81000,"volume_24h_usd":201000,"htf_regime_aligned":"false"}])
    return candles,funding,context


def test_import_emits_canonical_dataset_and_verified_manifest(tmp_path:Path):
    candles,funding,context=sources(tmp_path);out=tmp_path/"BTC-5m.csv"
    dataset,manifest_path=import_dataset(symbol="BTC",timeframe="5m",candles_path=candles,funding_path=funding,context_path=context,output_path=out,candles_source="hyperliquid:candleSnapshot",funding_source="hyperliquid:fundingHistory",oi_source="vendor:historical-oi",rolling_volume_source="vendor:historical-volume",htf_context_source="atlas:pit-derived-htf")
    rows=load_historical_contexts(dataset);assert len(rows)==2;assert rows[0].open_interest_usd==80000;assert rows[1].htf_regime_aligned is False
    manifest=load_manifest(manifest_path,dataset);assert manifest["symbol"]=="BTC";assert manifest["pit_aligned"] is True;assert manifest["current_state_backfill_used"] is False
    assert "raw_sha256=" in manifest["notes"]
    hashes=json.loads(manifest["notes"].split("raw_sha256=",1)[1]);assert set(hashes)=={"candles","funding","context"};assert all(len(v)==64 for v in hashes.values())


def test_import_fails_closed_when_context_missing_timestamp(tmp_path:Path):
    candles,funding,context=sources(tmp_path)
    lines=context.read_text(encoding="utf-8").splitlines();context.write_text("\n".join(lines[:2])+"\n",encoding="utf-8")
    try:import_dataset(symbol="BTC",timeframe="5m",candles_path=candles,funding_path=funding,context_path=context,output_path=tmp_path/"out.csv",candles_source="c",funding_source="f",oi_source="o",rolling_volume_source="v",htf_context_source="h")
    except ValueError as e:assert "missing point-in-time" in str(e)
    else:raise AssertionError("missing PIT context must fail closed")


def test_import_requires_real_source_files(tmp_path:Path):
    candles,funding,context=sources(tmp_path)
    try:import_dataset(symbol="BTC",timeframe="5m",candles_path=candles,funding_path=funding,context_path=tmp_path/"missing.csv",output_path=tmp_path/"out.csv",candles_source="c",funding_source="f",oi_source="o",rolling_volume_source="v",htf_context_source="h")
    except ValueError as e:assert "raw source file not found" in str(e)
    else:raise AssertionError("missing raw source must fail closed")
