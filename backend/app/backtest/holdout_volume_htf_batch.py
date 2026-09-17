"""Derive untouched HOLDOUT rolling-volume and completed-1h HTF context.

Research-only orchestration around the proven deterministic derivation paths. Rolling
volume acquires only the exact 24h warm-up/window 5m archives it needs. HTF consumes
the already-normalized HOLDOUT 5m/1h candles. No DEVELOPMENT mutation or live path.
"""
from __future__ import annotations

import argparse,json
from pathlib import Path

from app.backtest.binance_public_rolling_volume_batch import run as run_volume_batch
from app.backtest.binance_public_htf_batch import run as run_htf_batch

START_UTC="2025-07-01T00:00:00Z"
END_UTC="2026-01-01T00:00:00Z"
WINDOW="holdout-2025-h2"


def run(*,root:Path,manifest:Path,execute:bool=False)->dict:
    root=Path(root)
    candle_root=root/f"{WINDOW}-candles"
    volume_raw_root=root/f"{WINDOW}-volume24h"/"raw"
    volume_output_root=root/f"{WINDOW}-volume24h"
    htf_output_root=root/f"{WINDOW}-htf"

    volume=run_volume_batch(
        start_utc=START_UTC,end_utc=END_UTC,raw_root=volume_raw_root,
        output_root=volume_output_root,execute=execute,
    )
    htf=None
    if execute:
        htf=run_htf_batch(
            candle_root=candle_root,output_root=htf_output_root,
            start_utc=START_UTC,end_utc=END_UTC,
        )

    payload={
        "mode":"UNTOUCHED_HOLDOUT_VOLUME_HTF_BATCH",
        "research_window":WINDOW,
        "start_utc":START_UTC,"end_utc":END_UTC,
        "candle_root":str(candle_root),
        "volume_raw_root":str(volume_raw_root),
        "volume_output_root":str(volume_output_root),
        "htf_output_root":str(htf_output_root),
        "volume_object_count":volume["object_count"],
        "volume_normalized_output_count":volume["normalized_output_count"],
        "volume_status":volume["status"],
        "pit_rolling_volume_context_complete":volume["pit_rolling_volume_context_complete"],
        "htf_normalized_output_count":0 if htf is None else htf["normalized_output_count"],
        "htf_status":None if htf is None else htf["status"],
        "completed_hourly_only":False if htf is None else htf["completed_hourly_only"],
        "development_evidence_mutated":False,
        "threshold_retuning_allowed":False,
        "same_window_optimization_allowed":False,
        "holdout_evaluation_allowed_before_source_audit_green":False,
        "current_state_backfill_used":False,
        "live_capital_allowed":False,
        "automatic_real_money_execution":False,
        "status":"HOLDOUT_VOLUME_HTF_EXECUTED" if execute else "HOLDOUT_VOLUME_HTF_PLANNED",
    }
    manifest=Path(manifest);manifest.parent.mkdir(parents=True,exist_ok=True)
    manifest.write_text(json.dumps(payload,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    return payload


def main(argv:list[str]|None=None)->int:
    p=argparse.ArgumentParser(description="Plan/execute untouched HOLDOUT rolling-volume + completed-1h HTF")
    p.add_argument("--root",type=Path,required=True);p.add_argument("--manifest",type=Path,required=True);p.add_argument("--execute",action="store_true")
    a=p.parse_args(argv);result=run(root=a.root,manifest=a.manifest,execute=a.execute)
    print(json.dumps(result,indent=2,sort_keys=True));return 0

if __name__=="__main__":raise SystemExit(main())
