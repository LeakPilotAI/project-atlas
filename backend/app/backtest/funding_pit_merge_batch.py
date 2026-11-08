"""Batch exact first-party funding PIT merge for locked BTC/ETH/SOL 5m research bars."""
from __future__ import annotations

import argparse,json
from pathlib import Path

from app.backtest.funding_pit_merge import merge

SYMBOLS=("BTC","ETH","SOL")


def run_batch(*,bars_root:Path,funding_root:Path,output_root:Path,start_utc:str,end_utc:str,manifest:Path)->dict:
    outputs=[]
    for symbol in SYMBOLS:
        bars=Path(bars_root)/f"{symbol}-5m-{start_utc[:10]}_{end_utc[:10]}.csv"
        funding=Path(funding_root)/f"{symbol}-funding.csv"
        if not bars.exists():raise RuntimeError(f"missing bars source: {bars}")
        if not funding.exists():raise RuntimeError(f"missing funding source: {funding}")
        output=Path(output_root)/f"{symbol}-5m-funded.csv"
        report=output.with_suffix(output.suffix+".normalization.json")
        result=merge(bars_path=bars,funding_path=funding,output=output,report=report)
        outputs.append({"symbol":symbol,**result})
    payload={
        "mode":"RESEARCH_ONLY_BATCH_EXACT_EVENT_FUNDING_PIT_MERGE",
        "start_utc":start_utc,"end_utc":end_utc,
        "normalized_outputs":outputs,"status":"MERGED_FIRST_PARTY_FUNDING_INTO_5M_BARS",
        "interpolation_used":False,"forward_fill_used":False,"current_state_backfill_used":False,
        "live_capital_allowed":False,"automatic_real_money_execution":False,
    }
    manifest=Path(manifest);manifest.parent.mkdir(parents=True,exist_ok=True);manifest.write_text(json.dumps(payload,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    return payload


def main(argv:list[str]|None=None)->int:
    p=argparse.ArgumentParser(description="Batch exact funding PIT merge for BTC/ETH/SOL")
    p.add_argument("--bars-root",type=Path,required=True);p.add_argument("--funding-root",type=Path,required=True);p.add_argument("--output-root",type=Path,required=True)
    p.add_argument("--start",required=True);p.add_argument("--end",required=True);p.add_argument("--manifest",type=Path,required=True)
    a=p.parse_args(argv);r=run_batch(bars_root=a.bars_root,funding_root=a.funding_root,output_root=a.output_root,start_utc=a.start,end_utc=a.end,manifest=a.manifest)
    print(f"funding_merge_batch_manifest={a.manifest}")
    print(f"normalized_outputs={len(r['normalized_outputs'])} status={r['status']}")
    for item in r["normalized_outputs"]:print(f"{item['symbol']} bars={item['bar_count']} funding_events_merged={item['funding_events_merged']}")
    return 0

if __name__=="__main__":raise SystemExit(main())
