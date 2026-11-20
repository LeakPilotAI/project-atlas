import csv,json
from pathlib import Path
import pytest
from app.backtest import locked_development_baseline as mod

FIELDS=["timestamp","symbol","timeframe","open","high","low","close","volume","funding_rate","open_interest_usd","volume_24h_usd","htf_trend"]

def _write_dataset(root:Path,symbol:str):
    path=root/f"{symbol}-5m.csv"
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("w",newline="",encoding="utf-8") as fh:
        w=csv.DictWriter(fh,fieldnames=FIELDS);w.writeheader()
        w.writerow({"timestamp":"2024-07-01T00:00:00Z","symbol":symbol,"timeframe":"5m","open":1,"high":1,"low":1,"close":1,"volume":1,"funding_rate":0,"open_interest_usd":100000,"volume_24h_usd":200000,"htf_trend":"FLAT"})
    manifest={"symbol":symbol,"timeframe":"5m","first_timestamp":"2024-07-01T00:00:00Z","last_timestamp":"2024-07-01T00:00:00Z","row_count":1,"dataset_sha256":"x","candles_source":"c","funding_source":"f","oi_source":"o","rolling_volume_source":"v","htf_context_source":"h","pit_aligned":True,"current_state_backfill_used":False,"manifest_id":"m","notes":"raw_sha256=abc"}
    return path,manifest

def test_run_requires_green_audit(monkeypatch,tmp_path:Path):
    monkeypatch.setattr(mod,"audit_representative_bundle",lambda *a,**k:{"ready_for_locked_baseline_batch":False,"audit_id":"bad"})
    with pytest.raises(RuntimeError,match="source audit is not GREEN"):
        mod.run(canonical_root=tmp_path,output=tmp_path/"out.json")

def test_run_freezes_inputs_without_holdout_or_live(monkeypatch,tmp_path:Path):
    for s in mod.SYMBOLS:_write_dataset(tmp_path,s)
    monkeypatch.setattr(mod,"audit_representative_bundle",lambda *a,**k:{"ready_for_locked_baseline_batch":True,"audit_id":"green123"})
    result=mod.run(canonical_root=tmp_path,output=tmp_path/"out.json")
    assert result["source_audit_green"] is True
    assert result["threshold_retuning_allowed"] is False
    assert result["holdout_data_touched"] is False
    assert result["live_capital_allowed"] is False
    assert result["status"]=="LOCKED_DEVELOPMENT_BASELINE_INPUTS_FROZEN"
    assert len(result["datasets"])==3
