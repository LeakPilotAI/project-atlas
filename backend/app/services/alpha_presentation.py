"""E38/E39 read-only Alpha/Catalyst presentation and typed Discord alerts."""
from __future__ import annotations
import json,os
from datetime import datetime,timezone
from pathlib import Path
from app.alerts.discord import send_discord_alert
from app.services.alpha_ingestion import EVENT_PATH,feed
from app.services.alpha_operator import diagnostics
from app.services.e48_discord_events import legacy_payload_event, deliver_legacy_payload

STATE_PATH=Path(__file__).resolve().parents[2]/"data"/"e38_alpha_alert_state.json"
TELEMETRY_PATH=Path(__file__).resolve().parents[2]/"data"/"e40_alpha_delivery_telemetry.jsonl"

def freshness_badge(published_at,now=None):
    try: dt=datetime.fromisoformat(str(published_at).replace("Z","+00:00"))
    except Exception: return "UNKNOWN"
    if dt.tzinfo is None: dt=dt.replace(tzinfo=timezone.utc)
    age=((now or datetime.now(timezone.utc))-dt.astimezone(timezone.utc)).total_seconds()/3600
    return "FUTURE" if age<0 else "FRESH" if age<=24 else "RECENT" if age<=72 else "AGING" if age<=168 else "STALE"

def source_health(source):
    outcome=str((source or {}).get("last_outcome") or ""); status=(source or {}).get("last_http_status")
    return "HEALTHY" if outcome=="FETCHED" and status==200 else "COOLDOWN" if outcome=="COOLDOWN" else "UNKNOWN" if not outcome else "DEGRADED"

def alpha_view(*,event_path=EVENT_PATH,telemetry_path=None,limit=12):
    f=feed(event_path=Path(event_path),limit=limit,include_stale=False)
    op=diagnostics() if telemetry_path is None else diagnostics(telemetry_path)
    items=[]
    for e in f.get("items") or []:
        items.append({
            "event_id":e.get("event_id"),"source_id":e.get("source_id"),
            "source_class":e.get("source_class"),"trust_tier":e.get("trust_tier"),
            "published_at":e.get("published_at"),"title":e.get("title"),
            "event_type":e.get("event_type"),"entities":list(e.get("entities") or []),
            "symbols":list(e.get("symbols") or []),"url":e.get("url"),
            "stale":bool(e.get("stale")),"freshness":freshness_badge(e.get("published_at")),
            "corroboration_count":int(e.get("corroboration_count") or 0),
            "corroborators":list(e.get("corroborators") or []),"execution_authority":False,
        })
    return {"ok":True,"version":"e38-alpha-presentation-v1","items":items,
            "stored_event_count":f.get("stored_event_count",0),"sources":op.get("sources",{}),
            "execution_authority":False,"paper_entry_authority":False,
            "strategy_mutation_authority":False,"automatic_worker":False,"live_capital_allowed":False}

def build_alpha_alert(event):
    event_id=str(event.get("event_id") or "")
    title=str(event.get("title") or "").strip()
    if not event_id or not title: raise ValueError("invalid Alpha event")
    source=str(event.get("source_id") or "unknown").upper()
    etype=str(event.get("event_type") or "OTHER").upper()
    trust=str(event.get("trust_tier") or "UNKNOWN")
    entities=", ".join(str(x) for x in (event.get("entities") or [])) or "none"
    published=str(event.get("published_at") or "unknown")
    url=str(event.get("url") or "")
    freshness=freshness_badge(event.get("published_at"))
    corroborators=event.get("corroborators") or []
    support=", ".join(f"{x.get('source_id','unknown')} ({x.get('domain','unknown')})" for x in corroborators) or "none"
    desc=(f"**{etype} · {source} · {trust} · {freshness}**\n"
          f"{title}\n"
          f"Entities: {entities}\nPublished: {published}\n"
          f"Independent corroboration: {support}\nProvenance: {url}\n\n"
          "_Context intelligence only · external text is untrusted data · no order or PAPER-entry authority._")
    severity="HIGH" if trust=="PRIMARY_OFFICIAL" and int(event.get("corroboration_count") or 0)>=2 else "MEDIUM"
    return {"symbol":"ALPHA","title":f"Atlas Alpha · {etype}","description":desc,
            "price":0.0,"severity":severity,"opportunity":0,"confidence":0,"risk":0}

def _load(path):
    try:return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:return {"delivered_event_ids":[]}

def _save(path,state):
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix(".tmp"); tmp.write_text(json.dumps(state,sort_keys=True),encoding="utf-8"); os.replace(tmp,path)

def is_material(event):
    types={"REGULATORY","MACRO"}
    entities={"Bitcoin","Ethereum","Stablecoins","Crypto Assets","Digital Assets","Tokenized Securities","Market Structure","FOMC","Federal Funds Rate","Interest Rates","Inflation"}
    return str(event.get("event_type") or "").upper() in types and bool(set(event.get("entities") or []) & entities) and not bool(event.get("stale"))

def delivery_history(path=TELEMETRY_PATH,limit=25):
    rows=[];invalid=0;p=Path(path)
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            if not line.strip():continue
            try:r=json.loads(line)
            except Exception:invalid+=1;continue
            if not isinstance(r,dict) or not r.get("at") or r.get("raw_external_body_stored") is not False or r.get("execution_authority") is not False:invalid+=1;continue
            rows.append(r)
    cap=max(1,min(int(limit),100))
    return {"ok":invalid==0,"records":rows[-cap:],"record_count":len(rows),"invalid_record_count":invalid,"integrity_ok":invalid==0,"bounded_limit":cap,"execution_authority":False,"paper_entry_authority":False,"live_capital_allowed":False}

def delivery_status(state_path=STATE_PATH):
    s=_load(state_path)
    return {"dedup_count":len(s.get("delivered_event_ids") or []),"last_attempt_at":s.get("last_attempt_at"),"last_result":s.get("last_result"),"last_error":s.get("last_error"),"execution_authority":False,"paper_entry_authority":False}

def _append_telemetry(path,row):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("a",encoding="utf-8") as f:f.write(json.dumps(row,sort_keys=True)+"\n");f.flush();os.fsync(f.fileno())

async def alert_new_alpha_events(*,sender=send_discord_alert,state_path=STATE_PATH,event_path=EVENT_PATH,predicate=is_material,telemetry_path=TELEMETRY_PATH):
    view=alpha_view(event_path=event_path); state=_load(state_path); delivered=set(state.get("delivered_event_ids") or [])
    pending=[e for e in view["items"] if e["event_id"] not in delivered and predicate(e)]
    attempted=sent=0; failed_ids=[]; delivered_now=[]
    for event in reversed(pending):
        attempted+=1
        try:
            payload=build_alpha_alert(event)
            typed=legacy_payload_event(lane="ALPHA_CATALYST",event_type=str(event.get("event_type") or ""),identity=str(event["event_id"]),payload=payload,provenance=[str(event.get("url") or "")],material=True)
            ok=bool((await deliver_legacy_payload(typed,sender=sender))["acknowledged"])
        except Exception: ok=False
        if ok: delivered.add(event["event_id"]);delivered_now.append(event["event_id"]);sent+=1
        else: failed_ids.append(event["event_id"])
    now=datetime.now(timezone.utc).isoformat(); result={"attempted":attempted,"delivered":sent,"pending":len(pending)-sent}
    state={"delivered_event_ids":sorted(delivered),"last_attempt_at":now,"last_result":result,"last_error":None if not failed_ids else "SEND_FAILED"};_save(state_path,state)
    if attempted:_append_telemetry(telemetry_path,{"at":now,"attempted":attempted,"delivered":sent,"pending":result["pending"],"delivered_event_ids":delivered_now,"failed_event_ids":failed_ids,"raw_external_body_stored":False,"execution_authority":False})
    return {**result,"execution_authority":False,"paper_entry_authority":False}
