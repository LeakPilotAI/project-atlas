"""Acquire first-party Hyperliquid historical funding for BTC/ETH/SOL.

Research-only orchestration around hyperliquid_funding_history.acquire. Preserves exact
event timestamps/rates and per-symbol provenance. No interpolation/current-state backfill.
"""
from __future__ import annotations

import argparse,json
from pathlib import Path

from app.backtest.hyperliquid_funding_history import acquire

SYMBOLS=("BTC","ETH","SOL")


def run_batch(*,start_utc:str,end_utc:str,output_root:Path,manifest:Path)->dict:
    outputs=[]
    for symbol in SYMBOLS:
        output=Path(output_root)/f"{symbol}-funding.csv"
        report=output.with_suffix(output.suffix+".normalization.json")
        result=acquire(symbol=symbol,start_utc=start_utc,end_utc=end_utc,output=output,report=report)
        outputs.append(result)
    payload={
        "mode":"RESEARCH_ONLY_HYPERLIQUID_FUNDING_BATCH",
        "start_utc":start_utc,"end_utc":end_utc,
        "symbols":list(SYMBOLS),"normalized_outputs":outputs,
        "status":"ACQUIRED_FIRST_PARTY_FUNDING",
        "exact_event_timestamps":True,"interpolation_used":False,"current_state_backfill_used":False,
        "live_capital_allowed":False,"automatic_real_money_execution":False,
    }
    manifest=Path(manifest);manifest.parent.mkdir(parents=True,exist_ok=True)
    manifest.write_text(json.dumps(payload,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    return payload


def main(argv:list[str]|None=None)->int:
    p=argparse.ArgumentParser(description="Acquire first-party Hyperliquid funding batch")
    p.add_argument("--start",required=True);p.add_argument("--end",required=True)
    p.add_argument("--output-root",type=Path,required=True);p.add_argument("--manifest",type=Path,required=True)
    a=p.parse_args(argv);result=run_batch(start_utc=a.start,end_utc=a.end,output_root=a.output_root,manifest=a.manifest)
    print(f"funding_batch_manifest={a.manifest}")
    print(f"normalized_outputs={len(result['normalized_outputs'])} status={result['status']}")
    for row in result["normalized_outputs"]:
        print(f"{row['symbol']} rows={row['row_count']} pages={row['page_count']} first={row['first_timestamp']} last={row['last_timestamp']}")
    return 0

if __name__=="__main__":raise SystemExit(main())
