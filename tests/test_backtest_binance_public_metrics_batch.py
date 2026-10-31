from pathlib import Path
from app.backtest.binance_public_metrics_batch import _dates,run


def test_dates_half_open_daily_window():
    assert _dates("2024-07-01T00:00:00Z","2024-07-03T00:00:00Z")==["2024-07-01","2024-07-02"]


def test_plan_full_h2_object_count(tmp_path:Path):
    r=run(start_utc="2024-07-01T00:00:00Z",end_utc="2025-01-01T00:00:00Z",raw_root=tmp_path/"raw",output_root=tmp_path/"out",execute=False)
    assert r["object_count"]==552
    assert r["normalized_output_count"]==0
    assert r["pit_oi_context_complete"] is False
    assert r["rolling_volume_context_complete"] is False
    assert r["live_capital_allowed"] is False
    assert r["status"]=="PLANNED_NOT_DOWNLOADED"
