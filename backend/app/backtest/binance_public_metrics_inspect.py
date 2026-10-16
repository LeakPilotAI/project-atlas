"""Inspect checksum-verified Binance public USD-M futures metrics ZIPs.

Research-only. Validates real historical metrics schema/cadence before normalization.
Does not create canonical Atlas context or enable live capital.
"""
from __future__ import annotations

import argparse,csv,json,zipfile
from dataclasses import dataclass,asdict
from datetime import datetime,timezone
from pathlib import Path

REQUIRED_COLUMNS={"create_time","symbol","sum_open_interest","sum_open_interest_value"}

@dataclass(frozen=True)
class MetricsInspection:
    input:str
    provider_symbol:str
    member:str
    row_count:int
    first_timestamp:str
    last_timestamp:str
    header_columns:tuple[str,...]
    required_columns_present:bool
    ascending_unique:bool
    cadence_seconds:int|None
    cadence_consistent:bool
    research_only:bool=True
    pit_oi_context_complete:bool=False
    live_capital_allowed:bool=False
    automatic_real_money_execution:bool=False


def _parse_ts(value:str)->datetime:
    text=value.strip()
    dt=datetime.fromisoformat(text.replace("Z","+00:00"))
    if dt.tzinfo is None:dt=dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _iso(dt:datetime)->str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00","Z")


def inspect_zip(path:Path,*,provider_symbol:str)->MetricsInspection:
    path=Path(path)
    if not path.is_file():raise FileNotFoundError(path)
    with zipfile.ZipFile(path) as zf:
        members=[n for n in zf.namelist() if n.lower().endswith('.csv')]
        if len(members)!=1:raise RuntimeError(f"expected exactly one CSV member, found {len(members)}")
        member=members[0]
        with zf.open(member) as raw:
            text=(line.decode('utf-8-sig') for line in raw)
            reader=csv.DictReader(text)
            if not reader.fieldnames:raise RuntimeError("metrics archive missing header")
            headers=tuple(x.strip() for x in reader.fieldnames)
            if not REQUIRED_COLUMNS.issubset(headers):
                missing=sorted(REQUIRED_COLUMNS-set(headers));raise RuntimeError(f"metrics archive missing required columns: {', '.join(missing)}")
            rows=list(reader)
    if not rows:raise RuntimeError("metrics archive has no data rows")
    filtered=[r for r in rows if str(r.get("symbol","")).strip().upper()==provider_symbol.upper()]
    if not filtered:raise RuntimeError(f"metrics archive has no rows for {provider_symbol.upper()}")
    try:times=[_parse_ts(r["create_time"]) for r in filtered]
    except Exception as exc:raise RuntimeError("invalid metrics create_time") from exc
    ascending_unique=all(b>a for a,b in zip(times,times[1:]))
    deltas=[int((b-a).total_seconds()) for a,b in zip(times,times[1:])]
    cadence_seconds=deltas[0] if deltas and len(set(deltas))==1 else None
    cadence_consistent=ascending_unique and (cadence_seconds is not None or len(times)==1)
    for row in filtered:
        try:
            oi=float(row["sum_open_interest"]);oi_value=float(row["sum_open_interest_value"])
        except Exception as exc:raise RuntimeError("invalid metrics OI values") from exc
        if oi<0 or oi_value<0:raise RuntimeError("negative metrics OI value")
    return MetricsInspection(
        input=str(path),provider_symbol=provider_symbol.upper(),member=member,row_count=len(filtered),
        first_timestamp=_iso(times[0]),last_timestamp=_iso(times[-1]),header_columns=headers,
        required_columns_present=True,ascending_unique=ascending_unique,cadence_seconds=cadence_seconds,
        cadence_consistent=cadence_consistent,
    )


def main(argv:list[str]|None=None)->int:
    p=argparse.ArgumentParser(description="Inspect Binance public futures metrics ZIP")
    p.add_argument("--input",type=Path,required=True);p.add_argument("--provider-symbol",required=True);p.add_argument("--output",type=Path,required=True)
    a=p.parse_args(argv);result=inspect_zip(a.input,provider_symbol=a.provider_symbol)
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(asdict(result),indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(f"inspection={a.output}")
    print(f"rows={result.row_count} required_columns_present={str(result.required_columns_present).lower()} ascending_unique={str(result.ascending_unique).lower()} cadence_seconds={result.cadence_seconds} cadence_consistent={str(result.cadence_consistent).lower()}")
    return 0 if result.required_columns_present and result.ascending_unique and result.cadence_consistent else 2

if __name__=="__main__":raise SystemExit(main())
