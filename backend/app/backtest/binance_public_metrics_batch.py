"""Acquire and normalize full locked-window Binance public futures OI metrics.

Research-only. Produces non-canonical provider-neutral 5m OI context for BTC/ETH/SOL.
Does not fabricate rolling-volume context and cannot make source_audit GREEN alone.
"""
from __future__ import annotations

import argparse,json
from datetime import datetime,timezone,timedelta
from pathlib import Path

from app.backtest.binance_public_metrics import plan as metrics_plan, acquire as metrics_acquire
from app.backtest.binance_public_metrics_normalize import normalize as normalize_oi

SYMBOL_MAP={"BTC":"BTCUSDT","ETH":"ETHUSDT","SOL":"SOLUSDT"}


def _dt(value:str)->datetime:
    dt=datetime.fromisoformat(value.replace("Z","+00:00"))
    if dt.tzinfo is None:raise ValueError("timestamp must include timezone")
    return dt.astimezone(timezone.utc)


def _iso(dt:datetime)->str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00","Z")


def _dates(start:str,end:str)->list[str]:
    s,e=_dt(start),_dt(end)
    if s.time().isoformat()!="00:00:00" or e.time().isoformat()!="00:00:00":raise ValueError("metrics batch boundaries must be UTC midnight")
    if e<=s:raise ValueError("end must be after start")
    cur=s;out=[]
    while cur<e:
        out.append(cur.date().isoformat());cur+=timedelta(days=1)
    return out


def run(*,start_utc:str,end_utc:str,raw_root:Path,output_root:Path,symbols:tuple[str,...]=( "BTC","ETH","SOL"),execute:bool=False,max_missing_intervals:int=2)->dict:
    bad=sorted(set(symbols)-set(SYMBOL_MAP))
    if bad:raise ValueError(f"unsupported symbols: {', '.join(bad)}")
    if max_missing_intervals<0:raise ValueError("max_missing_intervals must be nonnegative")
    dates=_dates(start_utc,end_utc)
    payload=metrics_plan(start_utc=start_utc,end_utc=end_utc,raw_root=raw_root,symbols=symbols)
    if execute:payload=metrics_acquire(payload)
    normalized=[]
    if execute:
        for symbol in symbols:
            provider=SYMBOL_MAP[symbol]
            inputs=[Path(raw_root)/"binance_public_metrics"/provider/f"{provider}-metrics-{d}.zip" for d in dates]
            output=Path(output_root)/f"{symbol}-oi-5m.csv"
            report=Path(output_root)/f"{symbol}-oi-5m.normalization.json"
            result=normalize_oi(inputs=inputs,provider_symbol=provider,start_utc=start_utc,end_utc=end_utc,output=output,report=report,max_missing_intervals=max_missing_intervals)
            normalized.append(result)
    return {
        "mode":"RESEARCH_ONLY_BINANCE_PUBLIC_OI_BATCH",
        "start_utc":start_utc,"end_utc":end_utc,"symbols":list(symbols),
        "objects":payload["objects"],"object_count":len(payload["objects"]),
        "normalized_outputs":normalized,"normalized_output_count":len(normalized),
        "max_missing_intervals":max_missing_intervals,
        "pit_oi_context_complete":bool(execute and len(normalized)==len(symbols)),
        "rolling_volume_context_complete":False,
        "live_capital_allowed":False,"automatic_real_money_execution":False,
        "status":"ACQUIRED_AND_NORMALIZED_OI_ROLLING_VOLUME_STILL_REQUIRED" if execute else "PLANNED_NOT_DOWNLOADED",
    }


def main(argv:list[str]|None=None)->int:
    p=argparse.ArgumentParser(description="Acquire/normalize full Binance public historical OI metrics batch")
    p.add_argument("--start",required=True);p.add_argument("--end",required=True)
    p.add_argument("--raw-root",type=Path,default=Path("backend/data/research/raw/historical/dev-2024-h2-metrics"))
    p.add_argument("--output-root",type=Path,default=Path("backend/data/research/historical/dev-2024-h2-oi"))
    p.add_argument("--manifest",type=Path,default=Path("backend/data/research/historical/binance-public-oi-batch.json"))
    p.add_argument("--symbols",nargs="+",default=["BTC","ETH","SOL"]);p.add_argument("--execute",action="store_true")
    p.add_argument("--max-missing-intervals",type=int,default=2)
    a=p.parse_args(argv)
    result=run(start_utc=a.start,end_utc=a.end,raw_root=a.raw_root,output_root=a.output_root,symbols=tuple(x.upper() for x in a.symbols),execute=a.execute,max_missing_intervals=a.max_missing_intervals)
    a.manifest.parent.mkdir(parents=True,exist_ok=True);a.manifest.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(f"oi_batch_manifest={a.manifest}")
    print(f"objects={result['object_count']} normalized_outputs={result['normalized_output_count']} status={result['status']}")
    return 0

if __name__=="__main__":raise SystemExit(main())
