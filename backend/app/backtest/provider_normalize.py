"""Provider-neutral normalization for historical OI/rolling-volume/HTF context.

This module converts timestamped provider exports into Atlas PIT context files.
It never calls current-state market endpoints and never fabricates historical OI.
"""
from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import datetime,timezone
from pathlib import Path
from typing import Any,Iterable


def _iso(value:Any)->str:
    if isinstance(value,(int,float)) or (isinstance(value,str) and value.strip().isdigit()):
        n=int(value)
        if n<10_000_000_000:n*=1000
        return datetime.fromtimestamp(n/1000,tz=timezone.utc).isoformat().replace("+00:00","Z")
    text=str(value).strip()
    if text.endswith("Z"):return text
    try:return datetime.fromisoformat(text.replace("Z","+00:00")).astimezone(timezone.utc).isoformat().replace("+00:00","Z")
    except ValueError as exc:raise ValueError(f"invalid timestamp: {value!r}") from exc


def _read(path:Path)->list[dict[str,Any]]:
    path=Path(path);suffix=path.suffix.lower()
    if suffix==".csv":
        with path.open("r",encoding="utf-8-sig",newline="") as fh:return list(csv.DictReader(fh))
    if suffix in {".jsonl",".ndjson"}:
        out=[]
        for n,line in enumerate(path.read_text(encoding="utf-8").splitlines(),1):
            if not line.strip():continue
            value=json.loads(line)
            if not isinstance(value,dict):raise ValueError(f"{path}:{n}: row must be object")
            out.append(value)
        return out
    if suffix==".json":
        value=json.loads(path.read_text(encoding="utf-8"))
        if isinstance(value,dict):
            for key in ("data","rows","result","results","items"):
                if isinstance(value.get(key),list):value=value[key];break
        if not isinstance(value,list) or not all(isinstance(x,dict) for x in value):raise ValueError(f"{path}: JSON must contain an array of objects")
        return value
    raise ValueError(f"unsupported provider export format: {suffix}")


def _first(row:dict[str,Any],names:Iterable[str],required:bool=True)->Any:
    for name in names:
        if name in row and row[name] not in (None,""):return row[name]
    if required:raise ValueError(f"provider row missing one of: {', '.join(names)}")
    return None


def normalize_oi_export(path:Path)->dict[str,float]:
    out={}
    for row in _read(path):
        ts=_iso(_first(row,("timestamp","time","ts","t")))
        value=float(_first(row,("open_interest_usd","openInterestUsd","open_interest_quote","oi_usd","notional","openInterest")))
        if value<0:raise ValueError(f"negative OI at {ts}")
        if ts in out:raise ValueError(f"duplicate OI timestamp: {ts}")
        out[ts]=value
    if not out:raise ValueError("OI export is empty")
    return out


def normalize_volume_export(path:Path)->dict[str,float]:
    out={}
    for row in _read(path):
        ts=_iso(_first(row,("timestamp","time","ts","t")))
        value=float(_first(row,("volume_24h_usd","volume24hUsd","dayNtlVlm","rolling_volume_usd","volume_usd","notional_volume")))
        if value<0:raise ValueError(f"negative rolling volume at {ts}")
        if ts in out:raise ValueError(f"duplicate volume timestamp: {ts}")
        out[ts]=value
    if not out:raise ValueError("volume export is empty")
    return out


def _bool(value:Any)->bool:
    if isinstance(value,bool):return value
    text=str(value).strip().lower()
    if text in {"1","true","yes","aligned"}:return True
    if text in {"0","false","no","blocked","misaligned"}:return False
    raise ValueError(f"invalid HTF alignment value: {value!r}")


def normalize_htf_export(path:Path)->dict[str,bool]:
    out={}
    for row in _read(path):
        ts=_iso(_first(row,("timestamp","time","ts","t")))
        value=_bool(_first(row,("htf_regime_aligned","aligned","htf_aligned")))
        if ts in out:raise ValueError(f"duplicate HTF timestamp: {ts}")
        out[ts]=value
    if not out:raise ValueError("HTF export is empty")
    return out


def merge_context_exports(*,oi_path:Path,volume_path:Path,htf_path:Path,output_path:Path)->Path:
    oi=normalize_oi_export(oi_path);vol=normalize_volume_export(volume_path);htf=normalize_htf_export(htf_path)
    timestamps=sorted(set(oi)&set(vol)&set(htf))
    missing=(set(oi)|set(vol)|set(htf))-set(timestamps)
    if missing:raise ValueError(f"provider context timestamps are not perfectly aligned; unmatched={len(missing)}")
    if not timestamps:raise ValueError("provider exports have no shared timestamps")
    output_path=Path(output_path);output_path.parent.mkdir(parents=True,exist_ok=True)
    fields=["timestamp","open_interest_usd","volume_24h_usd","htf_regime_aligned"]
    with output_path.open("w",encoding="utf-8",newline="") as fh:
        w=csv.DictWriter(fh,fieldnames=fields);w.writeheader()
        for ts in timestamps:w.writerow({"timestamp":ts,"open_interest_usd":oi[ts],"volume_24h_usd":vol[ts],"htf_regime_aligned":str(htf[ts]).lower()})
    return output_path
