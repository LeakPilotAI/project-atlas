"""Assemble canonical PIT historical Atlas datasets for locked research.

Combines funded 5m bars, sparse point-in-time OI, exact trailing-24h quote volume,
and completed-1h HTF trend. Context rows missing any required PIT input are excluded
rather than fabricated. Research only; no current-state backfill or live execution.
"""
from __future__ import annotations

import argparse,csv,json
from hashlib import sha256
from pathlib import Path

from app.backtest.manifest import build_manifest,write_manifest

FIELDS=["timestamp","symbol","timeframe","open","high","low","close","volume","funding_rate","open_interest_usd","volume_24h_usd","htf_trend"]


def _sha256(path:Path)->str:
    h=sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda:fh.read(1024*1024),b""):h.update(chunk)
    return h.hexdigest()


def _read_map(path:Path,value_field:str)->dict[str,str]:
    out={}
    with Path(path).open("r",encoding="utf-8-sig",newline="") as fh:
        for row in csv.DictReader(fh):
            ts=row.get("timestamp");value=row.get(value_field)
            if not ts or value in (None,""):raise RuntimeError(f"{path}: missing timestamp/{value_field}")
            if ts in out:raise RuntimeError(f"{path}: duplicate timestamp {ts}")
            out[ts]=value
    if not out:raise RuntimeError(f"{path}: empty")
    return out


def assemble(*,symbol:str,bars:Path,oi:Path,volume:Path,htf:Path,output:Path,manifest:Path)->dict:
    symbol=symbol.upper()
    oi_map=_read_map(oi,"open_interest_usd")
    vol_map=_read_map(volume,"volume_24h_usd")
    htf_map=_read_map(htf,"htf_trend")
    rows=[];excluded=[]
    with Path(bars).open("r",encoding="utf-8-sig",newline="") as fh:
        for row in csv.DictReader(fh):
            ts=row.get("timestamp")
            if not ts:raise RuntimeError(f"{bars}: missing timestamp")
            missing=[]
            if ts not in oi_map:missing.append("open_interest_usd")
            if ts not in vol_map:missing.append("volume_24h_usd")
            if ts not in htf_map:missing.append("htf_trend")
            if missing:
                excluded.append({"timestamp":ts,"missing":missing});continue
            rows.append({
                "timestamp":ts,"symbol":symbol,"timeframe":row.get("timeframe") or "5m",
                "open":row["open"],"high":row["high"],"low":row["low"],"close":row["close"],"volume":row["volume"],
                "funding_rate":row.get("funding_rate") or "0","open_interest_usd":oi_map[ts],
                "volume_24h_usd":vol_map[ts],"htf_trend":htf_map[ts],
            })
    if not rows:raise RuntimeError("canonical assembly produced no complete PIT rows")
    timestamps=[r["timestamp"] for r in rows]
    if timestamps!=sorted(timestamps) or len(timestamps)!=len(set(timestamps)):raise RuntimeError("canonical timestamps must be unique and ascending")
    output=Path(output);output.parent.mkdir(parents=True,exist_ok=True)
    with output.open("w",encoding="utf-8",newline="") as fh:
        w=csv.DictWriter(fh,fieldnames=FIELDS);w.writeheader();w.writerows(rows)
    raw_checksums={"bars":_sha256(Path(bars)),"oi":_sha256(Path(oi)),"volume":_sha256(Path(volume)),"htf":_sha256(Path(htf))}
    notes=("raw_sha256="+json.dumps(raw_checksums,sort_keys=True,separators=(",",":"))+
           f";missing_context_policy=EXCLUDE_INCOMPLETE_ROWS_NO_FILL;excluded_rows={len(excluded)}")
    m=build_manifest(output,candles_source=str(bars),funding_source=str(bars),oi_source=str(oi),rolling_volume_source=str(volume),htf_context_source=str(htf),pit_aligned=True,current_state_backfill_used=False,notes=notes)
    write_manifest(m,manifest)
    payload={
        "mode":"RESEARCH_ONLY_CANONICAL_PIT_ASSEMBLY","symbol":symbol,"row_count":len(rows),
        "excluded_incomplete_rows":len(excluded),"excluded_timestamps":[x["timestamp"] for x in excluded],
        "missing_context_policy":"EXCLUDE_INCOMPLETE_ROWS_NO_FILL","output":str(output),"output_sha256":_sha256(output),
        "manifest":str(manifest),"raw_source_sha256":raw_checksums,"pit_aligned":True,
        "current_state_backfill_used":False,"live_capital_allowed":False,"automatic_real_money_execution":False,
    }
    return payload


def main(argv:list[str]|None=None)->int:
    p=argparse.ArgumentParser(description="Assemble canonical PIT Atlas historical dataset")
    p.add_argument("--symbol",required=True);p.add_argument("--bars",type=Path,required=True);p.add_argument("--oi",type=Path,required=True)
    p.add_argument("--volume",type=Path,required=True);p.add_argument("--htf",type=Path,required=True);p.add_argument("--output",type=Path,required=True);p.add_argument("--manifest",type=Path,required=True)
    a=p.parse_args(argv);result=assemble(symbol=a.symbol,bars=a.bars,oi=a.oi,volume=a.volume,htf=a.htf,output=a.output,manifest=a.manifest);print(json.dumps(result,indent=2,sort_keys=True));return 0

if __name__=="__main__":raise SystemExit(main())
