"""Batch canonical PIT assembly for BTC/ETH/SOL locked historical research."""
from __future__ import annotations

import argparse,json
from pathlib import Path

from app.backtest.canonical_assemble import assemble

SYMBOLS=("BTC","ETH","SOL")


def run(*,funded_root:Path,oi_root:Path,volume_root:Path,htf_root:Path,output_root:Path,manifest_path:Path,start:str,end:str)->dict:
    outputs=[]
    for symbol in SYMBOLS:
        bars=Path(funded_root)/f"{symbol}-5m-funded.csv"
        oi=Path(oi_root)/f"{symbol}-oi-5m.csv"
        volume=Path(volume_root)/f"{symbol}-volume24h-5m.csv"
        htf=Path(htf_root)/f"{symbol}-htf-5m.csv"
        missing=[str(p) for p in (bars,oi,volume,htf) if not p.is_file()]
        if missing:raise FileNotFoundError("canonical batch missing source artifact(s): "+", ".join(missing))
        output=Path(output_root)/f"{symbol}-5m.csv";manifest=output.with_suffix(output.suffix+".manifest.json")
        result=assemble(symbol=symbol,bars=bars,oi=oi,volume=volume,htf=htf,output=output,manifest=manifest)
        outputs.append(result)
    payload={"mode":"RESEARCH_ONLY_CANONICAL_PIT_BATCH","start_utc":start,"end_utc":end,"normalized_outputs":len(outputs),"outputs":outputs,"status":"ASSEMBLED_CANONICAL_PIT_DATASETS","live_capital_allowed":False,"automatic_real_money_execution":False}
    manifest_path=Path(manifest_path);manifest_path.parent.mkdir(parents=True,exist_ok=True);manifest_path.write_text(json.dumps(payload,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    return payload


def main(argv:list[str]|None=None)->int:
    p=argparse.ArgumentParser(description="Assemble canonical BTC/ETH/SOL PIT datasets")
    p.add_argument("--funded-root",type=Path,required=True);p.add_argument("--oi-root",type=Path,required=True);p.add_argument("--volume-root",type=Path,required=True);p.add_argument("--htf-root",type=Path,required=True);p.add_argument("--output-root",type=Path,required=True);p.add_argument("--manifest",type=Path,required=True);p.add_argument("--start",required=True);p.add_argument("--end",required=True)
    a=p.parse_args(argv);r=run(funded_root=a.funded_root,oi_root=a.oi_root,volume_root=a.volume_root,htf_root=a.htf_root,output_root=a.output_root,manifest_path=a.manifest,start=a.start,end=a.end)
    print(f"canonical_batch_manifest={a.manifest}");print(f"normalized_outputs={r['normalized_outputs']} status={r['status']}")
    for item in r["outputs"]:print(f"{item['symbol']} rows={item['row_count']} excluded_incomplete_rows={item['excluded_incomplete_rows']}")
    return 0

if __name__=="__main__":raise SystemExit(main())
