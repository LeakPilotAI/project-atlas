import csv
from pathlib import Path
from app.backtest.manifest import build_manifest,write_manifest
from app.backtest.source_audit import audit_dataset,audit_representative_bundle

FIELDS=["timestamp","symbol","timeframe","open","high","low","close","volume","funding_rate","open_interest_usd","volume_24h_usd","htf_regime_aligned"]

def dataset(root:Path,symbol:str):
    path=root/f"{symbol}-5m.csv";root.mkdir(parents=True,exist_ok=True)
    with path.open("w",encoding="utf-8",newline="") as fh:
        w=csv.DictWriter(fh,fieldnames=FIELDS);w.writeheader();w.writerow({"timestamp":"2026-01-01T00:00:00Z","symbol":symbol,"timeframe":"5m","open":100,"high":101,"low":99,"close":100,"volume":10,"funding_rate":0,"open_interest_usd":80000,"volume_24h_usd":200000,"htf_regime_aligned":"true"})
    m=build_manifest(path,candles_source="hyperliquid:candleSnapshot",funding_source="hyperliquid:fundingHistory",oi_source="vendor:historical-oi",rolling_volume_source="vendor:historical-volume",htf_context_source="atlas:pit-derived-htf",pit_aligned=True,notes='raw_sha256={"candles":"a","context":"b","funding":"c"}')
    mp=path.with_suffix(path.suffix+".manifest.json");write_manifest(m,mp);return path,mp


def test_representative_bundle_ready_only_when_all_three_verified(tmp_path:Path):
    for s in ("BTC","ETH","SOL"):dataset(tmp_path,s)
    result=audit_representative_bundle(tmp_path)
    assert result["ready_for_locked_baseline_batch"] is True
    assert all(x["ready"] for x in result["datasets"]);assert result["live_capital_allowed"] is False


def test_missing_symbol_dataset_blocks_batch(tmp_path:Path):
    dataset(tmp_path,"BTC");dataset(tmp_path,"ETH")
    result=audit_representative_bundle(tmp_path)
    assert result["ready_for_locked_baseline_batch"] is False
    sol=next(x for x in result["datasets"] if x["symbol"]=="SOL");assert "canonical dataset missing" in sol["reasons"]


def test_symbol_mismatch_and_missing_raw_provenance_fail_closed(tmp_path:Path):
    path,mp=dataset(tmp_path,"BTC")
    text=mp.read_text(encoding="utf-8").replace('"symbol": "BTC"','"symbol": "ETH"').replace('raw_sha256=','raw_hashes=')
    mp.write_text(text,encoding="utf-8")
    result=audit_dataset("BTC",path,mp)
    assert result.ready is False;assert "manifest symbol mismatch" in result.reasons;assert "raw source checksums missing from manifest notes" in result.reasons
