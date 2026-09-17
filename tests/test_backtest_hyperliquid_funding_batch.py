from pathlib import Path
from app.backtest import hyperliquid_funding_batch as mod


def test_batch_acquires_all_three_symbols(monkeypatch,tmp_path:Path):
    calls=[]
    def fake_acquire(*,symbol,start_utc,end_utc,output,report):
        calls.append(symbol)
        Path(output).parent.mkdir(parents=True,exist_ok=True)
        Path(output).write_text("timestamp,funding_rate\n2024-07-01T00:00:00Z,0.1\n",encoding="utf-8")
        return {"symbol":symbol,"row_count":1,"page_count":1,"first_timestamp":"2024-07-01T00:00:00Z","last_timestamp":"2024-07-01T00:00:00Z"}
    monkeypatch.setattr(mod,"acquire",fake_acquire)
    manifest=tmp_path/"manifest.json"
    result=mod.run_batch(start_utc="2024-07-01T00:00:00Z",end_utc="2025-01-01T00:00:00Z",output_root=tmp_path/"out",manifest=manifest)
    assert calls==["BTC","ETH","SOL"]
    assert len(result["normalized_outputs"])==3
    assert result["status"]=="ACQUIRED_FIRST_PARTY_FUNDING"
    assert result["interpolation_used"] is False
    assert result["current_state_backfill_used"] is False
    assert manifest.exists()


def test_batch_propagates_failure(monkeypatch,tmp_path:Path):
    def fake_acquire(**kwargs):
        if kwargs["symbol"]=="ETH":raise RuntimeError("boom")
        return {"symbol":kwargs["symbol"],"row_count":1,"page_count":1,"first_timestamp":"x","last_timestamp":"x"}
    monkeypatch.setattr(mod,"acquire",fake_acquire)
    import pytest
    with pytest.raises(RuntimeError,match="boom"):
        mod.run_batch(start_utc="2024-07-01T00:00:00Z",end_utc="2025-01-01T00:00:00Z",output_root=tmp_path/"out",manifest=tmp_path/"m.json")
