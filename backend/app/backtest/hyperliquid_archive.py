"""Plan/acquire Hyperliquid requester-pays historical asset contexts.

Research-only. The official archive path is documented as
s3://hyperliquid-archive/asset_ctxs/YYYYMMDD.csv.lz4. This module deliberately
uses the local AWS CLI credential chain and never accepts AWS secrets as CLI args.
It can plan without network access; acquisition requires configured AWS credentials.
"""
from __future__ import annotations

import argparse,hashlib,json,shutil,subprocess
from dataclasses import asdict,dataclass
from datetime import date,datetime,timedelta,timezone
from pathlib import Path

BUCKET="hyperliquid-archive"
PREFIX="asset_ctxs"


def _date(value:str)->date:
    d=datetime.fromisoformat(value.replace("Z","+00:00"))
    if d.tzinfo is None:d=d.replace(tzinfo=timezone.utc)
    return d.astimezone(timezone.utc).date()


def _days(start_utc:str,end_utc:str)->list[date]:
    start=_date(start_utc);end=_date(end_utc)
    if start>=end:raise ValueError("start must precede end")
    out=[];cur=start
    while cur<end:out.append(cur);cur+=timedelta(days=1)
    return out


def archive_uri(day:date)->str:
    return f"s3://{BUCKET}/{PREFIX}/{day:%Y%m%d}.csv.lz4"


@dataclass(frozen=True)
class ArchiveObject:
    day:str
    uri:str
    local_path:str


def plan(*,start_utc:str,end_utc:str,raw_root:Path)->dict:
    objects=[]
    for day in _days(start_utc,end_utc):
        local=raw_root/"asset_ctxs"/f"{day:%Y%m%d}.csv.lz4"
        objects.append(ArchiveObject(day.isoformat(),archive_uri(day),str(local)))
    return {
        "mode":"RESEARCH_ONLY_HYPERLIQUID_ARCHIVE_ASSET_CTXS",
        "source":"hyperliquid:first_party_requester_pays_s3",
        "bucket":BUCKET,"prefix":PREFIX,"start_utc":start_utc,"end_utc":end_utc,
        "request_payer":"requester","credential_policy":"AWS CLI credential chain only; no secrets accepted by Atlas CLI",
        "expected_context_fields":["openInterest","dayNtlVlm","markPx","oraclePx","midPx","premium"],
        "schema_status":"MUST_INSPECT_ACQUIRED_RAW_HEADER_BEFORE_NORMALIZATION",
        "live_capital_allowed":False,"automatic_real_money_execution":False,"current_state_backfill_allowed":False,
        "objects":[asdict(x) for x in objects],
    }


def _sha256(path:Path)->str:
    h=hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda:f.read(1024*1024),b""):h.update(chunk)
    return h.hexdigest()


def acquire(payload:dict,*,aws_profile:str|None=None)->dict:
    if shutil.which("aws") is None:raise RuntimeError("AWS CLI is required for requester-pays archive acquisition")
    results=[]
    for obj in payload["objects"]:
        path=Path(obj["local_path"]);path.parent.mkdir(parents=True,exist_ok=True)
        cmd=["aws","s3","cp",obj["uri"],str(path),"--request-payer","requester","--only-show-errors"]
        if aws_profile:cmd.extend(["--profile",aws_profile])
        proc=subprocess.run(cmd,capture_output=True,text=True,check=False)
        if proc.returncode!=0:
            raise RuntimeError(f"archive acquisition failed for {obj['day']}: {proc.stderr.strip() or proc.stdout.strip()}")
        results.append({**obj,"bytes":path.stat().st_size,"sha256":_sha256(path),"status":"ACQUIRED"})
    return {**payload,"objects":results,"acquisition_status":"ACQUIRED_RAW_SCHEMA_INSPECTION_REQUIRED"}


def main(argv:list[str]|None=None)->int:
    p=argparse.ArgumentParser(description="Plan/acquire official Hyperliquid requester-pays asset_ctxs history")
    p.add_argument("--start",required=True);p.add_argument("--end",required=True)
    p.add_argument("--raw-root",type=Path,default=Path("backend/data/research/raw/historical"))
    p.add_argument("--manifest",type=Path,default=Path("backend/data/research/historical/hyperliquid-asset-ctxs.json"))
    p.add_argument("--execute",action="store_true",help="actually download requester-pays objects")
    p.add_argument("--aws-profile",default=None,help="optional existing AWS profile name; never pass secrets here")
    a=p.parse_args(argv)
    payload=plan(start_utc=a.start,end_utc=a.end,raw_root=a.raw_root)
    if a.execute:payload=acquire(payload,aws_profile=a.aws_profile)
    else:payload["acquisition_status"]="PLANNED_NOT_DOWNLOADED"
    a.manifest.parent.mkdir(parents=True,exist_ok=True);a.manifest.write_text(json.dumps(payload,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(f"archive_manifest={a.manifest}");print(f"objects={len(payload['objects'])} status={payload['acquisition_status']}")
    return 0

if __name__=="__main__":raise SystemExit(main())
