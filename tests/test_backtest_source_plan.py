import json
from pathlib import Path
import pytest

from app.backtest.source_plan import HistoricalSourcePlan,representative_plans,write_source_plan


def test_representative_plans_lock_btc_eth_sol_and_sources():
    plans=representative_plans(start_utc="2026-01-01T00:00:00Z",end_utc="2026-02-01T00:00:00Z")
    assert [p.symbol for p in plans]==["BTC","ETH","SOL"]
    assert all(p.timeframe=="5m" for p in plans)
    assert all("0xarchive" in p.oi_source for p in plans)
    assert all("candleSnapshot:5m" in p.candles_source for p in plans)
    assert all("fundingHistory" in p.funding_source for p in plans)
    assert all("1h" in p.htf_source for p in plans)


def test_plan_emits_deterministic_operator_paths_and_safety_flags(tmp_path:Path):
    out=write_source_plan(tmp_path/"source-plan.json",start_utc="2026-01-01T00:00:00Z",end_utc="2026-02-01T00:00:00Z",raw_root=Path("raw"))
    payload=json.loads(out.read_text(encoding="utf-8"))
    assert payload["live_capital_allowed"] is False
    assert payload["automatic_real_money_execution"] is False
    assert payload["requirements"]["current_state_backfill_allowed"] is False
    btc=payload["plans"][0]
    assert btc["raw_paths"]["candles"].endswith("BTC-5m.candles.json")
    assert btc["raw_paths"]["open_interest"].endswith("BTC-5m.oi.json")
    assert btc["raw_paths"]["htf_candles"].endswith("BTC-1h.candles.json")


def test_invalid_representative_plan_fails_closed():
    with pytest.raises(ValueError,match="BTC, ETH, or SOL"):
        HistoricalSourcePlan("DOGE","5m","2026-01-01T00:00:00Z","2026-02-01T00:00:00Z","a","b","c","d","e").validate()
    with pytest.raises(ValueError,match="timeframe must be 5m"):
        HistoricalSourcePlan("BTC","1m","2026-01-01T00:00:00Z","2026-02-01T00:00:00Z","a","b","c","d","e").validate()
    with pytest.raises(ValueError,match="explicit UTC Z"):
        HistoricalSourcePlan("BTC","5m","2026-01-01","2026-02-01T00:00:00Z","a","b","c","d","e").validate()
