"""Untouched HOLDOUT first-party funding acquisition + exact PIT merge.

Research-only wrapper around the proven Hyperliquid funding batch and exact-event
5m funding merge. All artifacts remain in HOLDOUT-only roots. No interpolation,
forward-fill, current-state backfill, DEVELOPMENT mutation, or live unlock.
"""
from __future__ import annotations

import argparse,json
from pathlib import Path

from app.backtest.hyperliquid_funding_batch import run_batch as run_funding_batch
from app.backtest.funding_pit_merge_batch import run_batch as run_merge_batch

START_UTC="2025-07-01T00:00:00Z"
END_UTC="2026-01-01T00:00:00Z"
WINDOW="holdout-2025-h2"


def run(*,root:Path,manifest:Path,execute:bool=False)->dict:
    root=Path(root)
    bars_root=root/f"{WINDOW}-candles"
    funding_root=root/f"{WINDOW}-funding"
    funded_root=root/f"{WINDOW}-funded"
    funding_manifest=root/"holdout-funding-batch-2025-h2.json"
    merge_manifest=root/"holdout-funding-merge-batch-2025-h2.json"

    funding=None;merged=None
    if execute:
        funding=run_funding_batch(start_utc=START_UTC,end_utc=END_UTC,output_root=funding_root,manifest=funding_manifest)
        merged=run_merge_batch(bars_root=bars_root,funding_root=funding_root,output_root=funded_root,start_utc=START_UTC,end_utc=END_UTC,manifest=merge_manifest)

    payload={
        "mode":"UNTOUCHED_HOLDOUT_FUNDING_AND_PIT_MERGE",
        "research_window":WINDOW,
        "start_utc":START_UTC,"end_utc":END_UTC,
        "bars_root":str(bars_root),"funding_root":str(funding_root),"funded_root":str(funded_root),
        "funding_manifest":str(funding_manifest),"merge_manifest":str(merge_manifest),
        "funding_normalized_output_count":0 if funding is None else len(funding["normalized_outputs"]),
        "funding_status":None if funding is None else funding["status"],
        "funded_output_count":0 if merged is None else len(merged["normalized_outputs"]),
        "merge_status":None if merged is None else merged["status"],
        "exact_event_timestamps":False if funding is None else funding["exact_event_timestamps"],
        "interpolation_used":False,
        "forward_fill_used":False,
        "current_state_backfill_used":False,
        "development_evidence_mutated":False,
        "threshold_retuning_allowed":False,
        "same_window_optimization_allowed":False,
        "holdout_evaluation_allowed_before_source_audit_green":False,
        "live_capital_allowed":False,
        "automatic_real_money_execution":False,
        "status":"HOLDOUT_FUNDING_MERGE_EXECUTED" if execute else "HOLDOUT_FUNDING_MERGE_PLANNED",
    }
    manifest=Path(manifest);manifest.parent.mkdir(parents=True,exist_ok=True)
    manifest.write_text(json.dumps(payload,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    return payload


def main(argv:list[str]|None=None)->int:
    p=argparse.ArgumentParser(description="Plan/execute untouched HOLDOUT funding + exact PIT merge")
    p.add_argument("--root",type=Path,required=True);p.add_argument("--manifest",type=Path,required=True);p.add_argument("--execute",action="store_true")
    a=p.parse_args(argv);result=run(root=a.root,manifest=a.manifest,execute=a.execute)
    print(json.dumps(result,indent=2,sort_keys=True));return 0

if __name__=="__main__":raise SystemExit(main())
