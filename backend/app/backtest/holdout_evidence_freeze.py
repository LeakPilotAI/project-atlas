"""Freeze completed untouched HOLDOUT evidence without retuning.

Research-only. Copies the completed holdout summary into a compact immutable decision
artifact. It does not modify thresholds, production state, PAPER/SHADOW, or live capital.
"""
from __future__ import annotations
import argparse,json
from hashlib import sha256
from pathlib import Path


def _load(path:Path)->dict:
    payload=json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload,dict):raise ValueError("holdout summary must be a JSON object")
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
    expectancy=float(aggregate.get("expectancy_r",0.0));total=float(aggregate.get("total_r",0.0));trades=int(aggregate.get("trade_count",0))
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
    raw=Path(summary_path).read_bytes();payload=build(_load(summary_path));payload["holdout_summary_sha256"]=sha256(raw).hexdigest()
    output=Path(output);output.parent.mkdir(parents=True,exist_ok=True)
    text=json.dumps(payload,indent=2,sort_keys=True)+"\n"
    if output.exists() and output.read_text(encoding="utf-8")!=text:raise RuntimeError("existing holdout evidence freeze differs")
    output.write_text(text,encoding="utf-8");return payload


def main(argv=None)->int:
    p=argparse.ArgumentParser();p.add_argument("--summary",type=Path,required=True);p.add_argument("--output",type=Path,required=True);a=p.parse_args(argv)
    print(json.dumps(run(summary_path=a.summary,output=a.output),indent=2,sort_keys=True));return 0
if __name__=="__main__":raise SystemExit(main())
