"""Prepare an untouched HOLDOUT acquisition/canonicalization plan.

Research-only. This stage does not download or evaluate HOLDOUT data. It emits the
exact no-AWS commands and directory layout needed to build holdout-2025-h2 with the
same source/provenance controls used for DEVELOPMENT, while preserving the frozen
DEVELOPMENT experiment.
"""
from __future__ import annotations

import argparse,json
from pathlib import Path

SYMBOLS=("BTC","ETH","SOL")
START="2025-07-01T00:00:00Z"
END="2026-01-01T00:00:00Z"
WINDOW="holdout-2025-h2"


def build_plan(*,root:Path)->dict:
    root=Path(root)
    paths={
        "candles":str(root/f"{WINDOW}-candles"),
        "oi":str(root/f"{WINDOW}-oi"),
        "volume":str(root/f"{WINDOW}-volume"),
        "htf":str(root/f"{WINDOW}-htf"),
        "funding":str(root/f"{WINDOW}-funding"),
        "funded":str(root/f"{WINDOW}-funded"),
        "canonical":str(root/f"canonical-{WINDOW}"),
    }
    return {
        "mode":"UNTOUCHED_HOLDOUT_PREPARATION_PLAN",
        "research_window":WINDOW,
        "start_utc":START,
        "end_utc":END,
        "symbols":list(SYMBOLS),
        "paths":paths,
        "development_evidence_mutated":False,
        "threshold_retuning_allowed":False,
        "same_window_optimization_allowed":False,
        "holdout_evaluation_allowed_before_source_audit_green":False,
        "live_capital_allowed":False,
        "automatic_real_money_execution":False,
        "status":"HOLDOUT_PREPARATION_PLAN_READY",
    }


def main(argv:list[str]|None=None)->int:
    p=argparse.ArgumentParser(description="Prepare untouched holdout-2025-h2 data-build plan")
    p.add_argument("--root",type=Path,default=Path("backend/data/research/historical"))
    p.add_argument("--output",type=Path,required=True)
    a=p.parse_args(argv)
    result=build_plan(root=a.root)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps(result,indent=2,sort_keys=True))
    return 0

if __name__=="__main__":raise SystemExit(main())
