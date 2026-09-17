from app.backtest.historical import HistoricalBar
from app.backtest.perp_micro_baseline import PerpMicroBaselineConfig,baseline_metadata,locked_perp_micro_signal
from app.core.config import Settings


def make_bars(closes):
    out=[]
    for i,c in enumerate(closes):
        out.append(HistoricalBar(f"2026-01-01T00:{i:02d}:00Z","BTC","5m",c,c+1,c-1,c,1000))
    return out


def test_locked_config_reads_production_thresholds_without_mutation():
    s=Settings()
    before=(s.perp_micro_rsi_long,s.perp_micro_rsi_short,s.perp_micro_min_extension_pct,s.perp_micro_max_extension_pct,s.perp_micro_min_rr,s.perp_micro_risk_usd)
    cfg=PerpMicroBaselineConfig.from_settings(s)
    assert (cfg.rsi_long,cfg.rsi_short,cfg.min_extension_pct,cfg.max_extension_pct,cfg.min_rr,cfg.risk_usd)==before
    assert (s.perp_micro_rsi_long,s.perp_micro_rsi_short,s.perp_micro_min_extension_pct,s.perp_micro_max_extension_pct,s.perp_micro_min_rr,s.perp_micro_risk_usd)==before


def test_missing_non_ohlcv_production_inputs_fail_closed():
    cfg=PerpMicroBaselineConfig(28,72,1.4,3.5,1.8,1.0,True,True)
    bars=make_bars([100]*14+[95,94,93,92,91,90])
    assert locked_perp_micro_signal(bars,config=cfg) is None
    assert locked_perp_micro_signal(bars,config=cfg,oi_volume_eligible=True) is None


def test_long_and_short_signals_respect_locked_thresholds_when_external_gates_are_supplied():
    cfg=PerpMicroBaselineConfig(28,72,1.4,3.5,1.8,1.0,True,True)
    long_bars=make_bars([100]*14+[99,98,97,96,95,94])
    long_signal=locked_perp_micro_signal(long_bars,config=cfg,oi_volume_eligible=True,htf_regime_aligned=True)
    assert long_signal is not None;assert long_signal.side=="LONG"
    assert round((long_signal.target_price-long_bars[-1].close)/(long_bars[-1].close-long_signal.stop_price),10)==1.8
    short_bars=make_bars([100]*14+[101,102,103,104,105,106])
    short_signal=locked_perp_micro_signal(short_bars,config=cfg,oi_volume_eligible=True,htf_regime_aligned=True)
    assert short_signal is not None;assert short_signal.side=="SHORT"
    assert round((short_bars[-1].close-short_signal.target_price)/(short_signal.stop_price-short_bars[-1].close),10)==1.8


def test_extension_bounds_and_metadata_safety():
    cfg=PerpMicroBaselineConfig(28,72,1.4,3.5,1.8,1.0,False,False)
    weak=make_bars([100]*19+[99.5]);assert locked_perp_micro_signal(weak,config=cfg) is None
    extreme=make_bars([100]*14+[90,85,80,75,70,65]);assert locked_perp_micro_signal(extreme,config=cfg) is None
    meta=baseline_metadata(cfg)
    assert meta["name"]=="LOCKED_PERP_MICRO_BASELINE";assert meta["rsi_long"]==28;assert meta["rsi_short"]==72;assert meta["min_extension_pct"]==1.4;assert meta["max_extension_pct"]==3.5;assert meta["min_rr"]==1.8
    assert meta["production_strategy_modified"] is False;assert meta["live_capital_allowed"] is False;assert meta["automatic_real_money_execution"] is False
