"""Acquire first-party Hyperliquid historical funding events for research.

Uses Hyperliquid's public info endpoint with type=fundingHistory. Exact event timestamps
and rates are preserved. No interpolation, no current-state funding, no live execution.
"""
from __future__ import annotations

import argparse,csv,json,urllib.request
from datetime import datetime,timezone
from hashlib import sha256
from pathlib import Path

INFO_URL="https://api.hyperliquid.xyz/info"
SYMBOLS=("BTC","ETH","SOL")
FIELDS=["timestamp","funding_rate"]


def _ms(value:str)->int:
    dt=datetime.fromisoformat(value.replace("Z","+00:00"))
    if dt.tzinfo is None:raise ValueError("timestamp must include timezone")
    return int(dt.astimezone(timezone.utc).timestamp()*1000)


def _iso(ms:int)->str:
    return datetime.fromtimestamp(ms/1000,tz=timezone.utc).isoformat().replace("+00:00","Z")


def _sha256(path:Path)->str:
    h=sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda:fh.read(1024*1024),b""):h.update(chunk)
    return h.hexdigest()


def acquire(*,symbol:str,start_utc:str,end_utc:str,output:Path,report:Path|None=None)->dict:
    symbol=symbol.upper()
    if symbol not in SYMBOLS:raise ValueError(f"unsupported symbol: {symbol}")
    start,end=_ms(start_utc),_ms(end_utc)
    if end<=start:raise ValueError("end must be after start")
    body=json.dumps({"type":"fundingHistory","coin":symbol,"startTime":start,"endTime":end}).encode()
    req=urllib.request.Request(INFO_URL,data=body,headers={"Content-Type":"application/json"},method="POST")
    with urllib.request.urlopen(req,timeout=60) as response:
        raw=json.loads(response.read().decode("utf-8"))
    if not isinstance(raw,list):raise RuntimeError("unexpected Hyperliquid fundingHistory response")
    rows=[];seen=set();last=None
    for item in raw:
        if not isinstance(item,dict):raise RuntimeError("fundingHistory row must be object")
        ts=int(item.get("time"));rate=float(item.get("fundingRate"))
        if not(start<=ts<end):continue
        if ts in seen:raise RuntimeError(f"duplicate funding timestamp: {ts}")
        if last is not None and ts<=last:raise RuntimeError("funding events not strictly ascending")
        seen.add(ts);last=ts;rows.append((ts,rate))
    if not rows:raise RuntimeError("no Hyperliquid funding events returned for requested window")
    output=Path(output);output.parent.mkdir(parents=True,exist_ok=True)
    with output.open("w",encoding="utf-8",newline="") as fh:
        w=csv.DictWriter(fh,fieldnames=FIELDS);w.writeheader()
        for ts,rate in rows:w.writerow({"timestamp":_iso(ts),"funding_rate":rate})
    payload={
        "mode":"RESEARCH_ONLY_HYPERLIQUID_FUNDING_HISTORY",
        "source":"hyperliquid:/info fundingHistory","symbol":symbol,
        "start_utc":_iso(start),"end_utc":_iso(end),"row_count":len(rows),
        "first_timestamp":_iso(rows[0][0]),"last_timestamp":_iso(rows[-1][0]),
        "output":str(output),"output_sha256":_sha256(output),
        "exact_event_timestamps":True,"interpolation_used":False,"current_state_backfill_used":False,
        "live_capital_allowed":False,"automatic_real_money_execution":False,
    }
    if report is not None:
        report=Path(report);report.parent.mkdir(parents=True,exist_ok=True);report.write_text(json.dumps(payload,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    return payload


def main(argv:list[str]|None=None)->int:
    p=argparse.ArgumentParser(description="Acquire first-party Hyperliquid funding history")
    p.add_argument("--symbol",required=True);p.add_argument("--start",required=True);p.add_argument("--end",required=True)
    p.add_argument("--output",type=Path,required=True);p.add_argument("--report",type=Path)
    a=p.parse_args(argv);result=acquire(symbol=a.symbol,start_utc=a.start,end_utc=a.end,output=a.output,report=a.report)
    print(json.dumps(result,indent=2,sort_keys=True));return 0

if __name__=="__main__":raise SystemExit(main())
