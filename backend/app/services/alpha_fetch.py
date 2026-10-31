"""Execution 33 bounded governed-source fetch adapters."""
from __future__ import annotations
from datetime import datetime,timezone
import json, os, time
from pathlib import Path
from typing import Any,Callable
from urllib.parse import urlparse
import httpx
from app.services.alpha_ingestion import SOURCE_REGISTRY, DATA_DIR, ingest

FETCH_LOG=DATA_DIR/"alpha_fetch_telemetry.jsonl"
MAX_BYTES=512_000
TIMEOUT_SECONDS=8.0
COOLDOWN_SECONDS=300
ALLOWED_TYPES=("text/html","application/xml","text/xml","application/rss+xml","application/atom+xml","application/json")
FETCH_TARGETS={
 "federal_reserve":"https://www.federalreserve.gov/newsevents/pressreleases.htm",
 "sec":"https://www.sec.gov/newsroom/press-releases",
 "hyperliquid_docs":"https://hyperliquid.gitbook.io/hyperliquid-docs/",
}

def _append(path:Path,row:dict[str,Any]):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("a",encoding="utf-8",newline="\n") as f:
        f.write(json.dumps(row,sort_keys=True,ensure_ascii=False)+"\n"); f.flush(); os.fsync(f.fileno())

def _last_success(source_id:str,path:Path)->datetime|None:
    if not path.exists():return None
    for line in reversed(path.read_text(encoding="utf-8").splitlines()):
        try:r=json.loads(line)
        except Exception:continue
        if r.get("source_id")==source_id and r.get("outcome")=="FETCHED":
            try:return datetime.fromisoformat(r["finished_at"])
            except Exception:return None
    return None

def _validate_target(source_id:str,url:str):
    source=SOURCE_REGISTRY.get(source_id)
    if source is None:raise ValueError("source_id is not governed")
    if FETCH_TARGETS.get(source_id)!=url:raise ValueError("url is not the frozen fetch target")
    if (urlparse(url).hostname or "").lower()!=source.domain.lower():raise ValueError("fetch target domain mismatch")

def fetch_once(source_id:str,*,telemetry_path:Path=FETCH_LOG,now:datetime|None=None,
               transport:httpx.BaseTransport|None=None,include_body:bool=False)->dict[str,Any]:
    now=(now or datetime.now(timezone.utc)).astimezone(timezone.utc); url=FETCH_TARGETS[source_id]
    _validate_target(source_id,url)
    last=_last_success(source_id,telemetry_path)
    if last and (now-last).total_seconds()<COOLDOWN_SECONDS:
        row={"source_id":source_id,"url":url,"finished_at":now.isoformat(),"outcome":"COOLDOWN","execution_authority":False}
        _append(telemetry_path,row); return row
    started=time.perf_counter()
    row={"source_id":source_id,"url":url,"finished_at":now.isoformat(),"outcome":"ERROR","http_status":None,"bytes":0,"content_type":None,"latency_ms":None,"parse_result":"NOT_PARSED","rejection_reason":None,"execution_authority":False}
    try:
        with httpx.Client(timeout=TIMEOUT_SECONDS,follow_redirects=True,transport=transport,headers={"User-Agent":"ProjectAtlas-Research/1.0"}) as client:
            with client.stream("GET",url) as resp:
                row["http_status"]=resp.status_code
                final_host=(urlparse(str(resp.url)).hostname or "").lower()
                if final_host!=SOURCE_REGISTRY[source_id].domain.lower():raise ValueError("redirect left governed domain")
                ctype=resp.headers.get("content-type","").split(";")[0].strip().lower(); row["content_type"]=ctype
                if resp.status_code!=200: row["rejection_reason"]="HTTP_STATUS"
                elif ctype not in ALLOWED_TYPES: row["rejection_reason"]="CONTENT_TYPE"
                else:
                    chunks=[]; total=0
                    for chunk in resp.iter_bytes():
                        total+=len(chunk)
                        if total>MAX_BYTES: row["rejection_reason"]="RESPONSE_TOO_LARGE"; break
                        chunks.append(chunk)
                    row["bytes"]=total
                    if row["rejection_reason"] is None:
                        body=b"".join(chunks).decode(resp.encoding or "utf-8",errors="replace")
                        row["outcome"]="FETCHED"; row["parse_result"]="NO_SUPPORTED_CLAIM"
                        row["body_sha256"]=__import__("hashlib").sha256(body.encode()).hexdigest()
                        if include_body: row["_body"]=body
    except Exception as e:
        row["rejection_reason"]=f"{type(e).__name__}:{str(e)[:160]}"
    row["latency_ms"]=round((time.perf_counter()-started)*1000,2)
    ephemeral=row.pop("_body",None); _append(telemetry_path,row)
    if include_body and ephemeral is not None: row["_body"]=ephemeral
    return row

def live_acceptance()->dict[str,Any]:
    results=[]
    for source_id in ("federal_reserve","hyperliquid_docs"):
        results.append(fetch_once(source_id))
    return {"ok":True,"results":results,"events_created":0,"execution_authority":False,
            "note":"E33 bounded fetch acceptance records telemetry only; no claim parser means no event creation."}
