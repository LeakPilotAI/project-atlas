"""E36 operator diagnostics for bounded Alpha research."""
from datetime import datetime,timezone
from pathlib import Path
import json
from app.services.alpha_fetch import FETCH_LOG,FETCH_TARGETS
from app.services.alpha_ingestion import store_status

def diagnostics(telemetry_path=FETCH_LOG):
    path=Path(telemetry_path); latest={}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            try: row=json.loads(line)
            except Exception: continue
            sid=row.get("source_id")
            if sid in FETCH_TARGETS: latest[sid]=row
    sources={}
    for sid,url in FETCH_TARGETS.items():
        row=latest.get(sid,{})
        sources[sid]={"url":url,"last_finished_at":row.get("finished_at"),"last_observed_at":row.get("finished_at"),"last_fetched_at":row.get("finished_at") if row.get("outcome")=="FETCHED" else None,"last_outcome":row.get("outcome"),"last_http_status":row.get("http_status"),"last_parse_result":row.get("parse_result")}
    return {"ok":True,"version":"e36-alpha-operator-v1","generated_at":datetime.now(timezone.utc).isoformat(),"sources":sources,"store":store_status(),"execution_authority":False,"paper_entry_authority":False,"automatic_worker":False,"live_capital_allowed":False}
