from app.backtest.htf_context import HtfClose,derive_1h_trend_by_timestamp,htf_allows_side,trend_from_completed_closes
from app.backtest.historical import HistoricalBar
from app.backtest.perp_micro_baseline import PerpMicroBaselineConfig,locked_perp_micro_signal


def test_production_trend_boundaries_and_side_semantics():
    flat=[100.0]*19
    assert trend_from_completed_closes(flat+[100.0])=="FLAT"
    assert trend_from_completed_closes(flat+[101.0])=="UP"
    assert trend_from_completed_closes(flat+[99.0])=="DOWN"
    assert htf_allows_side("LONG","UP") is True;assert htf_allows_side("SHORT","UP") is False
    assert htf_allows_side("SHORT","DOWN") is True;assert htf_allows_side("LONG","DOWN") is False
    assert htf_allows_side("LONG","FLAT") is True;assert htf_allows_side("SHORT","UNKNOWN") is True


def test_unfinished_hourly_candle_is_never_visible():
    hourly=[HtfClose(f"2026-01-01T{h:02d}:00:00Z",100.0) for h in range(20)]
    # 19:30 cannot see the 19:00 candle; only 19 completed closes -> UNKNOWN.
    # 20:00 can see it; all 20 are flat.
    out=derive_1h_trend_by_timestamp(["2026-01-01T19:30:00Z","2026-01-01T20:00:00Z"],hourly)
    assert out["2026-01-01T19:30:00Z"]=="UNKNOWN"
    assert out["2026-01-01T20:00:00Z"]=="FLAT"


def _bars(closes):
    return [HistoricalBar(f"2026-01-01T00:{i:02d}:00Z","BTC","5m",c,c+0.2,c-0.2,c,1) for i,c in enumerate(closes)]


def test_locked_signal_uses_side_aware_htf_trend_not_generic_alignment():
    cfg=PerpMicroBaselineConfig(28,72,1.4,3.5,1.8,1.0,True,True)
    history=_bars([100]*14+[99.8,99.5,99.2,98.9,98.6,98.3])
    # Same oversold long candidate: production UP permits long, DOWN blocks fading it.
    assert locked_perp_micro_signal(history,config=cfg,oi_volume_eligible=True,htf_trend="UP") is not None
    assert locked_perp_micro_signal(history,config=cfg,oi_volume_eligible=True,htf_trend="DOWN") is None
