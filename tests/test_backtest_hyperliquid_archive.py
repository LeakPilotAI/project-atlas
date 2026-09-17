from datetime import date
from pathlib import Path
import pytest
from app.backtest.hyperliquid_archive import archive_uri,plan


def test_archive_uri_matches_official_asset_ctxs_layout():
    assert archive_uri(date(2024,7,1))=="s3://hyperliquid-archive/asset_ctxs/20240701.csv.lz4"


def test_plan_is_half_open_deterministic_and_research_only(tmp_path:Path):
    payload=plan(start_utc="2024-07-01T00:00:00Z",end_utc="2024-07-03T00:00:00Z",raw_root=tmp_path)
    assert [x["day"] for x in payload["objects"]]==["2024-07-01","2024-07-02"]
    local_path=Path(payload["objects"][0]["local_path"])
    assert local_path.name=="20240701.csv.lz4"
    assert local_path.parent.name=="asset_ctxs"
    assert payload["request_payer"]=="requester"
    assert payload["live_capital_allowed"] is False
    assert payload["automatic_real_money_execution"] is False
    assert payload["current_state_backfill_allowed"] is False
    assert payload["schema_status"]=="MUST_INSPECT_ACQUIRED_RAW_HEADER_BEFORE_NORMALIZATION"


def test_full_dev_2024_h2_plan_has_184_daily_objects(tmp_path:Path):
    payload=plan(start_utc="2024-07-01T00:00:00Z",end_utc="2025-01-01T00:00:00Z",raw_root=tmp_path)
    assert len(payload["objects"])==184
    assert payload["objects"][0]["uri"].endswith("20240701.csv.lz4")
    assert payload["objects"][-1]["uri"].endswith("20241231.csv.lz4")


def test_invalid_range_fails_closed(tmp_path:Path):
    with pytest.raises(ValueError,match="start must precede end"):
        plan(start_utc="2025-01-01T00:00:00Z",end_utc="2025-01-01T00:00:00Z",raw_root=tmp_path)
