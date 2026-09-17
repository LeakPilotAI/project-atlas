"""Normalize checksum-verified Binance USD-M futures metrics into Atlas PIT OI context.

Research-only. Uses historical sum_open_interest_value as point-in-time open_interest_usd.
Does not synthesize rolling volume or HTF context and cannot make source_audit GREEN alone.
"""
from __future__ import annotations

import argparse,csv,json,zipfile
from datetime import datetime,timezone
from hashlib import sha256
from pathlib import Path

from app.backtest.binance_public_metrics_inspect import REQUIRED_COLUMNS

SYMBOL_MAP={"BTCUSDT":"BTC","ETHUSDT":"ETH","SOLUSDT":"SOL"}
FIELDS=["timestamp","open_interest_usd"]


def _parse_ts(value:str)->datetime:
    text=value.strip()
    dt=datetime.fromisoformat(text.replace("Z","+00:00"))
    if dt.tzinfo is None:dt=dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _iso(dt:datetime)->str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00","Z")


def _sha256(path:Path)->str:
    h=sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda:fh.read(1024*1024),b""):h.update(chunk)
    return h.hexdigest()


def _rows(path:Path)->list[dict[str,str]]:
    path=Path(path)
    with zipfile.ZipFile(path) as zf:
        members=[n for n in zf.namelist() if n.lower().endswith('.csv')]
        if len(members)!=1:raise RuntimeError(f"expected exactly one CSV member, found {len(members)}")
        with zf.open(members[0]) as raw:
            reader=csv.DictReader(line.decode('utf-8-sig') for line in raw)
            if not reader.fieldnames:raise RuntimeError("metrics archive missing header")
            headers={x.strip() for x in reader.fieldnames}
            if not REQUIRED_COLUMNS.issubset(headers):
                missing=sorted(REQUIRED_COLUMNS-headers);raise RuntimeError(f"metrics archive missing required columns: {', '.join(missing)}")
            rows=list(reader)
    if not rows:raise RuntimeError("metrics archive has no data rows")
    return rows


def normalize(*,inputs:list[Path],provider_symbol:str,start_utc:str,end_utc:str,output:Path,report:Path|None=None,expected_cadence_seconds:int=300)->dict:
    provider_symbol=provider_symbol.upper()
    if provider_symbol not in SYMBOL_MAP:raise ValueError(f"unsupported provider symbol: {provider_symbol}")
    start=_parse_ts(start_utc);end=_parse_ts(end_utc)
    if end<=start:raise ValueError("end must be after start")
    cadence=expected_cadence_seconds
    if cadence<=0:raise ValueError("expected cadence must be positive")

    points={};sources=[]
    for path in sorted(map(Path,inputs),key=lambda p:p.name):
        sources.append({"path":str(path),"sha256":_sha256(path)})
        for row in _rows(path):
            if str(row.get("symbol","")).strip().upper()!=provider_symbol:continue
            ts=_parse_ts(row["create_time"])
            if not(start<=ts<end):continue
            key=_iso(ts)
            if key in points:raise RuntimeError(f"duplicate metrics timestamp across archives: {key}")
            try:oi_usd=float(row["sum_open_interest_value"])
            except Exception as exc:raise RuntimeError(f"invalid sum_open_interest_value at {key}") from exc
            if oi_usd<0:raise RuntimeError(f"negative open_interest_usd at {key}")
            points[key]=oi_usd

    if not points:raise RuntimeError("no metrics rows in requested window")
    ordered=sorted(points,key=_parse_ts)
    times=[_parse_ts(x) for x in ordered]
    gaps=[]
    for a,b in zip(times,times[1:]):
        delta=int((b-a).total_seconds())
        if delta!=cadence:gaps.append({"after":_iso(a),"before":_iso(b),"delta_seconds":delta,"missing_intervals":max(0,delta//cadence-1)})
    if gaps:
        preview="; ".join(f"{g['after']} -> {g['before']} ({g['delta_seconds']}s, missing={g['missing_intervals']})" for g in gaps[:10])
        raise RuntimeError(f"normalized OI metrics contain cadence gaps: {len(gaps)}; {preview}")

    output=Path(output);output.parent.mkdir(parents=True,exist_ok=True)
    with output.open("w",encoding="utf-8",newline="") as fh:
        w=csv.DictWriter(fh,fieldnames=FIELDS);w.writeheader()
        for ts in ordered:w.writerow({"timestamp":ts,"open_interest_usd":points[ts]})

    payload={
        "mode":"RESEARCH_ONLY_BINANCE_PUBLIC_OI_NORMALIZATION",
        "provider_symbol":provider_symbol,"symbol":SYMBOL_MAP[provider_symbol],
        "start_utc":_iso(start),"end_utc":_iso(end),"row_count":len(ordered),
        "first_timestamp":ordered[0],"last_timestamp":ordered[-1],"cadence_seconds":cadence,
        "output":str(output),"output_sha256":_sha256(output),"raw_sources":sources,
        "oi_source_field":"sum_open_interest_value","pit_oi_context_complete":True,
        "rolling_volume_context_complete":False,"live_capital_allowed":False,"automatic_real_money_execution":False,
    }
    if report is not None:
        report=Path(report);report.parent.mkdir(parents=True,exist_ok=True)
        report.write_text(json.dumps(payload,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    return payload


def main(argv:list[str]|None=None)->int:
    p=argparse.ArgumentParser(description="Normalize Binance public historical OI metrics")
    p.add_argument("--input",type=Path,nargs="+",required=True);p.add_argument("--provider-symbol",required=True)
    p.add_argument("--start",required=True);p.add_argument("--end",required=True)
    p.add_argument("--output",type=Path,required=True);p.add_argument("--report",type=Path)
    p.add_argument("--expected-cadence-seconds",type=int,default=300)
    a=p.parse_args(argv)
    result=normalize(inputs=a.input,provider_symbol=a.provider_symbol,start_utc=a.start,end_utc=a.end,output=a.output,report=a.report,expected_cadence_seconds=a.expected_cadence_seconds)
    print(json.dumps(result,indent=2,sort_keys=True));return 0

if __name__=="__main__":raise SystemExit(main())
