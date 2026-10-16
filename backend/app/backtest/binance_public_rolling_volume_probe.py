"""Acquire minimum 5m warm-up data and derive a real PIT rolling-volume probe.

Research-only helper for locked representative windows. It expands the acquisition
window backward by exactly 24h so the first requested decision timestamp has a full
trailing 288-bar quote-volume history.
"""
from __future__ import annotations

import argparse,json
from datetime import datetime,timedelta,timezone
from pathlib import Path

from app.backtest.binance_public_acquire import acquire,plan
from app.backtest.binance_public_rolling_volume import derive


def _dt(value:str)->datetime:
    dt=datetime.fromisoformat(value.replace("Z","+00:00"))
    if dt.tzinfo is None:raise ValueError("timestamp must include timezone")
    return dt.astimezone(timezone.utc)


def _iso(dt:datetime)->str:
    return dt.isoformat().replace("+00:00","Z")


def run(*,provider_symbol:str,start_utc:str,end_utc:str,raw_root:Path,output:Path,report:Path,execute:bool=False)->dict:
    start,end=_dt(start_utc),_dt(end_utc)
    warmup=start-timedelta(hours=24)
    atlas_symbol={"BTCUSDT":"BTC","ETHUSDT":"ETH","SOLUSDT":"SOL"}.get(provider_symbol.upper())
    if atlas_symbol is None:raise ValueError(f"unsupported provider symbol: {provider_symbol}")
    payload=plan(start_utc=_iso(warmup),end_utc=end_utc,raw_root=raw_root,symbols=(atlas_symbol,),intervals=("5m",))
    if not execute:
        return {"mode":"RESEARCH_ONLY_ROLLING_VOLUME_PROBE","acquisition":payload,"status":"PLANNED_NOT_DOWNLOADED"}
    acquired=acquire(payload)
    inputs=[Path(obj["local_zip"]) for obj in acquired["objects"]]
    result=derive(inputs=inputs,provider_symbol=provider_symbol,start_utc=start_utc,end_utc=end_utc,output=output,report=report)
    return {"mode":"RESEARCH_ONLY_ROLLING_VOLUME_PROBE","acquisition":acquired,"derivation":result,"status":"ACQUIRED_AND_DERIVED_ROLLING_VOLUME"}


def main(argv:list[str]|None=None)->int:
    p=argparse.ArgumentParser(description="Acquire minimum warm-up and derive real rolling-volume probe")
    p.add_argument("--provider-symbol",required=True);p.add_argument("--start",required=True);p.add_argument("--end",required=True)
    p.add_argument("--raw-root",type=Path,required=True);p.add_argument("--output",type=Path,required=True);p.add_argument("--report",type=Path,required=True)
    p.add_argument("--manifest",type=Path,required=True);p.add_argument("--execute",action="store_true")
    a=p.parse_args(argv);result=run(provider_symbol=a.provider_symbol,start_utc=a.start,end_utc=a.end,raw_root=a.raw_root,output=a.output,report=a.report,execute=a.execute)
    a.manifest.parent.mkdir(parents=True,exist_ok=True);a.manifest.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(f"rolling_volume_probe_manifest={a.manifest}")
    if a.execute:
        d=result["derivation"];print(f"rows={d['row_count']} first={d['first_timestamp']} last={d['last_timestamp']} warmup_start={d['warmup_start_utc']} status={result['status']}")
    else:print("status=PLANNED_NOT_DOWNLOADED")
    return 0

if __name__=="__main__":raise SystemExit(main())
