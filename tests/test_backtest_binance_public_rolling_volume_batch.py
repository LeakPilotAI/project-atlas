from pathlib import Path
from app.backtest.binance_public_rolling_volume_batch import run


def test_plan_full_h2_includes_warmup_month(tmp_path:Path):
    r=run(start_utc="2024-07-01T00:00:00Z",end_utc="2025-01-01T00:00:00Z",raw_root=tmp_path/"raw",output_root=tmp_path/"out",execute=False)
    assert r["warmup_start_utc"]=="2024-06-30T00:00:00Z"
    assert r["object_count"]==21
    assert r["normalized_output_count"]==0
    assert r["pit_rolling_volume_context_complete"] is False
    assert r["current_state_backfill_used"] is False
    assert r["status"]=="PLANNED_NOT_DOWNLOADED"


def test_plan_rejects_unknown_symbol(tmp_path:Path):
    try:
        run(start_utc="2024-07-01T00:00:00Z",end_utc="2025-01-01T00:00:00Z",raw_root=tmp_path/"raw",output_root=tmp_path/"out",symbols=("DOGE",),execute=False)
    except ValueError as e:assert "unsupported symbols" in str(e)
    else:raise AssertionError("expected unsupported symbol failure")
