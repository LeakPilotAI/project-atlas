"""Acquire official Hyperliquid historical data that is still available via the info API.

Research-only. Historical candleSnapshot is retention-limited to the most recent 5000
candles per interval, so old locked research windows must never silently produce empty
candle files and be mistaken for successful acquisition. External/archive reconstruction
remains required for out-of-retention candles and PIT historical OI/context.
"""
from __future__ import annotations

import argparse,asyncio,json,time
from datetime import datetime,timezone
from pathlib import Path
from typing import Any

import httpx

INFO_URL="https://api.hyperliquid.xyz/info"
SYMBOLS=("BTC","ETH","SOL")
INTERVAL_MS={"5m":300_000,"1h":3_600_000}
MAX_CANDLES_PER_REQUEST=5000
FUNDING_CHUNK_MS=30*24*3_600_000


def _ms(value:str)->int:
    d=datetime.fromisoformat(value.replace("Z","+00:00"))
    if d.tzinfo is None:d=d.replace(tzinfo=timezone.utc)
    return int(d.astimezone(timezone.utc).timestamp()*1000)


def _dump(path:Path,rows:list[dict[str,Any]])->None:
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(rows,indent=2,sort_keys=True)+"\n",encoding="utf-8")


def candle_retention_floor_ms(interval:str,*,now_ms:int|None=None)->int:
    """Earliest open timestamp that can plausibly exist in candleSnapshot retention."""
    if interval not in INTERVAL_MS:raise ValueError(f"unsupported interval: {interval}")
    current=int(now_ms if now_ms is not None else time.time()*1000)
    return current-(MAX_CANDLES_PER_REQUEST*INTERVAL_MS[interval])


def candle_request_within_retention(*,interval:str,end_ms:int,now_ms:int|None=None)->bool:
    """True only when the requested range reaches the API's current retention window."""
    return end_ms>candle_retention_floor_ms(interval,now_ms=now_ms)


async def _post(client:httpx.AsyncClient,body:dict[str,Any])->Any:
    r=await client.post(INFO_URL,json=body);r.raise_for_status();return r.json()


async def fetch_candles(client:httpx.AsyncClient,*,symbol:str,interval:str,start_ms:int,end_ms:int,now_ms:int|None=None)->list[dict[str,Any]]:
    if not candle_request_within_retention(interval=interval,end_ms=end_ms,now_ms=now_ms):
        raise RuntimeError(
            f"{interval} candle request for {symbol} ends before Hyperliquid candleSnapshot retention; "
            "use historical archive/provider reconstruction instead"
        )
    step=INTERVAL_MS[interval]
    floor=candle_retention_floor_ms(interval,now_ms=now_ms)
    cursor=max(start_ms,floor)
    by_ts:dict[int,dict[str,Any]]={}
    while cursor<end_ms:
        chunk_end=min(end_ms-1,cursor+step*(MAX_CANDLES_PER_REQUEST-1))
        data=await _post(client,{"type":"candleSnapshot","req":{"coin":symbol,"interval":interval,"startTime":cursor,"endTime":chunk_end}})
        if not isinstance(data,list):raise ValueError("unexpected candleSnapshot response")
        for row in data:
            if not isinstance(row,dict):continue
            ts=int(row.get("t") or 0)
            if start_ms<=ts<end_ms:by_ts[ts]=row
        cursor=chunk_end+step
    return [by_ts[k] for k in sorted(by_ts)]


async def fetch_funding(client:httpx.AsyncClient,*,symbol:str,start_ms:int,end_ms:int)->list[dict[str,Any]]:
    cursor=start_ms;by_ts:dict[int,dict[str,Any]]={}
    while cursor<end_ms:
        chunk_end=min(end_ms,cursor+FUNDING_CHUNK_MS)
        data=await _post(client,{"type":"fundingHistory","coin":symbol,"startTime":cursor,"endTime":chunk_end})
        if not isinstance(data,list):raise ValueError("unexpected fundingHistory response")
        for row in data:
            if not isinstance(row,dict):continue
            ts=int(row.get("time") or 0)
            if start_ms<=ts<end_ms:by_ts[ts]=row
        cursor=chunk_end
    return [by_ts[k] for k in sorted(by_ts)]


async def acquire(*,start_utc:str,end_utc:str,raw_root:Path,symbols:tuple[str,...]=SYMBOLS)->dict[str,Any]:
    start_ms,end_ms=_ms(start_utc),_ms(end_utc)
    if start_ms>=end_ms:raise ValueError("start must precede end")
    unknown=[s for s in symbols if s not in SYMBOLS]
    if unknown:raise ValueError(f"unsupported representative symbols: {unknown}")
    now_ms=int(time.time()*1000)
    c5_available=candle_request_within_retention(interval="5m",end_ms=end_ms,now_ms=now_ms)
    c1_available=candle_request_within_retention(interval="1h",end_ms=end_ms,now_ms=now_ms)
    manifest={
        "mode":"RESEARCH_HISTORICAL_ACQUISITION",
        "source":"hyperliquid:info",
        "start_utc":start_utc,"end_utc":end_utc,
        "live_capital_allowed":False,
        "automatic_real_money_execution":False,
        "current_state_backfill_allowed":False,
        "candle_snapshot_retention":{"max_candles":MAX_CANDLES_PER_REQUEST,"5m_available":c5_available,"1h_available":c1_available},
        "out_of_retention_candle_source_required":not (c5_available and c1_available),
        "historical_archive_note":"Use Hyperliquid requester-pays archive and/or verified historical provider for out-of-retention reconstruction; do not treat empty candleSnapshot as successful history.",
        "symbols":{},
    }
    async with httpx.AsyncClient(timeout=httpx.Timeout(30.0,connect=10.0),headers={"Content-Type":"application/json"}) as client:
        for symbol in symbols:
            c5=[];c1=[]
            if c5_available:c5=await fetch_candles(client,symbol=symbol,interval="5m",start_ms=start_ms,end_ms=end_ms,now_ms=now_ms)
            if c1_available:c1=await fetch_candles(client,symbol=symbol,interval="1h",start_ms=start_ms,end_ms=end_ms,now_ms=now_ms)
            funding=await fetch_funding(client,symbol=symbol,start_ms=start_ms,end_ms=end_ms)
            p5=raw_root/f"{symbol}-5m.candles.json";p1=raw_root/f"{symbol}-1h.candles.json";pf=raw_root/f"{symbol}-5m.funding.json"
            if c5_available:_dump(p5,c5)
            if c1_available:_dump(p1,c1)
            _dump(pf,funding)
            manifest["symbols"][symbol]={
                "candles_5m":{"path":str(p5),"rows":len(c5),"status":"ACQUIRED" if c5_available else "OUT_OF_RETENTION_EXTERNAL_RECONSTRUCTION_REQUIRED"},
                "candles_1h":{"path":str(p1),"rows":len(c1),"status":"ACQUIRED" if c1_available else "OUT_OF_RETENTION_EXTERNAL_RECONSTRUCTION_REQUIRED"},
                "funding":{"path":str(pf),"rows":len(funding),"status":"ACQUIRED"},
                "historical_oi_required":True,
            }
    return manifest


def main(argv:list[str]|None=None)->int:
    p=argparse.ArgumentParser(description="Acquire official Hyperliquid historical data still available via info API")
    p.add_argument("--start",required=True);p.add_argument("--end",required=True)
    p.add_argument("--raw-root",type=Path,default=Path("backend/data/research/raw/historical"))
    p.add_argument("--manifest",type=Path,default=Path("backend/data/research/historical/hyperliquid-acquisition.json"))
    a=p.parse_args(argv);payload=asyncio.run(acquire(start_utc=a.start,end_utc=a.end,raw_root=a.raw_root))
    a.manifest.parent.mkdir(parents=True,exist_ok=True);a.manifest.write_text(json.dumps(payload,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(f"acquisition_manifest={a.manifest}")
    for symbol,row in payload["symbols"].items():
        print(f"{symbol}: 5m={row['candles_5m']['status']}({row['candles_5m']['rows']}) 1h={row['candles_1h']['status']}({row['candles_1h']['rows']}) funding={row['funding']['rows']} oi=PENDING_EXTERNAL_PIT_SOURCE")
    return 0

if __name__=="__main__":raise SystemExit(main())
