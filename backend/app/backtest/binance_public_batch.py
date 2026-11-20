"""Acquire and normalize full representative Binance public candle windows.

Research-only orchestration around binance_public_acquire + binance_public_normalize.
It preserves raw ZIP/CHECKSUM provenance, writes non-canonical candle outputs, and
never fabricates PIT OI/rolling-volume context or unlocks live trading.
"""
from __future__ import annotations

import argparse,json
from pathlib import Path

from app.backtest.binance_public_acquire import acquire,plan
from app.backtest.binance_public_normalize import normalize

SYMBOLS=("BTC","ETH","SOL")
PROVIDER={"BTC":"BTCUSDT","ETH":"ETHUSDT","SOL":"SOLUSDT"}
INTERVALS=("5m","1h")


def run_batch(*,start_utc:str,end_utc:str,raw_root:Path,output_root:Path,manifest:Path,execute:bool=False)->dict:
    payload=plan(start_utc=start_utc,end_utc=end_utc,raw_root=raw_root,symbols=SYMBOLS,intervals=INTERVALS)
    if not execute:
        result={**payload,"batch_status":"PLANNED_NOT_DOWNLOADED","normalized_outputs":[],"pit_context_complete":False}
    else:
        acquired=acquire(payload)
        outputs=[]
        for symbol in SYMBOLS:
            provider_symbol=PROVIDER[symbol]
            for interval in INTERVALS:
                paths=[Path(obj["local_zip"]) for obj in acquired["objects"] if obj["symbol"]==symbol and obj["interval"]==interval]
                if not paths:raise RuntimeError(f"no acquired archives for {symbol} {interval}")
                output=Path(output_root)/f"{symbol}-{interval}-{start_utc[:10]}_{end_utc[:10]}.csv"
                report=output.with_suffix(output.suffix+".normalization.json")
                normalized=normalize(inputs=paths,provider_symbol=provider_symbol,interval=interval,start_utc=start_utc,end_utc=end_utc,output=output,report=report)
                outputs.append(normalized)
        result={**acquired,"batch_status":"ACQUIRED_AND_NORMALIZED_CANDLES_CONTEXT_STILL_REQUIRED","normalized_outputs":outputs,"pit_context_complete":False}
    manifest=Path(manifest);manifest.parent.mkdir(parents=True,exist_ok=True)
    manifest.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    return result


def main(argv:list[str]|None=None)->int:
    p=argparse.ArgumentParser(description="Acquire/normalize representative Binance public candle window")
    p.add_argument("--start",required=True);p.add_argument("--end",required=True)
    p.add_argument("--raw-root",type=Path,required=True);p.add_argument("--output-root",type=Path,required=True)
    p.add_argument("--manifest",type=Path,required=True);p.add_argument("--execute",action="store_true")
    a=p.parse_args(argv)
    result=run_batch(start_utc=a.start,end_utc=a.end,raw_root=a.raw_root,output_root=a.output_root,manifest=a.manifest,execute=a.execute)
    print(f"batch_manifest={a.manifest}")
    print(f"objects={len(result['objects'])} normalized_outputs={len(result['normalized_outputs'])} status={result['batch_status']}")
    return 0

if __name__=="__main__":raise SystemExit(main())
