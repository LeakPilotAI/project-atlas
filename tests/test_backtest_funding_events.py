from app.backtest.hyperliquid_import import HistoricalMarketContext,normalize_hyperliquid_history


def _candle(ts:int,px:float=100.0):
    return {"time":ts,"open":px,"high":px+1,"low":px-1,"close":px,"volume":10}


def _ctx(ts:str):
    return HistoricalMarketContext(ts,100_000,200_000,htf_trend="FLAT")


def test_funding_event_is_not_carried_across_5m_bars():
    base=1767225600000  # 2026-01-01T00:00:00Z
    candles=[_candle(base),_candle(base+300_000),_candle(base+600_000)]
    contexts=[
        _ctx("2026-01-01T00:00:00Z"),
        _ctx("2026-01-01T00:05:00Z"),
        _ctx("2026-01-01T00:10:00Z"),
    ]
    rows=normalize_hyperliquid_history(symbol="BTC",timeframe="5m",candles=candles,funding_history=[{"time":base,"fundingRate":"0.0001"}],historical_context=contexts)
    assert [r.bar.funding_rate for r in rows]==[0.0001,0.0,0.0]


def test_funding_events_apply_only_at_their_exact_timestamps():
    base=1767225600000
    hour=base+3_600_000
    candles=[_candle(base),_candle(base+300_000),_candle(hour)]
    contexts=[
        _ctx("2026-01-01T00:00:00Z"),
        _ctx("2026-01-01T00:05:00Z"),
        _ctx("2026-01-01T01:00:00Z"),
    ]
    funding=[{"time":base,"fundingRate":"0.0001"},{"time":hour,"fundingRate":"-0.0002"}]
    rows=normalize_hyperliquid_history(symbol="BTC",timeframe="5m",candles=candles,funding_history=funding,historical_context=contexts)
    assert [r.bar.funding_rate for r in rows]==[0.0001,0.0,-0.0002]


def test_conflicting_duplicate_funding_event_fails_closed():
    base=1767225600000
    candles=[_candle(base)]
    contexts=[_ctx("2026-01-01T00:00:00Z")]
    funding=[{"time":base,"fundingRate":"0.0001"},{"time":base,"fundingRate":"0.0002"}]
    try:
        normalize_hyperliquid_history(symbol="BTC",timeframe="5m",candles=candles,funding_history=funding,historical_context=contexts)
    except ValueError as exc:
        assert "conflicting funding events" in str(exc)
    else:
        raise AssertionError("conflicting duplicate funding events must fail closed")
