from __future__ import annotations

from app.investment.quality_dips_v2_runtime import enrich_research_row
from app.investment.quality_dips_v2_valuation import from_research_row


def _mv(value):
    return {"value": value, "availability": True, "effective_timestamp": "2026-09-17T12:00:00+00:00"}


def test_runtime_builds_quality_from_existing_scored_pillars():
    row = {"symbol": "MSFT", "components": {"fundamentals": 88, "balance_sheet": 82, "cash_flow": 86, "thesis_integrity": 90}}
    out = enrich_research_row(row)
    assert out["components"]["quality"] == 87.0
    assert out["quality_score_provenance"] == "MEDIAN_OF_SCORED_BUSINESS_PILLARS"


def test_runtime_extracts_explicit_provider_analyst_targets():
    row = {"symbol": "MSFT", "components": {"fundamentals": 88, "thesis_integrity": 90}, "input_snapshot": {"valuation": {"target_low_price": _mv(500), "target_mean_price": _mv(600), "target_high_price": _mv(700)}}}
    out = enrich_research_row(row)
    window = from_research_row(out)
    assert window["valuation_window_complete"] is True
    assert window["normalization_value"] == {"conservative": 500.0, "base": 600.0, "optimistic": 700.0}
    assert all(x["provenance"] == "ANALYST_CONSENSUS" for x in window["valuation_provenance"])


def test_runtime_does_not_invent_incomplete_targets():
    row = {"symbol": "ZZTEST_NO_CACHE", "components": {"fundamentals": 88, "thesis_integrity": 90}, "input_snapshot": {"valuation": {"target_mean_price": _mv(600)}}}
    out = enrich_research_row(row)
    window = from_research_row(out)
    assert window["valuation_window_complete"] is False
    assert window["normalization_value"]["conservative"] is None


def test_runtime_preserves_manual_only_v2_boundary():
    from app.investment.quality_dips_v2_board import build_v2_projection
    row = {"symbol": "MSFT", "timestamp": "2026-09-17T12:00:00+00:00", "price": 400, "evidence_quality": "HIGH", "thesis": "STRONG", "components": {"valuation": 92, "fundamentals": 92, "balance_sheet": 92, "cash_flow": 92, "thesis_integrity": 92}, "drawdown": {"percentile": 96}, "input_snapshot": {"valuation": {"target_low_price": _mv(600), "target_mean_price": _mv(650), "target_high_price": _mv(700)}}}
    out = build_v2_projection(row)
    assert out["normalization_value"]["conservative"] == 600.0
    assert out["conservative_upside_pct"] == 50.0
    assert out["execution"] == "MANUAL_ONLY"
    assert out["live_capital_allowed"] is False
    assert out["automatic_real_money_execution"] is False


def test_target_cache_schedule_refresh_is_non_blocking(monkeypatch):
    import asyncio
    from app.investment.quality_dips_v2_target_cache import QualityDipsV2TargetCache

    async def run():
        cache = QualityDipsV2TargetCache()
        cache._rows = {}
        started = asyncio.Event()
        release = asyncio.Event()

        async def slow_refresh(symbols):
            started.set()
            await release.wait()

        monkeypatch.setattr(cache, "refresh_many", slow_refresh)
        assert cache.schedule_refresh(["MSFT"]) is True
        await asyncio.wait_for(started.wait(), timeout=0.2)
        assert cache._refresh_task is not None
        assert cache._refresh_task.done() is False
        release.set()
        await cache._refresh_task

    asyncio.run(run())


def test_target_cache_transient_failure_preserves_last_good(monkeypatch):
    import asyncio
    from app.investment.quality_dips_v2_target_cache import QualityDipsV2TargetCache

    async def run():
        cache = QualityDipsV2TargetCache()
        old = {"targets": {"low": 100.0, "mean": 120.0, "high": 140.0}, "as_of": "2026-09-17T00:00:00+00:00", "fetched_at": "2020-01-01T00:00:00+00:00", "source": "yfinance_info", "complete": True}
        cache._rows = {"MSFT": old}

        async def fail_info(symbol):
            raise RuntimeError("provider down")

        monkeypatch.setattr(cache.client, "info", fail_info)
        monkeypatch.setattr(cache, "_save", lambda: None)
        await cache.refresh_many(["MSFT"])
        assert cache.get("MSFT") == old
        assert len(cache.sources("MSFT")) == 3

    asyncio.run(run())
