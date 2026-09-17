"""Operator CLI for PIT-safe Atlas historical dataset imports.

Raw source files are local research inputs. This command never queries current market
state to fill historical OI/volume/HTF fields. It emits a canonical CSV and provenance
manifest together or fails closed.
"""
from __future__ import annotations

import argparse
import csv
from hashlib import sha256
import json
from pathlib import Path
from typing import Any

from app.backtest.hyperliquid_import import HistoricalMarketContext,normalize_hyperliquid_history,write_canonical_csv
from app.backtest.manifest import build_manifest,write_manifest


def _sha(path:Path)->str:
    h=sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda:fh.read(1024*1024),b""):h.update(chunk)
    return h.hexdigest()


def _rows(path:Path)->list[dict[str,Any]]:
    suffix=path.suffix.lower()
    if suffix==".csv":
        with path.open("r",encoding="utf-8-sig",newline="") as fh:return list(csv.DictReader(fh))
    if suffix in {".jsonl",".ndjson"}:
        out=[]
        for n,line in enumerate(path.read_text(encoding="utf-8").splitlines(),1):
            if not line.strip():continue
            value=json.loads(line)
            if not isinstance(value,dict):raise ValueError(f"{path}: line {n} must be an object")
            out.append(value)
        return out
    if suffix==".json":
        value=json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value,list) or not all(isinstance(x,dict) for x in value):raise ValueError(f"{path}: JSON must be an array of objects")
        return value
    raise ValueError(f"unsupported raw source format: {path.suffix}")


def _bool(value:Any)->bool:
    text=str(value).strip().lower()
    if text in {"1","true","yes"}:return True
    if text in {"0","false","no"}:return False
    raise ValueError(f"invalid HTF alignment boolean: {value!r}")


def _context(path:Path)->list[HistoricalMarketContext]:
    out=[]
    for row in _rows(path):
        missing=[k for k in ("timestamp","open_interest_usd","volume_24h_usd","htf_regime_aligned") if row.get(k) in (None,"")]
        if missing:raise ValueError(f"historical context missing fields: {', '.join(missing)}")
        out.append(HistoricalMarketContext(str(row["timestamp"]),float(row["open_interest_usd"]),float(row["volume_24h_usd"]),_bool(row["htf_regime_aligned"])))
    return out


def _candles(path:Path)->list[dict[str,Any]]:
    out=[]
    for row in _rows(path):
        time_value=row.get("time",row.get("t"))
        if time_value in (None,""):raise ValueError("candle source missing time/t")
        out.append({"time":int(time_value),"open":float(row["open"]),"high":float(row["high"]),"low":float(row["low"]),"close":float(row["close"]),"volume":float(row["volume"])})
    return out


def _funding(path:Path)->list[dict[str,Any]]:
    out=[]
    for row in _rows(path):
        time_value=row.get("time")
        rate=row.get("funding_rate",row.get("fundingRate"))
        if time_value in (None,"") or rate in (None,""):raise ValueError("funding source requires time and funding_rate/fundingRate")
        out.append({"time":int(time_value),"funding_rate":float(rate)})
    return out


def import_dataset(*,symbol:str,timeframe:str,candles_path:Path,funding_path:Path,context_path:Path,output_path:Path,candles_source:str,funding_source:str,oi_source:str,rolling_volume_source:str,htf_context_source:str,notes:str="")->tuple[Path,Path]:
    for path in (candles_path,funding_path,context_path):
        if not Path(path).is_file():raise ValueError(f"raw source file not found: {path}")
    rows=normalize_hyperliquid_history(symbol=symbol,timeframe=timeframe,candles=_candles(Path(candles_path)),funding_history=_funding(Path(funding_path)),historical_context=_context(Path(context_path)))
    dataset=write_canonical_csv(rows,Path(output_path))
    raw_hashes={"candles":_sha(Path(candles_path)),"funding":_sha(Path(funding_path)),"context":_sha(Path(context_path))}
    note=(notes.strip()+" | " if notes.strip() else "")+"raw_sha256="+json.dumps(raw_hashes,sort_keys=True,separators=(",",":"))
    manifest=build_manifest(dataset,candles_source=candles_source,funding_source=funding_source,oi_source=oi_source,rolling_volume_source=rolling_volume_source,htf_context_source=htf_context_source,pit_aligned=True,current_state_backfill_used=False,notes=note)
    manifest_path=dataset.with_suffix(dataset.suffix+".manifest.json")
    write_manifest(manifest,manifest_path)
    return dataset,manifest_path


def main(argv:list[str]|None=None)->int:
    p=argparse.ArgumentParser(description="Normalize PIT-safe historical source files into Atlas canonical backtest data")
    p.add_argument("--symbol",required=True);p.add_argument("--timeframe",required=True)
    p.add_argument("--candles",type=Path,required=True);p.add_argument("--funding",type=Path,required=True);p.add_argument("--context",type=Path,required=True);p.add_argument("--output",type=Path,required=True)
    p.add_argument("--candles-source",required=True);p.add_argument("--funding-source",required=True);p.add_argument("--oi-source",required=True);p.add_argument("--rolling-volume-source",required=True);p.add_argument("--htf-context-source",required=True);p.add_argument("--notes",default="")
    a=p.parse_args(argv)
    dataset,manifest=import_dataset(symbol=a.symbol,timeframe=a.timeframe,candles_path=a.candles,funding_path=a.funding,context_path=a.context,output_path=a.output,candles_source=a.candles_source,funding_source=a.funding_source,oi_source=a.oi_source,rolling_volume_source=a.rolling_volume_source,htf_context_source=a.htf_context_source,notes=a.notes)
    print(f"dataset={dataset}");print(f"manifest={manifest}");return 0


if __name__=="__main__":raise SystemExit(main())
