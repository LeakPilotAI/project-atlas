"""A Yahoo consensus cache is never a partial or contradictory valuation window."""
from datetime import datetime, timezone, timedelta
from app.investment.quality_dips_v2_target_cache import QualityDipsV2TargetCache


def test_cache_requires_complete_ordered_original_dated_snapshot():
    cache = QualityDipsV2TargetCache()
    now = datetime.now(timezone.utc)
    base = {"original_target_as_of_verified": True,
            "original_target_as_of": (now - timedelta(days=1)).isoformat(),
            "targets": {"low": 100, "mean": 120, "high": 140}}
    cache._rows["AVGO"] = base
    assert len(cache.sources("AVGO")) == 3
    for targets in ({"low": 100, "mean": 120}, {"low": 130, "mean": 120, "high": 140},
                    {"low": 100, "mean": 120, "high": float("inf")}):
        cache._rows["AVGO"] = {**base, "targets": targets}
        assert cache.sources("AVGO") == []
    cache._rows["AVGO"] = {**base, "original_target_as_of": (now + timedelta(days=1)).isoformat()}
    assert cache.sources("AVGO") == []
    cache._rows["AVGO"] = {**base, "original_target_as_of_verified": False}
    assert cache.sources("AVGO") == []
