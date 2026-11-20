from pathlib import Path
import pytest

from app.backtest.hyperliquid_import import HistoricalMarketContext,normalize_hyperliquid_history,write_canonical_csv
from app.backtest.io import load_historical_contexts


def test_normalize_requires_timestamp_aligned_context_and_discrete_funding_events(tmp_path:Path):
    candles=[
        {"time":1767225600000,"open":100,"high":101,"low":99,"close":100,"volume":10},
        {"time":1767225900000,"open":100,"high":102,"low":99,"close":101,"volume":12},
    ]
    contexts=[
        HistoricalMarketContext("2026-01-01T00:00:00Z",80000,200000,True),
        HistoricalMarketContext("2026-01-01T00:05:00Z",81000,210000,False),
    ]
    # A prior hourly funding event must not be carried forward onto later 5m bars.
    funding=[{"time":1767222000000,"funding_rate":0.0001}]
    rows=normalize_hyperliquid_history(symbol="BTC",timeframe="5m",candles=candles,funding_history=funding,historical_context=contexts)
    assert len(rows)==2
    assert rows[0].bar.funding_rate==0.0
    assert rows[1].bar.funding_rate==0.0
    assert rows[1].open_interest_usd==81000
    assert rows[1].htf_regime_aligned is False
    out=write_canonical_csv(rows,tmp_path/"btc.csv")
    loaded=load_historical_contexts(out)
    assert loaded==rows


def test_exact_timestamp_funding_event_is_attached_once():
    candles=[
        {"time":1767225600000,"open":100,"high":101,"low":99,"close":100,"volume":10},
        {"time":1767225900000,"open":100,"high":102,"low":99,"close":101,"volume":12},
    ]
    contexts=[
        HistoricalMarketContext("2026-01-01T00:00:00Z",80000,200000,True),
        HistoricalMarketContext("2026-01-01T00:05:00Z",81000,210000,False),
    ]
    funding=[{"time":1767225600000,"funding_rate":0.0001}]
    rows=normalize_hyperliquid_history(symbol="BTC",timeframe="5m",candles=candles,funding_history=funding,historical_context=contexts)
    assert rows[0].bar.funding_rate==0.0001
    assert rows[1].bar.funding_rate==0.0


def test_missing_historical_context_fails_closed():
    candles=[{"time":1767225600000,"open":100,"high":101,"low":99,"close":100,"volume":10}]
    with pytest.raises(ValueError,match="missing point-in-time"):
        normalize_hyperliquid_history(symbol="BTC",timeframe="5m",candles=candles,funding_history=[],historical_context=[])


def test_duplicate_context_and_out_of_order_candles_fail_closed():
    dup=[HistoricalMarketContext("2026-01-01T00:00:00Z",80000,200000,True),HistoricalMarketContext("2026-01-01T00:00:00Z",80000,200000,True)]
    with pytest.raises(ValueError,match="duplicate historical context"):
        normalize_hyperliquid_history(symbol="BTC",timeframe="5m",candles=[{"time":1767225600000,"open":1,"high":1,"low":1,"close":1,"volume":1}],funding_history=[],historical_context=dup)
    contexts=[HistoricalMarketContext("2026-01-01T00:05:00Z",80000,200000,True),HistoricalMarketContext("2026-01-01T00:00:00Z",80000,200000,True)]
    candles=[{"time":1767225900000,"open":1,"high":1,"low":1,"close":1,"volume":1},{"time":1767225600000,"open":1,"high":1,"low":1,"close":1,"volume":1}]
    with pytest.raises(ValueError,match="unique ascending"):
        normalize_hyperliquid_history(symbol="BTC",timeframe="5m",candles=candles,funding_history=[],historical_context=contexts)
