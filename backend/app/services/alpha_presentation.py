"""E38/E39 read-only Alpha/Catalyst presentation and typed Discord alerts."""
from __future__ import annotations
import json,os
from pathlib import Path
from app.alerts.discord import send_discord_alert
from app.services.alpha_ingestion import EVENT_PATH,feed
from app.services.alpha_operator import diagnostics

STATE_PATH=Path(__file__).resolve().parents[2]/"data"/"e38_alpha_alert_state.json"

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
            "stale":bool(e.get("stale")),"execution_authority":False,
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
    desc=(f"**{etype} · {source} · {trust}**\n"
          f"{title}\n"
          f"Entities: {entities}\nPublished: {published}\n"
          f"Provenance: {url}\n\n"
          "_Context intelligence only · external text is untrusted data · no order or PAPER-entry authority._")
    return {"symbol":"ALPHA","title":f"Atlas Alpha · {etype}","description":desc,
            "price":0.0,"severity":"INFO","opportunity":0,"confidence":0,"risk":0}

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

async def alert_new_alpha_events(*,sender=send_discord_alert,state_path=STATE_PATH,event_path=EVENT_PATH,predicate=is_material):
    view=alpha_view(event_path=event_path); state=_load(state_path)
    delivered=set(state.get("delivered_event_ids") or [])
    pending=[e for e in view["items"] if e["event_id"] not in delivered and predicate(e)]
    attempted=sent=0
    for event in reversed(pending):
        attempted+=1
        try: ok=bool(await sender(**build_alpha_alert(event)))
        except Exception: ok=False
        if ok: delivered.add(event["event_id"]); sent+=1
    if sent:_save(state_path,{"delivered_event_ids":sorted(delivered)})
    return {"attempted":attempted,"delivered":sent,"pending":len(pending)-sent,
            "execution_authority":False,"paper_entry_authority":False}
