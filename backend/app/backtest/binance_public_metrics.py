"""Acquire Binance public daily USD-M futures metrics for historical PIT context research.

Research-only. The public metrics ZIPs contain timestamped historical open interest
and related ratios. Atlas uses only point-in-time fields and never substitutes current
state. This module does not by itself make canonical source readiness GREEN.
"""
from __future__ import annotations

import argparse,csv,hashlib,json,time,urllib.error,urllib.request,zipfile
from datetime import date,datetime,timedelta,timezone
from pathlib import Path

BASE_URL="https://data.binance.vision/data/futures/um/daily/metrics"
SYMBOL_MAP={"BTC":"BTCUSDT","ETH":"ETHUSDT","SOL":"SOLUSDT"}


def _date(value:str)->date:
    dt=datetime.fromisoformat(value.replace("Z","+00:00"))
    if dt.tzinfo is None:dt=dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).date()


def _days(start_utc:str,end_utc:str)->list[date]:
    start,end=_date(start_utc),_date(end_utc)
    if start>=end:raise ValueError("start must precede end")
    out=[];cur=start
    while cur<end:out.append(cur);cur+=timedelta(days=1)
    return out


def _sha256(path:Path)->str:
    h=hashlib.sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda:fh.read(1024*1024),b""):h.update(chunk)
    return h.hexdigest()


def _download(url:str,path:Path,*,timeout:int=20,retries:int=3)->None:
    path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_suffix(path.suffix+".part")
    last=None
    for attempt in range(1,retries+1):
        try:
            with urllib.request.urlopen(url,timeout=timeout) as response,tmp.open("wb") as fh:
                while True:
                    chunk=response.read(1024*1024)
                    if not chunk:break
                    fh.write(chunk)
            tmp.replace(path);return
        except Exception as exc:
            last=exc;tmp.unlink(missing_ok=True)
            if attempt<retries:time.sleep(min(2**(attempt-1),4))
    assert last is not None
    raise last


def _published_sha256(path:Path)->str:
    text=path.read_text(encoding="utf-8").strip();token=text.split()[0].lower() if text else ""
    if len(token)!=64 or any(c not in "0123456789abcdef" for c in token):raise RuntimeError(f"invalid published checksum: {path}")
    return token


def _already_verified(zp:Path,cp:Path)->tuple[bool,str|None]:
    if not(zp.is_file() and cp.is_file()):return False,None
    try:
        published=_published_sha256(cp);actual=_sha256(zp)
    except Exception:return False,None
    return published==actual,actual


def plan(*,start_utc:str,end_utc:str,raw_root:Path,symbols:tuple[str,...] = ("BTC","ETH","SOL"))->dict:
    bad=sorted(set(symbols)-set(SYMBOL_MAP))
    if bad:raise ValueError(f"unsupported representative symbols: {', '.join(bad)}")
    objects=[]
    for symbol in symbols:
        ps=SYMBOL_MAP[symbol]
        for d in _days(start_utc,end_utc):
            filename=f"{ps}-metrics-{d:%Y-%m-%d}.zip";url=f"{BASE_URL}/{ps}/{filename}"
            local=Path(raw_root)/"binance_public_metrics"/ps
            objects.append({"symbol":symbol,"provider_symbol":ps,"date":f"{d:%Y-%m-%d}","url":url,"checksum_url":url+".CHECKSUM","local_zip":str(local/filename),"local_checksum":str(local/(filename+".CHECKSUM"))})
    return {"mode":"RESEARCH_ONLY_PUBLIC_METRICS_ACQUISITION","source":"binance:data.binance.vision:futures_um_daily_metrics","start_utc":start_utc,"end_utc":end_utc,"objects":objects,"pit_context_complete":False,"current_state_backfill_allowed":False,"live_capital_allowed":False,"automatic_real_money_execution":False}


def acquire(payload:dict)->dict:
    results=[];total=len(payload["objects"])
    for idx,obj in enumerate(payload["objects"],1):
        zp,cp=Path(obj["local_zip"]),Path(obj["local_checksum"])
        verified,actual=_already_verified(zp,cp)
        if verified:
            pub=_published_sha256(cp)
            status="ALREADY_ACQUIRED_CHECKSUM_VERIFIED"
            print(f"[{idx}/{total}] {obj['provider_symbol']} {obj['date']} skip verified",flush=True)
        else:
            print(f"[{idx}/{total}] {obj['provider_symbol']} {obj['date']} download",flush=True)
            try:
                _download(obj["checksum_url"],cp);_download(obj["url"],zp)
            except urllib.error.HTTPError as exc:
                raise RuntimeError(f"public metrics acquisition failed for {obj['provider_symbol']} {obj['date']}: HTTP {exc.code}") from exc
            except Exception as exc:
                raise RuntimeError(f"public metrics acquisition failed for {obj['provider_symbol']} {obj['date']}: {type(exc).__name__}: {exc}") from exc
            pub,actual=_published_sha256(cp),_sha256(zp)
            if pub!=actual:raise RuntimeError(f"checksum mismatch for {zp}: published={pub} actual={actual}")
            status="ACQUIRED_CHECKSUM_VERIFIED"
        results.append({**obj,"bytes":zp.stat().st_size,"sha256":actual,"published_sha256":pub,"status":status})
    return {**payload,"objects":results,"acquisition_status":"ACQUIRED_RAW_METRICS_CHECKSUM_VERIFIED"}


def inspect_metrics_zip(path:Path)->dict:
    with zipfile.ZipFile(path) as zf:
        members=[n for n in zf.namelist() if n.lower().endswith('.csv')]
        if len(members)!=1:raise RuntimeError(f"expected exactly one metrics CSV member, found {len(members)}")
        with zf.open(members[0]) as raw:
            rows=list(csv.DictReader(line.decode("utf-8-sig") for line in raw))
            fields=list(rows[0].keys()) if rows else []
    if not rows:raise RuntimeError("metrics archive CSV is empty")
    required={"create_time","symbol","sum_open_interest","sum_open_interest_value"}
    missing=sorted(required-set(fields))
    if missing:raise RuntimeError(f"metrics schema missing required columns: {', '.join(missing)}")
    return {"rows":len(rows),"fields":fields,"has_open_interest":True,"source_sha256":_sha256(path),"pit_context_complete":False}


def main(argv:list[str]|None=None)->int:
    p=argparse.ArgumentParser(description="Plan/acquire Binance public historical futures metrics")
    p.add_argument("--start",required=True);p.add_argument("--end",required=True)
    p.add_argument("--raw-root",type=Path,default=Path("backend/data/research/raw/historical"));p.add_argument("--manifest",type=Path,required=True)
    p.add_argument("--symbols",nargs="+",default=["BTC","ETH","SOL"]);p.add_argument("--execute",action="store_true")
    a=p.parse_args(argv);payload=plan(start_utc=a.start,end_utc=a.end,raw_root=a.raw_root,symbols=tuple(x.upper() for x in a.symbols))
    payload=acquire(payload) if a.execute else {**payload,"acquisition_status":"PLANNED_NOT_DOWNLOADED"}
    a.manifest.parent.mkdir(parents=True,exist_ok=True);a.manifest.write_text(json.dumps(payload,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(f"metrics_manifest={a.manifest}");print(f"objects={len(payload['objects'])} status={payload['acquisition_status']}");return 0

if __name__=="__main__":raise SystemExit(main())
