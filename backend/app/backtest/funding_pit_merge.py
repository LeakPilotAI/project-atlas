"""Merge exact first-party funding events into historical 5m bars without synthesis.

Research-only. Funding is attached only when an event timestamp falls within the
bar's half-open interval [bar_open, bar_open+5m). No forward fill or interpolation.
Multiple events inside one bar are summed exactly for that bar.
"""
from __future__ import annotations

import argparse,csv,json
from datetime import datetime,timezone
from hashlib import sha256
from pathlib import Path

STEP_MS=300_000


def _ms(value:str)->int:
    dt=datetime.fromisoformat(value.replace("Z","+00:00"))
    if dt.tzinfo is None:raise ValueError("timestamp must include timezone")
    return int(dt.astimezone(timezone.utc).timestamp()*1000)


def _sha256(path:Path)->str:
    h=sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda:fh.read(1024*1024),b""):h.update(chunk)
    return h.hexdigest()


def merge(*,bars_path:Path,funding_path:Path,output:Path,report:Path|None=None)->dict:
    bars=[]
    with Path(bars_path).open("r",encoding="utf-8-sig",newline="") as fh:
        reader=csv.DictReader(fh)
        fields=list(reader.fieldnames or [])
        if "timestamp" not in fields:raise RuntimeError("bars missing timestamp")
        for row in reader:bars.append(row)
    if not bars:raise RuntimeError("bars file empty")
    bar_ts=[_ms(r["timestamp"]) for r in bars]
    if bar_ts!=sorted(bar_ts) or len(set(bar_ts))!=len(bar_ts):raise RuntimeError("bar timestamps must be unique ascending")
    if any((b-a)!=STEP_MS for a,b in zip(bar_ts,bar_ts[1:])):raise RuntimeError("bars must have exact 5m cadence")

    events=[]
    with Path(funding_path).open("r",encoding="utf-8-sig",newline="") as fh:
        for row in csv.DictReader(fh):
            ts=row.get("timestamp");rate=row.get("funding_rate")
            if not ts or rate in (None,""):raise RuntimeError("funding row missing timestamp/rate")
            events.append((_ms(ts),float(rate)))
    if not events:raise RuntimeError("funding file empty")
    event_ts=[x[0] for x in events]
    if event_ts!=sorted(event_ts) or len(set(event_ts))!=len(event_ts):raise RuntimeError("funding timestamps must be unique ascending")

    first,last=bar_ts[0],bar_ts[-1]+STEP_MS
    in_window=[x for x in events if first<=x[0]<last]
    per_bar={ts:0.0 for ts in bar_ts};count=0
    starts=set(bar_ts)
    for ts,rate in in_window:
        bar_open=ts-(ts%STEP_MS)
        if bar_open not in starts:raise RuntimeError(f"funding event does not map to a known 5m bar: {ts}")
        per_bar[bar_open]+=rate;count+=1

    output=Path(output);output.parent.mkdir(parents=True,exist_ok=True)
    out_fields=fields if "funding_rate" in fields else fields+["funding_rate"]
    with output.open("w",encoding="utf-8",newline="") as fh:
        w=csv.DictWriter(fh,fieldnames=out_fields);w.writeheader()
        for row,ts in zip(bars,bar_ts):
            row=dict(row);row["funding_rate"]=per_bar[ts];w.writerow(row)
    payload={
        "mode":"RESEARCH_ONLY_EXACT_EVENT_FUNDING_PIT_MERGE",
        "bars_source":str(bars_path),"bars_source_sha256":_sha256(Path(bars_path)),
        "funding_source":str(funding_path),"funding_source_sha256":_sha256(Path(funding_path)),
        "output":str(output),"output_sha256":_sha256(output),
        "bar_count":len(bars),"funding_events_total":len(events),"funding_events_merged":count,
        "merge_semantics":"event belongs to half-open 5m bar interval [open,open+5m); no fill/interpolation",
        "interpolation_used":False,"forward_fill_used":False,"current_state_backfill_used":False,
        "live_capital_allowed":False,"automatic_real_money_execution":False,
    }
    if report is not None:
        report=Path(report);report.parent.mkdir(parents=True,exist_ok=True);report.write_text(json.dumps(payload,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    return payload


def main(argv:list[str]|None=None)->int:
    p=argparse.ArgumentParser(description="Merge exact funding events into historical 5m bars")
    p.add_argument("--bars",type=Path,required=True);p.add_argument("--funding",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True);p.add_argument("--report",type=Path)
    a=p.parse_args(argv);result=merge(bars_path=a.bars,funding_path=a.funding,output=a.output,report=a.report)
    print(json.dumps(result,indent=2,sort_keys=True));return 0

if __name__=="__main__":raise SystemExit(main())
