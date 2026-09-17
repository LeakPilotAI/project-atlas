"""Untouched HOLDOUT historical PIT open-interest acquisition stage.

Research-only wrapper around the proven Binance public metrics batch. All raw and
normalized outputs stay inside holdout-2025-h2 roots. DEVELOPMENT evidence is
never mutated and strategy evaluation remains gated by independent source_audit.
"""
from __future__ import annotations

import argparse, json
from pathlib import Path

from app.backtest.binance_public_metrics_batch import run as run_oi_batch

START_UTC="2025-07-01T00:00:00Z"
END_UTC="2026-01-01T00:00:00Z"
WINDOW="holdout-2025-h2"


def run(*,root:Path,manifest:Path,execute:bool=False)->dict:
    root=Path(root)
    raw_root=root/f"{WINDOW}-oi"/"raw"
    output_root=root/f"{WINDOW}-oi"
    batch=run_oi_batch(start_utc=START_UTC,end_utc=END_UTC,raw_root=raw_root,output_root=output_root,execute=execute)
    result={
        "mode":"UNTOUCHED_HOLDOUT_OI_BATCH",
        "research_window":WINDOW,
        "start_utc":START_UTC,
        "end_utc":END_UTC,
        "raw_root":str(raw_root),
        "output_root":str(output_root),
        "object_count":batch["object_count"],
        "normalized_output_count":batch["normalized_output_count"],
        "batch_status":batch["status"],
        "pit_oi_context_complete":batch["pit_oi_context_complete"],
        "development_evidence_mutated":False,
        "threshold_retuning_allowed":False,
        "same_window_optimization_allowed":False,
        "holdout_evaluation_allowed_before_source_audit_green":False,
        "live_capital_allowed":False,
        "automatic_real_money_execution":False,
        "status":"HOLDOUT_OI_BATCH_EXECUTED" if execute else "HOLDOUT_OI_BATCH_PLANNED",
    }
    manifest=Path(manifest);manifest.parent.mkdir(parents=True,exist_ok=True)
    manifest.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    return result


def main(argv:list[str]|None=None)->int:
    p=argparse.ArgumentParser(description="Plan/execute untouched HOLDOUT PIT OI acquisition")
    p.add_argument("--root",type=Path,required=True)
    p.add_argument("--manifest",type=Path,required=True)
    p.add_argument("--execute",action="store_true")
    a=p.parse_args(argv)
    result=run(root=a.root,manifest=a.manifest,execute=a.execute)
    print(json.dumps(result,indent=2,sort_keys=True))
    return 0

if __name__=="__main__":raise SystemExit(main())
