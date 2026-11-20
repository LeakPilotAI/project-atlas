"""Receipt-time timestamp policy, deterministic fake providers only."""
import asyncio
from datetime import UTC, datetime, timedelta

import pandas as pd
import pytest
from app.investment import quality_dip_quotes as module

NOW = datetime(2026, 10, 16, 12, tzinfo=UTC)

@pytest.mark.parametrize("provider", ["rh", "history", "info"])
@pytest.mark.parametrize("age,quality", [(0,"LIVE"),(120,"LIVE"),(120.001,"FRESH"),
                                         (900,"FRESH"),(900.001,"REFERENCE"),(345600,"REFERENCE"),(345600.001,"STALE"),(-0.001,"MISSING")])
def test_latency_age_and_future_boundaries(monkeypatch, provider, age, quality):
    class Clock(datetime):
        value = NOW
        @classmethod
        def now(cls, tz=None): return cls.value
    class RH:
        async def get_quote(self, symbol):
            Clock.value = NOW + timedelta(seconds=2)
            if provider != "rh": return {}
            return {"price":250,"effective_timestamp":(Clock.value-timedelta(seconds=age)).isoformat()}
    class Yahoo:
        async def history(self, *a, **kw):
            Clock.value = NOW + timedelta(seconds=4)
            if provider != "history": return pd.DataFrame()
            return pd.DataFrame({"Close":[250]},index=pd.DatetimeIndex([Clock.value-timedelta(seconds=age)]))
        async def info(self, *a, **kw):
            if provider == "info":
                Clock.value = NOW + timedelta(seconds=6)
                return {"currentPrice":250,"regularMarketTime":(Clock.value-timedelta(seconds=age)).timestamp()}
            return {}
    monkeypatch.setattr(module,"datetime",Clock)
    result=asyncio.run(module.QualityDipQuoteService(client=Yahoo(),robinhood_client=RH())._fetch("TEST"))
    assert result["quality"] == quality
    if quality != "MISSING":
        assert result["age_sec"] == round(age,1)
        assert result["tradable_for_ladder"] == (quality in {"LIVE","FRESH"})
        assert result["retrieved_at"] == Clock.value.isoformat()
    else: assert result["price"] is None

@pytest.mark.parametrize("timestamp", [None,"invalid","2026-10-16T12:00:00"])
def test_missing_invalid_naive_rh_time_is_not_authoritative(monkeypatch,timestamp):
    class Clock(datetime):
        @classmethod
        def now(cls,tz=None): return NOW
    class RH:
        async def get_quote(self,symbol): return {"price":250,"effective_timestamp":timestamp}
    class Yahoo:
        async def history(self,*a,**kw): return pd.DataFrame()
        async def info(self,*a,**kw): return {}
    monkeypatch.setattr(module,"datetime",Clock)
    result=asyncio.run(module.QualityDipQuoteService(client=Yahoo(),robinhood_client=RH())._fetch("TEST"))
    assert result["quality"] == "MISSING"


def test_history_age_includes_subsequent_info_latency(monkeypatch):
    class Clock(datetime):
        value = NOW
        @classmethod
        def now(cls,tz=None): return cls.value
    class RH:
        async def get_quote(self,symbol): return {}
    class Yahoo:
        async def history(self,*a,**kw):
            return pd.DataFrame({"Close":[250]},index=pd.DatetimeIndex([NOW-timedelta(seconds=119)]))
        async def info(self,*a,**kw):
            Clock.value = NOW+timedelta(seconds=2)
            return {}
    monkeypatch.setattr(module,"datetime",Clock)
    result=asyncio.run(module.QualityDipQuoteService(client=Yahoo(),robinhood_client=RH())._fetch("TEST"))
    assert result["quality"] == "FRESH" and result["age_sec"] == 121
