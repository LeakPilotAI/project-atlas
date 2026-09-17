"""Build plan/orchestrator for untouched holdout-2025-h2 historical data.

Research-only. This module defines the exact HOLDOUT acquisition/canonicalization sequence
using the existing proven Atlas batch commands, but writes only to HOLDOUT-specific roots.
It does not evaluate the strategy, retune thresholds, mutate DEVELOPMENT evidence, or enable
live execution.
"""
from __future__ import annotations

import argparse,json
from pathlib import Path

START_UTC="2025-07-01T00:00:00Z"
END_UTC="2026-01-01T00:00:00Z"
WINDOW="holdout-2025-h2"


def build_plan(root:Path)->dict:
    root=Path(root)
    paths={
        "candles":root/f"{WINDOW}-candles",
        "oi":root/f"{WINDOW}-oi",
        "volume":root/f"{WINDOW}-volume",
        "htf":root/f"{WINDOW}-htf",
        "funding":root/f"{WINDOW}-funding",
        "funded":root/f"{WINDOW}-funded",
        "canonical":root/f"canonical-{WINDOW}",
    }
    commands=[
        {
            "stage":"candles",
            "module":"app.backtest.binance_public_batch",
            "status":"REQUIRED",
            "notes":"Acquire BTC/ETH/SOL 5m + 1h public Binance USD-M candles for the HOLDOUT window with checksum provenance.",
        },
        {
            "stage":"oi",
            "module":"app.backtest.hyperliquid_metrics_batch",
            "status":"REQUIRED",
            "notes":"Acquire and normalize historical PIT open interest for HOLDOUT; preserve sparse source missingness with no interpolation.",
        },
        {
            "stage":"rolling_volume",
            "module":"app.backtest.binance_public_rolling_volume_batch",
            "status":"REQUIRED",
            "notes":"Derive exact trailing 24h quote volume from raw 5m klines with required warm-up.",
        },
        {
            "stage":"htf",
            "module":"app.backtest.htf_context_batch",
            "status":"REQUIRED",
            "notes":"Derive completed-1h HTF context only; no future/incomplete hourly candle use.",
        },
        {
            "stage":"funding",
            "module":"app.backtest.hyperliquid_funding_batch",
            "status":"REQUIRED",
            "notes":"Acquire paginated first-party Hyperliquid funding history with exact event timestamps.",
        },
        {
            "stage":"funding_merge",
            "module":"app.backtest.funding_pit_merge_batch",
            "status":"REQUIRED",
            "notes":"Merge exact funding events into containing half-open 5m intervals; no fill/interpolation.",
        },
        {
            "stage":"canonical",
            "module":"app.backtest.canonical_batch",
            "status":"REQUIRED",
            "notes":"Assemble canonical HOLDOUT datasets; exclude incomplete PIT context rows instead of fabricating values.",
        },
        {
            "stage":"source_audit",
            "module":"app.backtest.source_audit",
            "status":"GATE",
            "notes":"HOLDOUT evaluation forbidden until ready_for_locked_baseline_batch=true for canonical HOLDOUT root.",
        },
    ]
    return {
        "mode":"UNTOUCHED_HOLDOUT_DATA_BUILD_PLAN",
        "research_window":WINDOW,
        "start_utc":START_UTC,
        "end_utc":END_UTC,
        "paths":{k:str(v) for k,v in paths.items()},
        "stages":commands,
        "development_evidence_mutated":False,
        "threshold_retuning_allowed":False,
        "same_window_optimization_allowed":False,
        "holdout_evaluation_allowed_before_source_audit_green":False,
        "live_capital_allowed":False,
        "automatic_real_money_execution":False,
        "status":"HOLDOUT_DATA_BUILD_PLAN_READY",
    }


def run(*,root:Path,output:Path)->dict:
    payload=build_plan(root)
    output=Path(output);output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(payload,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    return payload


def main(argv:list[str]|None=None)->int:
    p=argparse.ArgumentParser(description="Create untouched HOLDOUT historical-data build plan")
    p.add_argument("--root",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    a=p.parse_args(argv)
    print(json.dumps(run(root=a.root,output=a.output),indent=2,sort_keys=True))
    return 0

if __name__=="__main__":raise SystemExit(main())
