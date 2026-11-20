"""Acquire warm-up data and derive exact PIT trailing-24h quote volume for BTC/ETH/SOL.

Research-only. Reuses Binance public USD-M monthly 5m klines, expands the locked window
backward exactly 24h, checksum-verifies raw archives, and writes one provider-neutral
rolling-volume artifact per Atlas symbol. No current-state backfill or live path.
"""
from __future__ import annotations

import argparse,json
from datetime import datetime,timedelta,timezone
from pathlib import Path

from app.backtest.binance_public_acquire import acquire,plan
from app.backtest.binance_public_rolling_volume import derive

SYMBOLS=("BTC","ETH","SOL")
PROVIDER={"BTC":"BTCUSDT","ETH":"ETHUSDT","SOL":"SOLUSDT"}


def _dt(value:str)->datetime:
    dt=datetime.fromisoformat(value.replace("Z","+00:00"))
    if dt.tzinfo is None:raise ValueError("timestamp must include timezone")
    return dt.astimezone(timezone.utc)


def _iso(dt:datetime)->str:
    return dt.isoformat().replace("+00:00","Z")


def run(*,start_utc:str,end_utc:str,raw_root:Path,output_root:Path,symbols:tuple[str,...]=SYMBOLS,execute:bool=False)->dict:
    bad=sorted(set(symbols)-set(SYMBOLS))
    if bad:raise ValueError(f"unsupported symbols: {', '.join(bad)}")
    start,end=_dt(start_utc),_dt(end_utc)
    if end<=start:raise ValueError("end must be after start")
    warmup=start-timedelta(hours=24)
    payload=plan(start_utc=_iso(warmup),end_utc=end_utc,raw_root=raw_root,symbols=symbols,intervals=("5m",))
    if execute:payload=acquire(payload)
    normalized=[]
    if execute:
        for symbol in symbols:
            provider=PROVIDER[symbol]
            inputs=[Path(obj["local_zip"]) for obj in payload["objects"] if obj["symbol"]==symbol and obj["interval"]=="5m"]
            if not inputs:raise RuntimeError(f"no acquired 5m archives for {symbol}")
            output=Path(output_root)/f"{symbol}-volume24h-5m.csv"
            report=Path(output_root)/f"{symbol}-volume24h-5m.normalization.json"
            normalized.append(derive(inputs=inputs,provider_symbol=provider,start_utc=start_utc,end_utc=end_utc,output=output,report=report))
    return {
        "mode":"RESEARCH_ONLY_BINANCE_PUBLIC_ROLLING_VOLUME_BATCH",
        "start_utc":start_utc,"end_utc":end_utc,"warmup_start_utc":_iso(warmup),
        "symbols":list(symbols),"objects":payload["objects"],"object_count":len(payload["objects"]),
        "normalized_outputs":normalized,"normalized_output_count":len(normalized),
        "pit_rolling_volume_context_complete":bool(execute and len(normalized)==len(symbols)),
        "current_state_backfill_used":False,"live_capital_allowed":False,"automatic_real_money_execution":False,
        "status":"ACQUIRED_AND_DERIVED_ROLLING_VOLUME" if execute else "PLANNED_NOT_DOWNLOADED",
    }


def main(argv:list[str]|None=None)->int:
    p=argparse.ArgumentParser(description="Acquire/derive full locked Binance rolling-volume batch")
    p.add_argument("--start",required=True);p.add_argument("--end",required=True)
    p.add_argument("--raw-root",type=Path,required=True);p.add_argument("--output-root",type=Path,required=True)
    p.add_argument("--manifest",type=Path,required=True);p.add_argument("--symbols",nargs="+",default=list(SYMBOLS));p.add_argument("--execute",action="store_true")
    a=p.parse_args(argv);result=run(start_utc=a.start,end_utc=a.end,raw_root=a.raw_root,output_root=a.output_root,symbols=tuple(x.upper() for x in a.symbols),execute=a.execute)
    a.manifest.parent.mkdir(parents=True,exist_ok=True);a.manifest.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(f"rolling_volume_batch_manifest={a.manifest}")
    print(f"objects={result['object_count']} normalized_outputs={result['normalized_output_count']} status={result['status']}")
    return 0

if __name__=="__main__":raise SystemExit(main())
