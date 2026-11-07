"""Run the locked DEVELOPMENT baseline on canonical PIT datasets.

Research-only. This stage consumes canonical BTC/ETH/SOL 5m datasets that already
passed source_audit. It does not retune thresholds, touch holdout windows, or unlock
live execution.
"""
from __future__ import annotations

import argparse,json
from pathlib import Path

from app.backtest.io import load_historical_contexts
from app.backtest.source_audit import audit_representative_bundle

SYMBOLS=("BTC","ETH","SOL")


def run(*,canonical_root:Path,output:Path,timeframe:str="5m")->dict:
    audit=audit_representative_bundle(canonical_root,SYMBOLS,timeframe)
    if not audit["ready_for_locked_baseline_batch"]:
        raise RuntimeError("canonical source audit is not GREEN")
    datasets=[]
    total_rows=0
    for symbol in SYMBOLS:
        path=Path(canonical_root)/f"{symbol}-{timeframe}.csv"
        rows=load_historical_contexts(path)
        datasets.append({
            "symbol":symbol,
            "path":str(path),
            "row_count":len(rows),
            "first_timestamp":rows[0].bar.timestamp,
            "last_timestamp":rows[-1].bar.timestamp,
        })
        total_rows+=len(rows)
    payload={
        "mode":"LOCKED_DEVELOPMENT_BASELINE_INPUT_FREEZE",
        "research_window":"dev-2024-h2",
        "timeframe":timeframe,
        "datasets":datasets,
        "total_rows":total_rows,
        "source_audit_id":audit["audit_id"],
        "source_audit_green":True,
        "threshold_retuning_allowed":False,
        "holdout_data_touched":False,
        "live_capital_allowed":False,
        "automatic_real_money_execution":False,
        "status":"LOCKED_DEVELOPMENT_BASELINE_INPUTS_FROZEN",
    }
    output=Path(output);output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(payload,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    return payload


def main(argv:list[str]|None=None)->int:
    p=argparse.ArgumentParser(description="Freeze canonical inputs for locked DEVELOPMENT baseline")
    p.add_argument("--canonical-root",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    p.add_argument("--timeframe",default="5m")
    a=p.parse_args(argv)
    result=run(canonical_root=a.canonical_root,output=a.output,timeframe=a.timeframe)
    print(json.dumps(result,indent=2,sort_keys=True))
    return 0

if __name__=="__main__":raise SystemExit(main())
