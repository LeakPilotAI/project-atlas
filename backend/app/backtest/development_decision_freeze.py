"""Freeze locked DEVELOPMENT baseline decisions before any HOLDOUT access.

Research-only. This stage records the exact locked DEVELOPMENT result and freezes the
configuration without retuning. A negative DEVELOPMENT baseline is preserved as failed
evidence rather than optimized on the same window.
"""
from __future__ import annotations

import argparse,json
from pathlib import Path


def run(*,baseline_summary:Path,output:Path)->dict:
    baseline_summary=Path(baseline_summary)
    payload=json.loads(baseline_summary.read_text(encoding="utf-8"))
    if payload.get("status")!="LOCKED_DEVELOPMENT_BASELINE_COMPLETE":
        raise RuntimeError("locked DEVELOPMENT baseline is not complete")
    if payload.get("holdout_data_touched") is not False:
        raise RuntimeError("DEVELOPMENT baseline touched holdout data")
    if payload.get("threshold_retuning_allowed") is not False:
        raise RuntimeError("threshold retuning must remain disabled")
    aggregate=payload.get("aggregate") or {}
    expectancy=float(aggregate.get("expectancy_r") or 0.0)
    total_r=float(aggregate.get("total_r") or 0.0)
    trades=int(aggregate.get("trade_count") or 0)
    development_edge_positive=bool(trades>0 and expectancy>0.0 and total_r>0.0)
    result={
        "mode":"DEVELOPMENT_DECISION_FREEZE",
        "research_window":"dev-2024-h2",
        "baseline_summary":str(baseline_summary),
        "source_audit_id":payload.get("source_audit_id"),
        "thresholds":payload.get("thresholds"),
        "aggregate":aggregate,
        "runs":payload.get("runs"),
        "development_edge_positive":development_edge_positive,
        "development_result":"POSITIVE" if development_edge_positive else "FAILED_NEGATIVE",
        "threshold_retuning_allowed":False,
        "same_window_optimization_allowed":False,
        "holdout_data_touched":False,
        "parameters_frozen":True,
        "live_capital_allowed":False,
        "automatic_real_money_execution":False,
        "status":"DEVELOPMENT_DECISIONS_FROZEN",
    }
    output=Path(output);output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    return result


def main(argv:list[str]|None=None)->int:
    p=argparse.ArgumentParser(description="Freeze DEVELOPMENT result and parameters before HOLDOUT")
    p.add_argument("--baseline-summary",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    a=p.parse_args(argv)
    result=run(baseline_summary=a.baseline_summary,output=a.output)
    print(json.dumps(result,indent=2,sort_keys=True))
    return 0

if __name__=="__main__":raise SystemExit(main())
