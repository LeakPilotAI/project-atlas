"""Untouched HOLDOUT evaluation for the frozen Atlas DEVELOPMENT configuration.

Research-only. This stage requires a completed DEVELOPMENT decision freeze and runs the
exact frozen parameters on a separate canonical holdout bundle. It does not retune,
modify production strategy state, or enable live capital.
"""
from __future__ import annotations

import argparse,json
from pathlib import Path

from app.backtest.locked_development_baseline_run import LockedThresholds,_signal_fn
from app.backtest.historical import BacktestAssumptions,run_historical_backtest,persist_backtest_result
from app.backtest.io import load_historical_contexts
from app.backtest.source_audit import audit_representative_bundle

SYMBOLS=("BTC","ETH","SOL")


def _load_json(path:Path)->dict:
    payload=json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload,dict):
        raise ValueError("freeze payload must be a JSON object")
    return payload


def _thresholds_from_freeze(payload:dict)->LockedThresholds:
    if payload.get("status")!="DEVELOPMENT_DECISIONS_FROZEN":
        raise RuntimeError("development decisions are not frozen")
    if payload.get("parameters_frozen") is not True:
        raise RuntimeError("development parameters are not frozen")
    if payload.get("same_window_optimization_allowed") is not False:
        raise RuntimeError("same-window optimization must be disabled")
    values=payload.get("thresholds") or {}
    return LockedThresholds(**values)


def run(*,freeze_path:Path,canonical_root:Path,output_root:Path,summary_path:Path,timeframe:str="5m",research_window:str="holdout-2025-h2")->dict:
    freeze=_load_json(Path(freeze_path))
    thresholds=_thresholds_from_freeze(freeze)
    audit=audit_representative_bundle(canonical_root,SYMBOLS,timeframe)
    if not audit["ready_for_locked_baseline_batch"]:
        raise RuntimeError("holdout canonical source audit is not GREEN")
    runs=[]
    for symbol in SYMBOLS:
        path=Path(canonical_root)/f"{symbol}-{timeframe}.csv"
        contexts=load_historical_contexts(path)
        bars=[x.bar for x in contexts]
        result=run_historical_backtest(bars,_signal_fn(contexts,thresholds),BacktestAssumptions())
        persisted=persist_backtest_result(result,Path(output_root)/symbol)
        runs.append({"symbol":symbol,"dataset":str(path),"result_path":str(persisted),"run_id":result["run_id"],"metrics":result["metrics"]})
    total_trades=sum(x["metrics"]["trade_count"] for x in runs)
    total_r=sum(x["metrics"]["total_r"] for x in runs)
    payload={
        "mode":"UNTOUCHED_HOLDOUT_EVALUATION",
        "research_window":research_window,
        "development_freeze":str(freeze_path),
        "development_result":freeze.get("development_result"),
        "source_audit_id":audit["audit_id"],
        "source_audit_green":True,
        "thresholds":freeze.get("thresholds"),
        "parameters_frozen":True,
        "threshold_retuning_allowed":False,
        "same_window_optimization_allowed":False,
        "holdout_data_touched":True,
        "production_strategy_modified":False,
        "live_capital_allowed":False,
        "automatic_real_money_execution":False,
        "runs":runs,
        "aggregate":{"trade_count":total_trades,"total_r":total_r,"expectancy_r":total_r/total_trades if total_trades else 0.0},
        "status":"UNTOUCHED_HOLDOUT_EVALUATION_COMPLETE",
    }
    summary_path=Path(summary_path);summary_path.parent.mkdir(parents=True,exist_ok=True)
    summary_path.write_text(json.dumps(payload,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    return payload


def main(argv:list[str]|None=None)->int:
    p=argparse.ArgumentParser(description="Run untouched HOLDOUT evaluation using frozen DEVELOPMENT parameters")
    p.add_argument("--freeze",type=Path,required=True)
    p.add_argument("--canonical-root",type=Path,required=True)
    p.add_argument("--output-root",type=Path,required=True)
    p.add_argument("--summary",type=Path,required=True)
    p.add_argument("--timeframe",default="5m")
    p.add_argument("--research-window",default="holdout-2025-h2")
    a=p.parse_args(argv)
    result=run(freeze_path=a.freeze,canonical_root=a.canonical_root,output_root=a.output_root,summary_path=a.summary,timeframe=a.timeframe,research_window=a.research_window)
    print(json.dumps(result,indent=2,sort_keys=True))
    return 0

if __name__=="__main__":raise SystemExit(main())
