from pathlib import Path
from app.backtest.historical import BacktestAssumptions,BacktestSignal,HistoricalBar,persist_backtest_result,run_historical_backtest


def bars():
    return [
        HistoricalBar("2026-01-01T00:00:00Z","BTC","5m",100,101,99,100,10),
        HistoricalBar("2026-01-01T00:05:00Z","BTC","5m",100,101,99,100,10),
        HistoricalBar("2026-01-01T00:10:00Z","BTC","5m",100,102,99,101,10),
        HistoricalBar("2026-01-01T00:15:00Z","BTC","5m",101,104,100,103,10),
        HistoricalBar("2026-01-01T00:20:00Z","BTC","5m",103,106,102,105,10),
    ]


def test_signal_receives_only_point_in_time_history_and_fills_next_bar():
    seen=[]
    def signal(history):
        seen.append(tuple(x.timestamp for x in history))
        if len(history)==2:return BacktestSignal("LONG",98,104)
        return None
    r=run_historical_backtest(bars(),signal,BacktestAssumptions(fee_bps_per_fill=0,slippage_bps_per_fill=0))
    assert seen[1]==("2026-01-01T00:00:00Z","2026-01-01T00:05:00Z")
    t=r["trades"][0];assert t["signal_timestamp"]=="2026-01-01T00:05:00Z";assert t["entry_timestamp"]=="2026-01-01T00:10:00Z";assert t["entry_price"]==100
    assert t["exit_reason"]=="TARGET";assert t["exit_timestamp"]=="2026-01-01T00:20:00Z"


def test_costs_are_explicit_and_reduce_net_pnl():
    def signal(history):
        return BacktestSignal("LONG",98,104) if len(history)==2 else None
    free=run_historical_backtest(bars(),signal,BacktestAssumptions(fee_bps_per_fill=0,slippage_bps_per_fill=0))
    cost=run_historical_backtest(bars(),signal,BacktestAssumptions(fee_bps_per_fill=10,slippage_bps_per_fill=5))
    assert cost["metrics"]["fees_usd"]>0;assert cost["metrics"]["slippage_usd"]>0
    assert cost["trades"][0]["net_pnl_usd"]<free["trades"][0]["net_pnl_usd"]


def test_same_input_is_deterministic_and_persistence_is_idempotent(tmp_path:Path):
    def signal(history):
        return BacktestSignal("LONG",98,104) if len(history)==2 else None
    a=run_historical_backtest(bars(),signal);b=run_historical_backtest(bars(),signal)
    assert a==b;assert a["run_id"]==b["run_id"]
    p1=persist_backtest_result(a,tmp_path);p2=persist_backtest_result(b,tmp_path);assert p1==p2;assert p1.exists()


def test_research_only_safety_and_input_validation():
    def none(_):return None
    r=run_historical_backtest(bars(),none)
    assert r["mode"]=="RESEARCH_ONLY_HISTORICAL_BACKTEST";assert r["production_strategy_modified"] is False;assert r["live_capital_allowed"] is False;assert r["automatic_real_money_execution"] is False
    bad=list(reversed(bars()))
    try:run_historical_backtest(bad,none)
    except ValueError as e:assert "ascending timestamps" in str(e)
    else:raise AssertionError("descending data must fail closed")
