from dataclasses import replace

import pytest
from app.backtest.historical import (
    BacktestAssumptions,
    BacktestSignal,
    persist_backtest_result,
    run_historical_backtest,
)
from test_historical_backtest_foundation import bars


@pytest.mark.parametrize("options",[{"fee_bps_per_fill":-1},{"slippage_bps_per_fill":-1},
                                     {"risk_usd":0},{"initial_equity_usd":float('nan')},
                                     {"intrabar_priority":"TYPO"}])
def test_invalid_cost_or_risk_assumptions_are_never_successful_results(options):
    with pytest.raises(ValueError):run_historical_backtest(bars(),lambda _:None,BacktestAssumptions(**options))


@pytest.mark.parametrize("change",[{"close":float('nan')},{"volume":-1},{"funding_rate":float('inf')},
                                    {"open":200},{"high":True}])
def test_invalid_market_numbers_refuse_even_when_no_trade_occurs(change):
    rows=bars();rows[1]=replace(rows[1],**change)
    with pytest.raises(ValueError):run_historical_backtest(rows,lambda _:None)


def test_invalid_side_is_not_silently_treated_as_short():
    with pytest.raises(ValueError):
        run_historical_backtest(bars(),lambda h:BacktestSignal("TYPO",110,90))


def test_result_path_cannot_escape_requested_directory(tmp_path):
    with pytest.raises(ValueError):persist_backtest_result({"run_id":"../escape"},tmp_path)


def test_successful_identical_replay_never_rewrites_existing_evidence(tmp_path,monkeypatch):
    result=run_historical_backtest(bars(),lambda _:None);p=persist_backtest_result(result,tmp_path);before=p.read_bytes()
    original=type(p).write_text
    def forbidden(path,*args,**kwargs):
        if path==p:raise AssertionError("Existing evidence must not be rewritten")
        return original(path,*args,**kwargs)
    monkeypatch.setattr(type(p),'write_text',forbidden)
    assert persist_backtest_result(result,tmp_path)==p and p.read_bytes()==before

def test_partial_persistence_failure_is_preserved_and_retry_refuses(tmp_path,monkeypatch):
    from app.backtest import historical
    result=run_historical_backtest(bars(),lambda _:None)
    def broken(handle,text):handle.write(text[:9]);handle.flush();raise OSError('disk full')
    with monkeypatch.context() as patcher:
        patcher.setattr(historical,'write_flushed',broken)
        with pytest.raises(OSError):persist_backtest_result(result,tmp_path)
    p=tmp_path/(result['run_id']+'.json');before=p.read_bytes();assert before
    with pytest.raises(RuntimeError):persist_backtest_result(result,tmp_path)
    assert p.read_bytes()==before


def test_identical_persistence_retry_rechecks_fsync_failure(tmp_path,monkeypatch):
    from app.backtest import historical
    result=run_historical_backtest(bars(),lambda _:None);p=persist_backtest_result(result,tmp_path);before=p.read_bytes()
    def failed(_):raise OSError('fsync failed')
    monkeypatch.setattr(historical.os,'fsync',failed)
    with pytest.raises(OSError):persist_backtest_result(result,tmp_path)
    assert p.read_bytes()==before


def test_nonfinite_signal_and_generated_arithmetic_refuse():
    for stop in (float('nan'),float('inf'),True):
        with pytest.raises(ValueError):run_historical_backtest(bars(),lambda _,stop=stop:BacktestSignal('LONG',stop,104))


def test_legacy_crlf_evidence_reacknowledges_without_rewriting(tmp_path):
    result=run_historical_backtest(bars(),lambda _:None);p=persist_backtest_result(result,tmp_path)
    raw=p.read_bytes().replace(b'\n',b'\r\n');p.write_bytes(raw)
    assert persist_backtest_result(result,tmp_path)==p and p.read_bytes()==raw

@pytest.mark.parametrize('side,gap,expected',[('LONG',90,90),('SHORT',110,110)])
def test_historical_stop_gap_uses_adverse_open_not_unavailable_stop_price(side,gap,expected):
    rows=bars()
    rows[2]=replace(rows[2],open=100,high=101,low=99,close=100)
    rows[3]=replace(rows[3],open=gap,high=gap+2,low=gap-2,close=gap+1)
    signal=BacktestSignal(side,98 if side=='LONG' else 102,104 if side=='LONG' else 96)
    result=run_historical_backtest(rows,lambda h:signal if len(h)==2 else None,
                                   BacktestAssumptions(fee_bps_per_fill=0,slippage_bps_per_fill=0))
    assert result['trades'][0]['exit_price']==expected
    assert result['trades'][0]['net_pnl_usd']==-5


def test_slippage_is_embedded_once_and_fees_funding_are_separate_costs():
    rows=bars();rows[2]=replace(rows[2],funding_rate=.001);rows[3]=replace(rows[3],funding_rate=.001)
    result=run_historical_backtest(rows,lambda h:BacktestSignal('LONG',98,104) if len(h)==2 else None,
                                   BacktestAssumptions(fee_bps_per_fill=10,slippage_bps_per_fill=5))
    trade=result['trades'][0]
    assert trade['slippage_usd']>0 and trade['fees_usd']>0 and trade['funding_usd']>0
    assert trade['net_pnl_usd']==pytest.approx(trade['gross_pnl_usd']-trade['fees_usd']-trade['funding_usd'])
