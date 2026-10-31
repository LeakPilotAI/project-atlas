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


def test_tampered_manifest_identity_fails_closed(tmp_path:Path):
    path, mp = dataset(tmp_path, "BTC")
    text = mp.read_text(encoding="utf-8").replace('"symbol": "BTC"', '"symbol": "ETH"')
    mp.write_text(text, encoding="utf-8")

    result = audit_dataset("BTC", path, mp)

    assert result.ready is False
    assert any("manifest integrity verification failed" in reason for reason in result.reasons)
    assert result.manifest_id is None


def test_symbol_mismatch_and_missing_raw_provenance_fail_closed(tmp_path:Path):
    import hashlib
    import json

    path, mp = dataset(tmp_path, "BTC")
    payload = json.loads(mp.read_text(encoding="utf-8"))

    payload["symbol"] = "ETH"
    payload["notes"] = payload["notes"].replace("raw_sha256=", "raw_hashes=")

    identity = {key: value for key, value in payload.items() if key != "manifest_id"}
    payload["manifest_id"] = hashlib.sha256(
        json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()[:20]

    mp.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")

    result = audit_dataset("BTC", path, mp)

    assert result.ready is False
    assert "manifest symbol mismatch" in result.reasons
    assert "raw source checksums missing from manifest notes" in result.reasons


def test_source_audit_exposes_conservative_availability_reporting(tmp_path:Path):
    path, manifest = dataset(tmp_path, "BTC")

    result = audit_dataset("BTC", path, manifest)

    assert result.ready is True
    assert result.integrity_verified is True
    assert result.historical_availability_authenticated is False
    assert result.historical_availability_classification == "CLAIMED_HISTORICAL_AVAILABILITY"

    bundle = audit_representative_bundle(tmp_path, symbols=("BTC",))
    entry = bundle["datasets"][0]

    assert bundle["ready_for_locked_baseline_batch"] is True
    assert entry["integrity_verified"] is True
    assert entry["historical_availability_authenticated"] is False
    assert entry["historical_availability_classification"] == "CLAIMED_HISTORICAL_AVAILABILITY"


def test_source_audit_refused_manifest_reports_no_authentication(tmp_path:Path):
    path, manifest = dataset(tmp_path, "BTC")
    manifest.write_text('{"invalid":true}', encoding="utf-8")

    result = audit_dataset("BTC", path, manifest)

    assert result.ready is False
    assert result.integrity_verified is False
    assert result.historical_availability_authenticated is False
    assert result.historical_availability_classification == "INTEGRITY_REFUSED"
