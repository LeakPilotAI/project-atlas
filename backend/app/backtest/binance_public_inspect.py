"""Inspect checksum-verified Binance public USD-M futures kline ZIPs.

Research-only. Validates raw CSV shape/cadence before normalization. Does not
create canonical Atlas datasets and does not satisfy PIT OI/rolling-volume gates.
"""
from __future__ import annotations

import argparse,csv,json,zipfile
from dataclasses import dataclass,asdict
from datetime import datetime,timezone
from pathlib import Path

EXPECTED_COLUMNS=12
INTERVAL_MS={"5m":300_000,"1h":3_600_000}

@dataclass(frozen=True)
class Inspection:
    input:str
    provider_symbol:str
    interval:str
    member:str
    row_count:int
    first_open_time:str
    last_open_time:str
    cadence_ms:int
    cadence_consistent:bool
    schema_columns:int
    schema_valid:bool
    ascending_unique:bool
    research_only:bool=True
    pit_oi_context_complete:bool=False
    live_capital_allowed:bool=False
    automatic_real_money_execution:bool=False


def _iso(ms:int)->str:
    return datetime.fromtimestamp(ms/1000,tz=timezone.utc).isoformat().replace("+00:00","Z")


def inspect_zip(path:Path,*,provider_symbol:str,interval:str)->Inspection:
    path=Path(path)
    if interval not in INTERVAL_MS:raise ValueError(f"unsupported interval: {interval}")
    if not path.is_file():raise FileNotFoundError(path)
    with zipfile.ZipFile(path) as zf:
        members=[n for n in zf.namelist() if n.lower().endswith('.csv')]
        if len(members)!=1:raise RuntimeError(f"expected exactly one CSV member, found {len(members)}")
        member=members[0]
        with zf.open(member) as raw:
            text=(line.decode('utf-8-sig').strip() for line in raw)
            rows=list(csv.reader(line for line in text if line))
    if not rows:raise RuntimeError("kline archive CSV is empty")
    if any(len(r)!=EXPECTED_COLUMNS for r in rows):raise RuntimeError("unexpected Binance kline column count")
    try:times=[int(r[0]) for r in rows]
    except Exception as exc:raise RuntimeError("invalid kline open_time") from exc
    if any(t<=0 for t in times):raise RuntimeError("nonpositive kline open_time")
    ascending_unique=all(b>a for a,b in zip(times,times[1:]))
    step=INTERVAL_MS[interval]
    cadence_consistent=ascending_unique and all((b-a)==step for a,b in zip(times,times[1:]))
    return Inspection(
        input=str(path),provider_symbol=provider_symbol,interval=interval,member=member,
        row_count=len(rows),first_open_time=_iso(times[0]),last_open_time=_iso(times[-1]),
        cadence_ms=step,cadence_consistent=cadence_consistent,schema_columns=EXPECTED_COLUMNS,
        schema_valid=True,ascending_unique=ascending_unique,
    )


def main(argv:list[str]|None=None)->int:
    p=argparse.ArgumentParser(description="Inspect raw Binance public USD-M kline ZIP")
    p.add_argument("--input",type=Path,required=True)
    p.add_argument("--provider-symbol",required=True)
    p.add_argument("--interval",required=True,choices=sorted(INTERVAL_MS))
    p.add_argument("--output",type=Path,required=True)
    a=p.parse_args(argv)
    result=inspect_zip(a.input,provider_symbol=a.provider_symbol.upper(),interval=a.interval)
    payload=asdict(result)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(payload,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(f"inspection={a.output}")
    print(f"rows={result.row_count} schema_valid={str(result.schema_valid).lower()} cadence_consistent={str(result.cadence_consistent).lower()} ascending_unique={str(result.ascending_unique).lower()}")
    if not(result.schema_valid and result.cadence_consistent and result.ascending_unique):return 2
    return 0

if __name__=="__main__":raise SystemExit(main())
