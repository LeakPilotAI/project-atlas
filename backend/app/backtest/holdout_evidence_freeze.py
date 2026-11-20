"""Freeze completed untouched HOLDOUT evidence without retuning.

Research-only. Copies the completed holdout summary into a compact immutable decision
artifact. It does not modify thresholds, production state, PAPER/SHADOW, or live capital.
"""
from __future__ import annotations

import argparse
import json
import math
import os
from hashlib import sha256
from pathlib import Path

from app.core.durable_io import sync_parent, write_flushed


def _load(path:Path)->dict:
    payload=json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload,dict):raise ValueError("holdout summary must be a JSON object")  # noqa: TRY004 - preserve evidence-refusal compatibility
    return payload


def build(summary:dict)->dict:
    if summary.get("status")!="UNTOUCHED_HOLDOUT_EVALUATION_COMPLETE":raise RuntimeError("holdout evaluation is not complete")
    if summary.get("source_audit_green") is not True:raise RuntimeError("holdout source audit is not GREEN")
    if summary.get("parameters_frozen") is not True or summary.get("threshold_retuning_allowed") is not False:raise RuntimeError("holdout parameters were not frozen")
    if summary.get("production_strategy_modified") is not False or summary.get("live_capital_allowed") is not False:raise RuntimeError("holdout execution safety boundary violated")
    runs=summary.get("runs") or []
    symbols=[x.get("symbol") for x in runs]
    if symbols!=["BTC","ETH","SOL"]:raise RuntimeError("expected exact BTC/ETH/SOL holdout runs")
    aggregate=summary.get("aggregate") or {}
    trades=aggregate.get("trade_count")
    expectancy=aggregate.get("expectancy_r");total=aggregate.get("total_r")
    if type(trades) is not int or trades<0:raise ValueError("holdout trade count must be a nonnegative integer")
    if any(type(value) not in (int,float) or not math.isfinite(value) for value in (expectancy,total)):
        raise ValueError("holdout measured metrics must be finite numbers")
    if trades==0 and (expectancy!=0 or total!=0):raise ValueError("empty holdout cannot have nonzero measured returns")
    if summary.get("same_window_optimization_allowed") is True:raise RuntimeError("holdout optimization is not frozen")
    expectancy=float(expectancy);total=float(total)
    result="POSITIVE" if trades>0 and expectancy>0 and total>0 else "FAILED_NEGATIVE"
    return {
        "mode":"HOLDOUT_EVIDENCE_FREEZE",
        "research_window":summary.get("research_window"),
        "development_result":summary.get("development_result"),
        "holdout_result":result,
        "aggregate":{"trade_count":trades,"total_r":total,"expectancy_r":expectancy},
        "runs":[{"symbol":x["symbol"],"run_id":x["run_id"],"metrics":x["metrics"]} for x in runs],
        "source_audit_id":summary.get("source_audit_id"),
        "source_audit_green":True,
        "thresholds":summary.get("thresholds"),
        "parameters_frozen":True,
        "threshold_retuning_allowed":False,
        "same_window_optimization_allowed":False,
        "production_strategy_modified":False,
        "live_capital_allowed":False,
        "automatic_real_money_execution":False,
        "stable_positive_edge_established":False,
        "next_cycle_must_be_isolated":True,
        "status":"HOLDOUT_EVIDENCE_FROZEN",
    }


def run(*,summary_path:Path,output:Path)->dict:
    # Parse exactly the bytes whose digest is recorded, never reread a moving input.
    raw=Path(summary_path).read_bytes()
    summary=json.loads(raw)
    if not isinstance(summary,dict):raise ValueError("holdout summary must be a JSON object")  # noqa: TRY004 - preserve evidence-refusal compatibility
    payload=build(summary);payload["holdout_summary_sha256"]=sha256(raw).hexdigest()
    output=Path(output);output.parent.mkdir(parents=True,exist_ok=True)
    if output.is_symlink():raise RuntimeError("linked holdout output refused")
    text=json.dumps(payload,indent=2,sort_keys=True,allow_nan=False)+"\n"
    try:
        # Exclusive publication: concurrent/new runs never truncate existing evidence.
        with output.open("x",encoding="utf-8",newline="\n") as stream:
            write_flushed(stream,text)
    except FileExistsError:
        # Re-establish the supported durability boundary without rewriting bytes.
        with output.open("r+b") as stream:
            existing=stream.read()
            legacy=text.replace("\n","\r\n").encode("utf-8")
            if existing not in (text.encode("utf-8"),legacy):
                raise RuntimeError("existing holdout evidence freeze differs or is incomplete")
            os.fsync(stream.fileno())
    sync_parent(output)
    return payload


def main(argv=None)->int:
    p=argparse.ArgumentParser();p.add_argument("--summary",type=Path,required=True);p.add_argument("--output",type=Path,required=True);a=p.parse_args(argv)
    print(json.dumps(run(summary_path=a.summary,output=a.output),indent=2,sort_keys=True));return 0
if __name__=="__main__":raise SystemExit(main())
