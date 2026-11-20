from pathlib import Path
import json
import app.backtest.binance_public_batch as batch


def test_plan_only_writes_36_object_manifest(tmp_path:Path):
    manifest=tmp_path/"batch.json"
    result=batch.run_batch(start_utc="2024-07-01T00:00:00Z",end_utc="2025-01-01T00:00:00Z",raw_root=tmp_path/"raw",output_root=tmp_path/"out",manifest=manifest,execute=False)
    assert result["batch_status"]=="PLANNED_NOT_DOWNLOADED"
    assert len(result["objects"])==36
    assert result["normalized_outputs"]==[]
    assert result["pit_context_complete"] is False
    payload=json.loads(manifest.read_text())
    assert payload["automatic_real_money_execution"] is False
    assert payload["live_capital_allowed"] is False


def test_execute_orchestrates_six_normalized_outputs(monkeypatch,tmp_path:Path):
    fake_plan={"objects":[],"automatic_real_money_execution":False,"live_capital_allowed":False}
    for symbol,provider in batch.PROVIDER.items():
        for interval in batch.INTERVALS:
            for month in ("2024-07","2024-08"):
                fake_plan["objects"].append({"symbol":symbol,"provider_symbol":provider,"interval":interval,"month":month,"local_zip":str(tmp_path/f"{provider}-{interval}-{month}.zip")})
    monkeypatch.setattr(batch,"plan",lambda **kwargs:fake_plan)
    monkeypatch.setattr(batch,"acquire",lambda payload:{**payload,"acquisition_status":"ACQUIRED_RAW_CANDLES_CHECKSUM_VERIFIED_CONTEXT_STILL_REQUIRED"})
    calls=[]
    def fake_normalize(**kwargs):
        calls.append(kwargs)
        kwargs["output"].parent.mkdir(parents=True,exist_ok=True);kwargs["output"].write_text("x")
        return {"symbol":kwargs["provider_symbol"].replace("USDT",""),"interval":kwargs["interval"],"row_count":1,"pit_context_complete":False}
    monkeypatch.setattr(batch,"normalize",fake_normalize)
    result=batch.run_batch(start_utc="2024-07-01T00:00:00Z",end_utc="2024-09-01T00:00:00Z",raw_root=tmp_path/"raw",output_root=tmp_path/"out",manifest=tmp_path/"m.json",execute=True)
    assert result["batch_status"]=="ACQUIRED_AND_NORMALIZED_CANDLES_CONTEXT_STILL_REQUIRED"
    assert len(result["normalized_outputs"])==6
    assert len(calls)==6
    assert all(len(c["inputs"])==2 for c in calls)
    assert result["pit_context_complete"] is False
