"""Normalize verified Binance public USD-M kline ZIPs into deterministic Atlas candles.

Research-only. This module never fabricates PIT OI/rolling-volume context and cannot
make historical source readiness GREEN by itself.
"""
from __future__ import annotations

import argparse,csv,json,zipfile
from datetime import datetime,timezone
from hashlib import sha256
from pathlib import Path

from app.backtest.binance_public_inspect import EXPECTED_COLUMNS,HEADER_FIRST_COLUMNS,INTERVAL_MS

SYMBOL_MAP={"BTCUSDT":"BTC","ETHUSDT":"ETH","SOLUSDT":"SOL"}
FIELDS=["timestamp","symbol","timeframe","open","high","low","close","volume"]


def _iso(ms:int)->str:
    return datetime.fromtimestamp(ms/1000,tz=timezone.utc).isoformat().replace("+00:00","Z")


def _ms(value:str)->int:
    text=value.strip().replace("Z","+00:00")
    dt=datetime.fromisoformat(text)
    if dt.tzinfo is None:raise ValueError("timestamp must include timezone")
    return int(dt.astimezone(timezone.utc).timestamp()*1000)


def _sha256(path:Path)->str:
    h=sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda:fh.read(1024*1024),b""):h.update(chunk)
    return h.hexdigest()


def _rows(path:Path)->list[list[str]]:
    path=Path(path)
    with zipfile.ZipFile(path) as zf:
        members=[n for n in zf.namelist() if n.lower().endswith('.csv')]
        if len(members)!=1:raise RuntimeError(f"expected exactly one CSV member, found {len(members)}")
        with zf.open(members[0]) as raw:
            text=(line.decode('utf-8-sig').strip() for line in raw)
            rows=list(csv.reader(line for line in text if line))
    if not rows:raise RuntimeError("kline archive CSV is empty")
    if any(len(r)!=EXPECTED_COLUMNS for r in rows):raise RuntimeError("unexpected Binance kline column count")
    if rows[0] and rows[0][0].strip().lower() in HEADER_FIRST_COLUMNS:rows=rows[1:]
    if not rows:raise RuntimeError("kline archive has no data rows")
    return rows


def normalize(*,inputs:list[Path],provider_symbol:str,interval:str,start_utc:str,end_utc:str,output:Path,report:Path|None=None)->dict:
    provider_symbol=provider_symbol.upper()
    if provider_symbol not in SYMBOL_MAP:raise ValueError(f"unsupported provider symbol: {provider_symbol}")
    if interval not in INTERVAL_MS:raise ValueError(f"unsupported interval: {interval}")
    start_ms,end_ms=_ms(start_utc),_ms(end_utc)
    if end_ms<=start_ms:raise ValueError("end must be after start")
    step=INTERVAL_MS[interval]
    if start_ms%step or end_ms%step:raise ValueError("window must align exactly to candle cadence")

    candles={};sources=[]
    for path in sorted(map(Path,inputs),key=lambda p:p.name):
        sources.append({"path":str(path),"sha256":_sha256(path)})
        for row in _rows(path):
            try:ts=int(row[0]);o,h,l,c,v=map(float,row[1:6])
            except Exception as exc:raise RuntimeError(f"invalid numeric kline row in {path}") from exc
            if not(start_ms<=ts<end_ms):
                continue
            if ts in candles:raise RuntimeError(f"duplicate candle timestamp across archives: {ts}")
            if min(o,h,l,c)<=0 or v<0:raise RuntimeError(f"nonpositive price or negative volume at {ts}")
            if h<max(o,c,l) or l>min(o,c,h):raise RuntimeError(f"invalid OHLC envelope at {ts}")
            candles[ts]=(o,h,l,c,v)

    expected=list(range(start_ms,end_ms,step))
    actual=sorted(candles)
    missing=sorted(set(expected)-set(actual))
    extra=sorted(set(actual)-set(expected))
    if extra:raise RuntimeError(f"unexpected timestamps inside normalized set: {len(extra)}")
    if missing:raise RuntimeError(f"normalized candles contain cadence/window gaps: {len(missing)}")
    if actual!=expected:raise RuntimeError("normalized timestamps are not exact ascending half-open window cadence")

    output=Path(output);output.parent.mkdir(parents=True,exist_ok=True)
    with output.open("w",encoding="utf-8",newline="") as fh:
        writer=csv.DictWriter(fh,fieldnames=FIELDS);writer.writeheader()
        symbol=SYMBOL_MAP[provider_symbol]
        for ts in actual:
            o,h,l,c,v=candles[ts]
            writer.writerow({"timestamp":_iso(ts),"symbol":symbol,"timeframe":interval,"open":o,"high":h,"low":l,"close":c,"volume":v})

    payload={
        "mode":"RESEARCH_ONLY_BINANCE_PUBLIC_CANDLE_NORMALIZATION",
        "provider_symbol":provider_symbol,"symbol":SYMBOL_MAP[provider_symbol],"interval":interval,
        "start_utc":_iso(start_ms),"end_utc":_iso(end_ms),"row_count":len(actual),
        "first_timestamp":_iso(actual[0]) if actual else None,"last_timestamp":_iso(actual[-1]) if actual else None,
        "output":str(output),"output_sha256":_sha256(output),"raw_sources":sources,
        "pit_context_complete":False,"live_capital_allowed":False,"automatic_real_money_execution":False,
    }
    if report is not None:
        report=Path(report);report.parent.mkdir(parents=True,exist_ok=True)
        report.write_text(json.dumps(payload,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    return payload


def main(argv:list[str]|None=None)->int:
    p=argparse.ArgumentParser(description="Normalize verified Binance public klines into Atlas candle CSV")
    p.add_argument("--input",type=Path,nargs="+",required=True)
    p.add_argument("--provider-symbol",required=True)
    p.add_argument("--interval",choices=sorted(INTERVAL_MS),required=True)
    p.add_argument("--start",required=True);p.add_argument("--end",required=True)
    p.add_argument("--output",type=Path,required=True);p.add_argument("--report",type=Path)
    a=p.parse_args(argv)
    result=normalize(inputs=a.input,provider_symbol=a.provider_symbol,interval=a.interval,start_utc=a.start,end_utc=a.end,output=a.output,report=a.report)
    print(json.dumps(result,indent=2,sort_keys=True));return 0

if __name__=="__main__":raise SystemExit(main())
