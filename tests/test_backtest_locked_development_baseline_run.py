from pathlib import Path
import csv,json

import pytest

from app.backtest.locked_development_baseline_run import LockedThresholds,_signal_fn
from app.backtest.historical import HistoricalBar
from app.backtest.io import HistoricalContext


def _contexts(trend="UNKNOWN"):
    out=[]
    price=100.0
    for i in range(25):
        price*=0.9985
        bar=HistoricalBar(f"2024-07-01T00:{i*5:02d}:00Z","BTC","5m",price,price,price,price,1.0,0.0)
        out.append(HistoricalContext(bar,100_000.0,200_000.0,None,trend))
    return out


def test_signal_respects_locked_liquidity_and_htf():
    permitted=_contexts("UP")
    sig=_signal_fn(permitted,LockedThresholds())(tuple(x.bar for x in permitted))
    assert sig is not None and sig.side=="LONG"

    blocked=[HistoricalContext(x.bar,x.open_interest_usd,x.volume_24h_usd,x.htf_regime_aligned,"DOWN") for x in permitted]
    assert _signal_fn(blocked,LockedThresholds())(tuple(x.bar for x in blocked)) is None

    thin=[HistoricalContext(x.bar,74_999.0,x.volume_24h_usd,x.htf_regime_aligned,"UP") for x in permitted]
    assert _signal_fn(thin,LockedThresholds())(tuple(x.bar for x in thin)) is None


def test_thresholds_are_locked_defaults():
    t=LockedThresholds()
    assert t.min_open_interest_usd==75_000.0
    assert t.min_volume_24h_usd==150_000.0
    assert t.rsi_long_max==28.0
    assert t.rsi_short_min==72.0
    assert t.min_extension_pct==1.4
    assert t.max_extension_pct==3.5
    assert t.min_rr==1.8
    assert t.htf_alignment_enabled is True
