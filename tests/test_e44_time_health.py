from datetime import datetime,timezone,timedelta
import json
from app.services.e43_cadence_store import append_observation,history
from app.services.e42_alpha_health import source_health
from app.services.alpha_operator import diagnostics

def test_new_cadence_timestamp_and_legacy_compat(tmp_path):
 p=tmp_path/"c.jsonl"
 p.write_text(json.dumps({"alpha_ms":5,"cycle_ms":100,"execution_authority":False})+"\n",encoding="utf-8")
 row=append_observation(6,100,p);h=history(p)
 assert row["observed_at"].endswith("+00:00")
 assert h["valid_count"]==2 and h["timestamped_count"]==1 and h["legacy_untimestamped_count"]==1
 assert h["rows"][0]["observed_at"] is None

def test_source_health_boundaries_and_future():
 now=datetime(2026,10,6,tzinfo=timezone.utc)
 def s(hours):return {"last_outcome":"FETCHED","last_http_status":200,"last_observed_at":(now-timedelta(hours=hours)).isoformat()}
 assert source_health(s(24),now)=="HEALTHY"
 assert source_health(s(24.001),now)=="STALE"
 assert source_health({"last_outcome":"FETCHED","last_http_status":200,"last_observed_at":"bad"},now)=="UNKNOWN"
 future={"last_outcome":"FETCHED","last_http_status":200,"last_observed_at":(now+timedelta(minutes=6)).isoformat()}
 assert source_health(future,now)=="FUTURE"

def test_operator_exposes_fetch_timestamp(tmp_path):
 p=tmp_path/"fetch.jsonl";stamp="2026-10-06T00:00:00+00:00"
 p.write_text(json.dumps({"source_id":"sec","finished_at":stamp,"outcome":"FETCHED","http_status":200})+"\n",encoding="utf-8")
 s=diagnostics(p)["sources"]["sec"]
 assert s["last_observed_at"]==stamp and s["last_fetched_at"]==stamp
