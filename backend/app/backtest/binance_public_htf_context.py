"""Derive production-equivalent completed-1h HTF trend for historical 5m decisions.

Research-only. Uses checksum-verified normalized 1h candles and exposes each hourly
close only after that candle has completed. No current-state backfill and no live unlock.
"""
from __future__ import annotations

import argparse,csv,json
from hashlib import sha256
from pathlib import Path

from app.backtest.htf_context import HtfClose,derive_1h_trend_by_timestamp

FIELDS=["timestamp","htf_trend"]


def _sha256(path:Path)->str:
    h=sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda:fh.read(1024*1024),b""):h.update(chunk)
    return h.hexdigest()


def derive(*,decision_candles:Path,hourly_candles:Path,output:Path,report:Path|None=None)->dict:
    decisions=[]
    with Path(decision_candles).open("r",encoding="utf-8-sig",newline="") as fh:
        for row in csv.DictReader(fh):
            ts=row.get("timestamp")
            if not ts:raise RuntimeError("decision candle missing timestamp")
            decisions.append(ts)
    if not decisions:raise RuntimeError("decision candle file is empty")

    hourly=[]
    with Path(hourly_candles).open("r",encoding="utf-8-sig",newline="") as fh:
        for row in csv.DictReader(fh):
            ts=row.get("timestamp");close=row.get("close")
            if not ts or close in (None,""):raise RuntimeError("hourly candle missing timestamp/close")
            hourly.append(HtfClose(open_timestamp=ts,close=float(close)))
    if not hourly:raise RuntimeError("hourly candle file is empty")

    trends=derive_1h_trend_by_timestamp(decisions,hourly)
    output=Path(output);output.parent.mkdir(parents=True,exist_ok=True)
    with output.open("w",encoding="utf-8",newline="") as fh:
        w=csv.DictWriter(fh,fieldnames=FIELDS);w.writeheader()
        for ts in decisions:w.writerow({"timestamp":ts,"htf_trend":trends[ts]})
    payload={
        "mode":"RESEARCH_ONLY_COMPLETED_1H_HTF_CONTEXT",
        "decision_source":str(decision_candles),"decision_source_sha256":_sha256(Path(decision_candles)),
        "hourly_source":str(hourly_candles),"hourly_source_sha256":_sha256(Path(hourly_candles)),
        "output":str(output),"output_sha256":_sha256(output),"row_count":len(decisions),
        "first_timestamp":decisions[0],"last_timestamp":decisions[-1],
        "rule":"latest completed 1h close vs SMA20; UP > +0.2%, DOWN < -0.2%, else FLAT; <20 completed closes UNKNOWN",
        "completed_hourly_only":True,"current_state_backfill_used":False,
        "live_capital_allowed":False,"automatic_real_money_execution":False,
    }
    if report is not None:
        report=Path(report);report.parent.mkdir(parents=True,exist_ok=True);report.write_text(json.dumps(payload,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    return payload


def main(argv:list[str]|None=None)->int:
    p=argparse.ArgumentParser(description="Derive completed-1h HTF context for historical 5m decisions")
    p.add_argument("--decision-candles",type=Path,required=True);p.add_argument("--hourly-candles",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True);p.add_argument("--report",type=Path)
    a=p.parse_args(argv);result=derive(decision_candles=a.decision_candles,hourly_candles=a.hourly_candles,output=a.output,report=a.report)
    print(json.dumps(result,indent=2,sort_keys=True));return 0

if __name__=="__main__":raise SystemExit(main())
