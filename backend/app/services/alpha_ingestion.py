"""Execution 32 append-only Alpha ingestion and read-only feed."""
from __future__ import annotations
from dataclasses import asdict
from datetime import datetime, timezone
import json, os
from pathlib import Path
from typing import Any, Iterable
from app.services.alpha_intelligence import SourceRecord, normalize_event, annotate_context, deduplicate, safety_contract

DATA_DIR=Path(__file__).resolve().parents[2]/"data"
RAW_PATH=DATA_DIR/"alpha_intelligence_raw.jsonl"
EVENT_PATH=DATA_DIR/"alpha_intelligence_events.jsonl"
STORE_VERSION="alpha-ingestion-store-v1"

SOURCE_REGISTRY={
    "hyperliquid_docs":SourceRecord("hyperliquid_docs","Hyperliquid official","OFFICIAL","PRIMARY_OFFICIAL","hyperliquid.gitbook.io"),
    "coinbase":SourceRecord("coinbase","Coinbase official","OFFICIAL","PRIMARY_OFFICIAL","www.coinbase.com"),
    "sec":SourceRecord("sec","U.S. SEC","OFFICIAL","PRIMARY_OFFICIAL","www.sec.gov"),
    "federal_reserve":SourceRecord("federal_reserve","Federal Reserve","MACRO","PRIMARY_OFFICIAL","www.federalreserve.gov"),
    "reuters":SourceRecord("reuters","Reuters","NEWS","REPUTABLE_REPORTING","www.reuters.com"),
}

def registry_view()->list[dict[str,Any]]:
    return [asdict(SOURCE_REGISTRY[k]) for k in sorted(SOURCE_REGISTRY)]

def _append_jsonl(path:Path,row:dict[str,Any]):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("a",encoding="utf-8",newline="\n") as f:
        f.write(json.dumps(row,sort_keys=True,ensure_ascii=False)+"\n")
        f.flush(); os.fsync(f.fileno())

def _read_jsonl(path:Path)->list[dict[str,Any]]:
    if not path.exists():return []
    out=[]
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            row=json.loads(line)
            if isinstance(row,dict):out.append(row)
        except Exception:continue
    return out

def ingest(raw:dict[str,Any],*,raw_path:Path=RAW_PATH,event_path:Path=EVENT_PATH,now:datetime|None=None)->dict[str,Any]:
    source_id=str(raw.get("source_id") or "")
    source=SOURCE_REGISTRY.get(source_id)
    if source is None:raise ValueError("source_id is not in governed registry")
    observed=(now or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat()
    raw_record={"store_version":STORE_VERSION,"observed_at":observed,"source_id":source_id,"payload":raw,
                "untrusted_external_text":True,"execution_authority":False}
    event=normalize_event(raw,source,now=now)
    existing=_read_jsonl(event_path)
    if any(x.get("event_id")==event.event_id for x in existing):
        return {"accepted":False,"reason":"EVENT_ID_ALREADY_STORED","event_id":event.event_id}
    _append_jsonl(raw_path,raw_record)
    row={"store_version":STORE_VERSION,"stored_at":observed,**asdict(event)}
    _append_jsonl(event_path,row)
    return {"accepted":True,"reason":"STORED","event_id":event.event_id}

def _event_from_row(row):
    from app.services.alpha_intelligence import IntelligenceEvent
    allowed=set(IntelligenceEvent.__dataclass_fields__)
    data={k:v for k,v in row.items() if k in allowed}
    for k in ("symbols","entities","corroborators"):
        if isinstance(data.get(k),list):data[k]=tuple(data[k])
    return IntelligenceEvent(**data)

def feed(*,event_path:Path=EVENT_PATH,limit:int=100,include_stale:bool=True)->dict[str,Any]:
    rows=_read_jsonl(event_path); events=[]
    for row in rows:
        try:events.append(_event_from_row(row))
        except Exception:continue
    annotated=annotate_context(events)
    if not include_stale:annotated=[e for e in annotated if not e.stale]
    unique=deduplicate(annotated)
    unique.sort(key=lambda e:(e.published_at or e.retrieved_at,e.retrieved_at),reverse=True)
    items=[asdict(e) for e in unique[:max(1,min(int(limit),500))]]
    return {"ok":True,"store_version":STORE_VERSION,"source_count":len(SOURCE_REGISTRY),
            "stored_event_count":len(events),"feed_count":len(items),"items":items,
            **safety_contract()}

def store_status(*,raw_path:Path=RAW_PATH,event_path:Path=EVENT_PATH)->dict[str,Any]:
    return {"store_version":STORE_VERSION,"raw_records":len(_read_jsonl(raw_path)),
            "normalized_records":len(_read_jsonl(event_path)),"sources":registry_view(),**safety_contract()}
