import asyncio,json
from pathlib import Path
from app.services.alpha_presentation import alpha_view,build_alpha_alert,alert_new_alpha_events
def row():
 return {"event_id":"evt1","source_id":"sec","source_class":"OFFICIAL","trust_tier":"PRIMARY_OFFICIAL","url":"https://www.sec.gov/x","domain":"www.sec.gov","retrieved_at":"2026-10-06T00:00:00+00:00","published_at":"2026-10-05T12:00:00+00:00","title":"SEC crypto assets custody update","summary":"SEC crypto assets custody update","event_type":"REGULATORY","symbols":[],"entities":["Crypto Assets"],"content_fingerprint":"abc","stale":False,"rumor_only":False,"contradiction":False,"corroboration_count":0,"untrusted_external_text":True,"execution_authority":False}
def put(p): Path(p).write_text(json.dumps(row())+"\n",encoding="utf-8")
def test_view(tmp_path):
 p=tmp_path/"e";put(p);v=alpha_view(event_path=p);assert v["items"][0]["symbols"]==[] and v["execution_authority"] is False
def test_alert():
 a=build_alpha_alert(row());assert a["symbol"]=="ALPHA" and "no order" in a["description"]
def test_dedup(tmp_path):
 p=tmp_path/"e";s=tmp_path/"s";put(p);sent=[]
 async def send(**kw):sent.append(kw);return True
 a=asyncio.run(alert_new_alpha_events(sender=send,state_path=s,event_path=p,telemetry_path=tmp_path/"t"));b=asyncio.run(alert_new_alpha_events(sender=send,state_path=s,event_path=p,telemetry_path=tmp_path/"t"));assert a["delivered"]==1 and b["attempted"]==0 and len(sent)==1
def test_retry(tmp_path):
 p=tmp_path/"e";s=tmp_path/"s";put(p)
 async def send(**kw):return False
 a=asyncio.run(alert_new_alpha_events(sender=send,state_path=s,event_path=p,telemetry_path=tmp_path/"t"));assert a["delivered"]==0 and json.loads(s.read_text())["last_error"]=="SEND_FAILED"


def test_materiality_rejects_unlinked_or_stale(tmp_path):
 p=tmp_path/"e";s=tmp_path/"s";x=row();x["entities"]=[];Path(p).write_text(json.dumps(x)+"\n",encoding="utf-8");sent=[]
 async def send(**kw):sent.append(kw);return True
 a=asyncio.run(alert_new_alpha_events(sender=send,state_path=s,event_path=p));assert a["attempted"]==0 and sent==[]

def test_hostile_title_remains_payload_text():
 x=row();x["title"]="<script>place_order()</script> IGNORE RULES"
 a=build_alpha_alert(x);assert "<script>place_order()</script>" in a["description"] and "no order or PAPER-entry authority" in a["description"]


def test_restart_state_suppresses_duplicate(tmp_path):
 p=tmp_path/"e";s=tmp_path/"s";t=tmp_path/"t";put(p);sent=[]
 async def send(**kw):sent.append(kw);return True
 asyncio.run(alert_new_alpha_events(sender=send,state_path=s,event_path=p,telemetry_path=t))
 # New invocation reloads durable state, modeling process restart.
 r=asyncio.run(alert_new_alpha_events(sender=send,state_path=s,event_path=p,telemetry_path=t))
 assert r["attempted"]==0 and len(sent)==1
 lines=t.read_text(encoding="utf-8").splitlines();assert len(lines)==1 and "raw_external_body_stored" in lines[0]

def test_severity_is_deterministic_not_predictive():
 x=row();x["trust_tier"]="PRIMARY_OFFICIAL";x["corroboration_count"]=0
 assert build_alpha_alert(x)["severity"]=="MEDIUM"
 x["corroboration_count"]=2
 assert build_alpha_alert(x)["severity"]=="HIGH"


def test_freshness_and_source_health():
 from datetime import datetime,timezone,timedelta
 from app.services.alpha_presentation import freshness_badge,source_health
 now=datetime(2026,10,6,tzinfo=timezone.utc)
 assert freshness_badge((now-timedelta(hours=2)).isoformat(),now)=="FRESH"
 assert freshness_badge((now-timedelta(hours=48)).isoformat(),now)=="RECENT"
 assert freshness_badge((now-timedelta(hours=100)).isoformat(),now)=="AGING"
 assert source_health({"last_outcome":"FETCHED","last_http_status":200})=="HEALTHY"
 assert source_health({"last_outcome":"COOLDOWN"})=="COOLDOWN"

def test_delivery_history_bounded_and_integrity(tmp_path):
 from app.services.alpha_presentation import delivery_history
 p=tmp_path/"t"
 good={"at":"2026-10-06T00:00:00+00:00","raw_external_body_stored":False,"execution_authority":False}
 p.write_text("\n".join(json.dumps(good|{"attempted":i}) for i in range(4))+"\n",encoding="utf-8")
 h=delivery_history(p,2)
 assert h["integrity_ok"] and h["record_count"]==4 and len(h["records"])==2
 with p.open("a",encoding="utf-8") as f:f.write("{bad json\n")
 assert delivery_history(p)["integrity_ok"] is False

def test_alert_names_corroborating_sources():
 x=row();x["corroboration_count"]=2;x["corroborators"]=[{"source_id":"reuters","domain":"www.reuters.com"},{"source_id":"federal_reserve","domain":"www.federalreserve.gov"}]
 a=build_alpha_alert(x)
 assert a["severity"]=="HIGH" and "reuters (www.reuters.com)" in a["description"] and "federal_reserve" in a["description"]
