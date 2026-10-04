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
MAX_PAGES=1000


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


def _request_page(*,symbol:str,start:int,end:int)->list[dict]:
    body=json.dumps({"type":"fundingHistory","coin":symbol,"startTime":start,"endTime":end}).encode()
    req=urllib.request.Request(INFO_URL,data=body,headers={"Content-Type":"application/json"},method="POST")
    with urllib.request.urlopen(req,timeout=60) as response:
        raw=json.loads(response.read().decode("utf-8"))
    if not isinstance(raw,list):raise RuntimeError("unexpected Hyperliquid fundingHistory response")
    return raw


def acquire(*,symbol:str,start_utc:str,end_utc:str,output:Path,report:Path|None=None)->dict:
    symbol=symbol.upper()
    if symbol not in SYMBOLS:raise ValueError(f"unsupported symbol: {symbol}")
    start,end=_ms(start_utc),_ms(end_utc)
    if end<=start:raise ValueError("end must be after start")

    rows=[];seen=set();cursor=start;pages=0;last_global=None
    while cursor<end:
        pages+=1
        if pages>MAX_PAGES:raise RuntimeError("fundingHistory pagination exceeded safety limit")
        raw=_request_page(symbol=symbol,start=cursor,end=end)
        if not raw:break
        page_last=None
        for item in raw:
            if not isinstance(item,dict):raise RuntimeError("fundingHistory row must be object")
            try:ts=int(item.get("time"));rate=float(item.get("fundingRate"))
            except Exception as exc:raise RuntimeError("invalid Hyperliquid fundingHistory row") from exc
            if not(start<=ts<end):continue
            if ts in seen:
                continue
            if last_global is not None and ts<last_global:raise RuntimeError("funding events not ascending across pages")
            seen.add(ts);last_global=ts;page_last=ts;rows.append((ts,rate))
        if page_last is None:break
        next_cursor=page_last+1
        if next_cursor<=cursor:raise RuntimeError("fundingHistory pagination made no forward progress")
        cursor=next_cursor
        if len(raw)<500:break

    if not rows:raise RuntimeError("no Hyperliquid funding events returned for requested window")
    rows.sort(key=lambda x:x[0])
    if any(rows[i][0]>=rows[i+1][0] for i in range(len(rows)-1)):raise RuntimeError("funding events not strictly ascending after pagination")

    output=Path(output);output.parent.mkdir(parents=True,exist_ok=True)
    with output.open("w",encoding="utf-8",newline="") as fh:
        w=csv.DictWriter(fh,fieldnames=FIELDS);w.writeheader()
        for ts,rate in rows:w.writerow({"timestamp":_iso(ts),"funding_rate":rate})
    payload={
        "mode":"RESEARCH_ONLY_HYPERLIQUID_FUNDING_HISTORY",
        "source":"hyperliquid:/info fundingHistory","symbol":symbol,
        "start_utc":_iso(start),"end_utc":_iso(end),"row_count":len(rows),"page_count":pages,
        "first_timestamp":_iso(rows[0][0]),"last_timestamp":_iso(rows[-1][0]),
        "output":str(output),"output_sha256":_sha256(output),
        "pagination":"cursor=last_event_ms+1 until end or short/empty page",
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
