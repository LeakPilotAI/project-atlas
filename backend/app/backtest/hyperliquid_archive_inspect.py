"""Inspect acquired Hyperliquid asset_ctxs archive files before normalization.

Fail-closed research utility: raw archive schemas are authoritative. Atlas does not
promote expected/current API field names into historical facts without inspection.
"""
from __future__ import annotations

import argparse,csv,json,shutil,subprocess
from pathlib import Path
from typing import Any

TARGETS=("BTC","ETH","SOL")
OI_FIELDS=("openInterest","open_interest","openInterestUsd","open_interest_usd")
VOL_FIELDS=("dayNtlVlm","day_ntl_vlm","volume24h","volume_24h","volume_24h_usd")
SYMBOL_FIELDS=("coin","symbol","name","asset")
TIME_FIELDS=("time","timestamp","ts","datetime")


def _decompress(path:Path)->str:
    if path.suffix.lower()!=".lz4":return path.read_text(encoding="utf-8",errors="replace")
    exe=shutil.which("lz4")
    if exe is None:raise RuntimeError("lz4 CLI is required to inspect .lz4 archive files")
    p=subprocess.run([exe,"-dc",str(path)],capture_output=True,check=False)
    if p.returncode!=0:raise RuntimeError(f"lz4 decompression failed: {p.stderr.decode(errors='replace').strip()}")
    return p.stdout.decode("utf-8",errors="replace")


def _pick(fields:list[str],candidates:tuple[str,...])->str|None:
    exact={x:x for x in fields};lower={x.lower():x for x in fields}
    for c in candidates:
        if c in exact:return c
        if c.lower() in lower:return lower[c.lower()]
    return None


def inspect_file(path:Path)->dict[str,Any]:
    text=_decompress(Path(path));reader=csv.DictReader(text.splitlines())
    fields=list(reader.fieldnames or [])
    if not fields:raise ValueError("archive CSV has no header")
    symbol_field=_pick(fields,SYMBOL_FIELDS);time_field=_pick(fields,TIME_FIELDS)
    oi_field=_pick(fields,OI_FIELDS);volume_field=_pick(fields,VOL_FIELDS)
    samples={s:[] for s in TARGETS};rows=0
    for row in reader:
        rows+=1
        if symbol_field:
            symbol=str(row.get(symbol_field) or "").upper()
            if symbol in samples and len(samples[symbol])<3:
                samples[symbol].append({k:row.get(k) for k in fields})
    target_counts={k:len(v) for k,v in samples.items()}
    return {
        "mode":"RESEARCH_ONLY_ARCHIVE_SCHEMA_INSPECTION",
        "path":str(path),"header":fields,"rows_scanned":rows,
        "detected":{"symbol":symbol_field,"timestamp":time_field,"open_interest":oi_field,"day_notional_volume":volume_field},
        "target_sample_counts":target_counts,
        "pit_context_candidate":bool(symbol_field and time_field and oi_field and volume_field and all(target_counts.values())),
        "normalization_allowed":bool(symbol_field and time_field and oi_field and volume_field and all(target_counts.values())),
        "live_capital_allowed":False,"automatic_real_money_execution":False,
        "samples":samples,
    }


def main(argv:list[str]|None=None)->int:
    p=argparse.ArgumentParser(description="Inspect raw Hyperliquid asset_ctxs archive schema")
    p.add_argument("--input",type=Path,required=True);p.add_argument("--output",type=Path,required=True)
    a=p.parse_args(argv);payload=inspect_file(a.input)
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(payload,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(f"inspection={a.output}");print(f"pit_context_candidate={str(payload['pit_context_candidate']).lower()} detected={payload['detected']}")
    return 0

if __name__=="__main__":raise SystemExit(main())
