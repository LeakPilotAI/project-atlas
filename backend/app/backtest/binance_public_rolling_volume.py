"""Derive exact PIT trailing-24h quote-notional volume from Binance USD-M 5m klines.

Research-only. Uses the provider's historical quote_volume field (column 7), never
base-volume approximations or current-state backfills. A full 24h warm-up is required
before the first emitted decision timestamp.
"""
from __future__ import annotations

import argparse,csv,json,zipfile
from collections import deque
from datetime import datetime,timezone
from hashlib import sha256
from pathlib import Path

from app.backtest.binance_public_inspect import EXPECTED_COLUMNS,HEADER_FIRST_COLUMNS,INTERVAL_MS

SYMBOL_MAP={"BTCUSDT":"BTC","ETHUSDT":"ETH","SOLUSDT":"SOL"}
FIELDS=["timestamp","volume_24h_usd"]
QUOTE_VOLUME_INDEX=7
STEP_MS=INTERVAL_MS["5m"]
WINDOW_BARS=24*60//5


def _ms(value:str)->int:
    dt=datetime.fromisoformat(value.strip().replace("Z","+00:00"))
    if dt.tzinfo is None:raise ValueError("timestamp must include timezone")
    return int(dt.astimezone(timezone.utc).timestamp()*1000)


def _iso(ms:int)->str:
    return datetime.fromtimestamp(ms/1000,tz=timezone.utc).isoformat().replace("+00:00","Z")


def _sha256(path:Path)->str:
    h=sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda:fh.read(1024*1024),b""):h.update(chunk)
    return h.hexdigest()


def _rows(path:Path)->list[list[str]]:
    with zipfile.ZipFile(path) as zf:
        members=[n for n in zf.namelist() if n.lower().endswith(".csv")]
        if len(members)!=1:raise RuntimeError(f"expected exactly one CSV member, found {len(members)}")
        with zf.open(members[0]) as raw:
            text=(line.decode("utf-8-sig").strip() for line in raw)
            rows=list(csv.reader(line for line in text if line))
    if not rows:raise RuntimeError("kline archive CSV is empty")
    if any(len(r)!=EXPECTED_COLUMNS for r in rows):raise RuntimeError("unexpected Binance kline column count")
    if rows[0][0].strip().lower() in HEADER_FIRST_COLUMNS:rows=rows[1:]
    if not rows:raise RuntimeError("kline archive has no data rows")
    return rows


def derive(*,inputs:list[Path],provider_symbol:str,start_utc:str,end_utc:str,output:Path,report:Path|None=None)->dict:
    provider_symbol=provider_symbol.upper()
    if provider_symbol not in SYMBOL_MAP:raise ValueError(f"unsupported provider symbol: {provider_symbol}")
    start,end=_ms(start_utc),_ms(end_utc)
    if end<=start:raise ValueError("end must be after start")
    if start%STEP_MS or end%STEP_MS:raise ValueError("window must align to 5m cadence")
    warmup=start-WINDOW_BARS*STEP_MS
    bars={};sources=[]
    for path in sorted(map(Path,inputs),key=lambda p:p.name):
        sources.append({"path":str(path),"sha256":_sha256(path)})
        for row in _rows(path):
            try:ts=int(row[0]);quote=float(row[QUOTE_VOLUME_INDEX])
            except Exception as exc:raise RuntimeError(f"invalid timestamp/quote_volume in {path}") from exc
            if warmup<=ts<end:
                if ts in bars:raise RuntimeError(f"duplicate candle timestamp across archives: {ts}")
                if quote<0:raise RuntimeError(f"negative quote_volume at {ts}")
                bars[ts]=quote
    expected=list(range(warmup,end,STEP_MS))
    actual=sorted(bars)
    missing=sorted(set(expected)-set(actual))
    if missing:raise RuntimeError(f"rolling-volume source lacks exact 24h warm-up/window cadence: {len(missing)} missing; first={_iso(missing[0])}")
    if actual!=expected:raise RuntimeError("rolling-volume source timestamps are not exact ascending cadence")

    q=deque();rolling=0.0;values=[]
    for ts in actual:
        q.append(bars[ts]);rolling+=bars[ts]
        if len(q)>WINDOW_BARS:rolling-=q.popleft()
        if ts>=start:
            if len(q)!=WINDOW_BARS:raise RuntimeError(f"incomplete trailing 24h window at {_iso(ts)}")
            values.append((ts,rolling))
    expected_outputs=(end-start)//STEP_MS
    if len(values)!=expected_outputs:raise RuntimeError("rolling-volume output does not cover exact requested decision window")

    output=Path(output);output.parent.mkdir(parents=True,exist_ok=True)
    with output.open("w",encoding="utf-8",newline="") as fh:
        w=csv.DictWriter(fh,fieldnames=FIELDS);w.writeheader()
        for ts,value in values:w.writerow({"timestamp":_iso(ts),"volume_24h_usd":value})
    payload={
        "mode":"RESEARCH_ONLY_EXACT_PIT_ROLLING_QUOTE_VOLUME",
        "provider_symbol":provider_symbol,"symbol":SYMBOL_MAP[provider_symbol],
        "start_utc":_iso(start),"end_utc":_iso(end),"warmup_start_utc":_iso(warmup),
        "cadence_seconds":300,"window_bars":WINDOW_BARS,"row_count":len(values),
        "first_timestamp":_iso(values[0][0]) if values else None,"last_timestamp":_iso(values[-1][0]) if values else None,
        "source_field":"quote_volume","source_column_index":QUOTE_VOLUME_INDEX,
        "output":str(output),"output_sha256":_sha256(output),"raw_sources":sources,
        "pit_rolling_volume_context_complete":True,"current_state_backfill_used":False,
        "live_capital_allowed":False,"automatic_real_money_execution":False,
    }
    if report is not None:
        report=Path(report);report.parent.mkdir(parents=True,exist_ok=True);report.write_text(json.dumps(payload,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    return payload


def main(argv:list[str]|None=None)->int:
    p=argparse.ArgumentParser(description="Derive exact PIT trailing-24h quote-notional volume")
    p.add_argument("--input",type=Path,nargs="+",required=True);p.add_argument("--provider-symbol",required=True)
    p.add_argument("--start",required=True);p.add_argument("--end",required=True);p.add_argument("--output",type=Path,required=True);p.add_argument("--report",type=Path)
    a=p.parse_args(argv);result=derive(inputs=a.input,provider_symbol=a.provider_symbol,start_utc=a.start,end_utc=a.end,output=a.output,report=a.report)
    print(json.dumps(result,indent=2,sort_keys=True));return 0

if __name__=="__main__":raise SystemExit(main())
