"""Assemble untouched HOLDOUT canonical PIT datasets and run independent source audit.

Research-only. Reuses canonical_batch + source_audit against HOLDOUT-only roots. The
audit is the mandatory gate before holdout_evaluation can run. No retuning or live path.
"""
from __future__ import annotations

import argparse,json
from pathlib import Path

from app.backtest.canonical_batch import run as run_canonical_batch
from app.backtest.source_audit import audit_representative_bundle

START_UTC="2025-07-01T00:00:00Z"
END_UTC="2026-01-01T00:00:00Z"
WINDOW="holdout-2025-h2"


def run(*,root:Path,manifest:Path,execute:bool=False)->dict:
    root=Path(root)
    funded_root=root/f"{WINDOW}-funded"
    oi_root=root/f"{WINDOW}-oi"
    volume_root=root/f"{WINDOW}-volume24h"
    htf_root=root/f"{WINDOW}-htf"
    canonical_root=root/f"canonical-{WINDOW}"
    canonical_manifest=root/f"canonical-batch-{WINDOW}.json"

    canonical=None;audit=None
    if execute:
        canonical=run_canonical_batch(
            funded_root=funded_root,oi_root=oi_root,volume_root=volume_root,htf_root=htf_root,
            output_root=canonical_root,manifest_path=canonical_manifest,start=START_UTC,end=END_UTC,
        )
        audit=audit_representative_bundle(canonical_root,("BTC","ETH","SOL"),"5m")

    payload={
        "mode":"UNTOUCHED_HOLDOUT_CANONICAL_AND_SOURCE_AUDIT",
        "research_window":WINDOW,
        "start_utc":START_UTC,"end_utc":END_UTC,
        "funded_root":str(funded_root),"oi_root":str(oi_root),
        "volume_root":str(volume_root),"htf_root":str(htf_root),
        "canonical_root":str(canonical_root),"canonical_manifest":str(canonical_manifest),
        "canonical_status":None if canonical is None else canonical["status"],
        "canonical_output_count":0 if canonical is None else canonical["normalized_outputs"],
        "source_audit":audit,
        "ready_for_locked_baseline_batch":False if audit is None else audit["ready_for_locked_baseline_batch"],
        "development_evidence_mutated":False,
        "threshold_retuning_allowed":False,
        "same_window_optimization_allowed":False,
        "holdout_evaluation_allowed":bool(audit and audit["ready_for_locked_baseline_batch"]),
        "live_capital_allowed":False,"automatic_real_money_execution":False,
        "status":"HOLDOUT_CANONICAL_AUDIT_EXECUTED" if execute else "HOLDOUT_CANONICAL_AUDIT_PLANNED",
    }
    manifest=Path(manifest);manifest.parent.mkdir(parents=True,exist_ok=True)
    manifest.write_text(json.dumps(payload,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    return payload


def main(argv:list[str]|None=None)->int:
    p=argparse.ArgumentParser(description="Plan/execute untouched HOLDOUT canonical assembly + independent source audit")
    p.add_argument("--root",type=Path,required=True);p.add_argument("--manifest",type=Path,required=True);p.add_argument("--execute",action="store_true")
    a=p.parse_args(argv);result=run(root=a.root,manifest=a.manifest,execute=a.execute)
    print(json.dumps(result,indent=2,sort_keys=True))
    if a.execute and not result["ready_for_locked_baseline_batch"]:return 2
    return 0

if __name__=="__main__":raise SystemExit(main())
