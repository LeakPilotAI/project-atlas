from pathlib import Path
from app.backtest.cli import run_cli
from app.backtest.io import load_historical_contexts,bars_only
from app.backtest.historical import BacktestAssumptions,run_historical_backtest
from app.backtest.perp_micro_baseline import PerpMicroBaselineConfig,locked_perp_micro_signal

FIXTURE=Path('tests/fixtures/backtest_smoke.csv')


def _run_direct():
    contexts=load_historical_contexts(FIXTURE)
    bars=bars_only(contexts)
    by_ts={x.bar.timestamp:x for x in contexts}
    cfg=PerpMicroBaselineConfig.from_settings()
    def signal(history):
        row=by_ts[history[-1].timestamp]
        eligible=row.open_interest_usd>=cfg.min_open_interest_usd and row.volume_24h_usd>=cfg.min_volume_24h_usd
        return locked_perp_micro_signal(history,config=cfg,oi_volume_eligible=eligible,htf_regime_aligned=row.htf_regime_aligned)
    return run_historical_backtest(bars,signal,BacktestAssumptions(risk_usd=cfg.risk_usd,fee_bps_per_fill=3.5,slippage_bps_per_fill=1.0,initial_equity_usd=10_000.0))


def test_smoke_backtest_is_repeatable_and_reconciled():
    a=_run_direct();b=_run_direct()
    assert a==b
    assert a['run_id']==b['run_id']
    assert a['mode']=='RESEARCH_ONLY_HISTORICAL_BACKTEST'
    assert a['live_capital_allowed'] is False
    assert a['automatic_real_money_execution'] is False
    assert a['metrics']['trade_count']>=1
    assert len(a['trades'])==a['metrics']['trade_count']
    assert abs(sum(t['net_r'] for t in a['trades'])-a['metrics']['total_r'])<1e-12
    assert abs(sum(t['fees_usd'] for t in a['trades'])-a['metrics']['fees_usd'])<1e-12
    assert abs(sum(t['slippage_usd'] for t in a['trades'])-a['metrics']['slippage_usd'])<1e-12
    assert abs(sum(t['funding_usd'] for t in a['trades'])-a['metrics']['funding_usd'])<1e-12


def test_cli_smoke_persists_same_result_path_twice(tmp_path):
    args=['--dataset',str(FIXTURE),'--output-dir',str(tmp_path)]
    assert run_cli(args)==0
    first=list(tmp_path.glob('*.json'))
    assert len(first)==1
    text=first[0].read_text(encoding='utf-8')
    assert 'RESEARCH_ONLY_HISTORICAL_BACKTEST' in text
    assert run_cli(args)==0
    second=list(tmp_path.glob('*.json'))
    assert second==first
