"""Batch completed-1h HTF derivation for locked BTC/ETH/SOL historical windows.

Research-only. Consumes normalized 5m + 1h candle artifacts and writes one 5m HTF
context artifact per symbol. No current-state backfill and no live unlock.
"""
from __future__ import annotations

import argparse,json
from pathlib import Path

from app.backtest.binance_public_htf_context import derive

SYMBOLS=("BTC","ETH","SOL")


def run(*,candle_root:Path,output_root:Path,start_utc:str,end_utc:str,symbols:tuple[str,...]=SYMBOLS)->dict:
    bad=sorted(set(symbols)-set(SYMBOLS))
    if bad:raise ValueError(f"unsupported symbols: {', '.join(bad)}")
    outputs=[]
    start_date=start_utc[:10];end_date=end_utc[:10]
    for symbol in symbols:
        decision=Path(candle_root)/f"{symbol}-5m-{start_date}_{end_date}.csv"
        hourly=Path(candle_root)/f"{symbol}-1h-{start_date}_{end_date}.csv"
        if not decision.exists():raise FileNotFoundError(f"missing normalized decision candles: {decision}")
        if not hourly.exists():raise FileNotFoundError(f"missing normalized hourly candles: {hourly}")
        output=Path(output_root)/f"{symbol}-htf-5m.csv"
        report=Path(output_root)/f"{symbol}-htf-5m.normalization.json"
        result=derive(decision_candles=decision,hourly_candles=hourly,output=output,report=report)
        outputs.append(result)
    return {
        "mode":"RESEARCH_ONLY_COMPLETED_1H_HTF_BATCH",
        "start_utc":start_utc,"end_utc":end_utc,"symbols":list(symbols),
        "normalized_outputs":outputs,"normalized_output_count":len(outputs),
        "completed_hourly_only":True,"current_state_backfill_used":False,
        "live_capital_allowed":False,"automatic_real_money_execution":False,
        "status":"DERIVED_COMPLETED_1H_HTF_CONTEXT",
    }


def main(argv:list[str]|None=None)->int:
    p=argparse.ArgumentParser(description="Derive completed-1h HTF context batch")
    p.add_argument("--candle-root",type=Path,required=True);p.add_argument("--output-root",type=Path,required=True)
    p.add_argument("--start",required=True);p.add_argument("--end",required=True)
    p.add_argument("--manifest",type=Path,required=True);p.add_argument("--symbols",nargs="+",default=list(SYMBOLS))
    a=p.parse_args(argv)
    result=run(candle_root=a.candle_root,output_root=a.output_root,start_utc=a.start,end_utc=a.end,symbols=tuple(x.upper() for x in a.symbols))
    a.manifest.parent.mkdir(parents=True,exist_ok=True);a.manifest.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(f"htf_batch_manifest={a.manifest}")
    print(f"normalized_outputs={result['normalized_output_count']} status={result['status']}")
    return 0

if __name__=="__main__":raise SystemExit(main())
