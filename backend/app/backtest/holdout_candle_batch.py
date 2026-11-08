"""Acquire and normalize untouched HOLDOUT candles into HOLDOUT-only roots.

Thin research-only orchestration around the proven Binance public batch path. It fixes
holdout-2025-h2 boundaries and never writes into DEVELOPMENT roots or enables live use.
"""
from __future__ import annotations

import argparse,json
from pathlib import Path

from app.backtest.binance_public_batch import run_batch

START_UTC="2025-07-01T00:00:00Z"
END_UTC="2026-01-01T00:00:00Z"


def run(*,root:Path,manifest:Path,execute:bool=False)->dict:
    root=Path(root)
    raw_root=root/"holdout-2025-h2-candles"/"raw"
    output_root=root/"holdout-2025-h2-candles"
    batch_manifest=root/"holdout-candle-batch-2025-h2.json"
    result=run_batch(start_utc=START_UTC,end_utc=END_UTC,raw_root=raw_root,output_root=output_root,manifest=batch_manifest,execute=execute)
    payload={
        "mode":"UNTOUCHED_HOLDOUT_CANDLE_BATCH",
        "research_window":"holdout-2025-h2",
        "start_utc":START_UTC,
        "end_utc":END_UTC,
        "raw_root":str(raw_root),
        "output_root":str(output_root),
        "batch_manifest":str(batch_manifest),
        "batch_status":result["batch_status"],
        "object_count":len(result["objects"]),
        "normalized_output_count":len(result["normalized_outputs"]),
        "development_evidence_mutated":False,
        "threshold_retuning_allowed":False,
        "holdout_evaluation_allowed_before_source_audit_green":False,
        "live_capital_allowed":False,
        "automatic_real_money_execution":False,
        "status":"HOLDOUT_CANDLE_BATCH_EXECUTED" if execute else "HOLDOUT_CANDLE_BATCH_PLANNED",
    }
    manifest=Path(manifest);manifest.parent.mkdir(parents=True,exist_ok=True)
    manifest.write_text(json.dumps(payload,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    return payload


def main(argv:list[str]|None=None)->int:
    p=argparse.ArgumentParser(description="Plan/acquire untouched holdout-2025-h2 candles")
    p.add_argument("--root",type=Path,required=True)
    p.add_argument("--manifest",type=Path,required=True)
    p.add_argument("--execute",action="store_true")
    a=p.parse_args(argv)
    result=run(root=a.root,manifest=a.manifest,execute=a.execute)
    print(json.dumps(result,indent=2,sort_keys=True))
    return 0

if __name__=="__main__":raise SystemExit(main())
