"""Canonical research-only Atlas historical backtest CLI."""
from __future__ import annotations
import argparse
from pathlib import Path
from app.backtest.historical import BacktestAssumptions,persist_backtest_result,run_historical_backtest
from app.backtest.io import load_historical_contexts,bars_only
from app.backtest.perp_micro_baseline import PerpMicroBaselineConfig,baseline_metadata,locked_perp_micro_signal

def _parser()->argparse.ArgumentParser:
    p=argparse.ArgumentParser(description="Run deterministic research-only Atlas historical backtest");p.add_argument("--dataset",required=True,type=Path);p.add_argument("--output-dir",type=Path,default=Path("data/research/backtests"));p.add_argument("--strategy",choices=["locked-perp-micro-baseline"],default="locked-perp-micro-baseline");p.add_argument("--fee-bps",type=float,default=3.5);p.add_argument("--slippage-bps",type=float,default=1.0);p.add_argument("--initial-equity",type=float,default=10_000.0);return p

def run_cli(argv:list[str]|None=None)->int:
    args=_parser().parse_args(argv);contexts=load_historical_contexts(args.dataset);cfg=PerpMicroBaselineConfig.from_settings();bars=bars_only(contexts);by_timestamp={row.bar.timestamp:row for row in contexts}
    def signal(history):
        current=by_timestamp[history[-1].timestamp];eligible=current.open_interest_usd>=cfg.min_open_interest_usd and current.volume_24h_usd>=cfg.min_volume_24h_usd
        kwargs={"history":history,"config":cfg,"oi_volume_eligible":eligible}
        if current.htf_trend is not None:kwargs["htf_trend"]=current.htf_trend
        else:kwargs["htf_regime_aligned"]=current.htf_regime_aligned
        return locked_perp_micro_signal(**kwargs)
    assumptions=BacktestAssumptions(risk_usd=cfg.risk_usd,fee_bps_per_fill=args.fee_bps,slippage_bps_per_fill=args.slippage_bps,initial_equity_usd=args.initial_equity)
    result=run_historical_backtest(bars,signal,assumptions);result["strategy"]=baseline_metadata(cfg);result["dataset_path"]=str(args.dataset);path=persist_backtest_result(result,args.output_dir);m=result["metrics"]
    print(f"run_id={result['run_id']}");print(f"result={path}");print(f"trades={m['trade_count']} win_rate={m['win_rate']:.4f} expectancy_r={m['expectancy_r']:.4f} total_r={m['total_r']:.4f} profit_factor={m['profit_factor']}");print(f"max_drawdown_usd={m['max_drawdown_usd']:.4f} fees_usd={m['fees_usd']:.4f} slippage_usd={m['slippage_usd']:.4f} funding_usd={m['funding_usd']:.4f}");print("mode=RESEARCH_ONLY_HISTORICAL_BACKTEST live_capital_allowed=False");return 0

if __name__=="__main__":raise SystemExit(run_cli())
