from datetime import datetime,timezone,timedelta
from app.services.e42_alpha_policy import decision
from app.services.e42_alpha_health import source_health

def test_cadence_gate():
 assert decision([{"alpha_ms":100,"cycle_ms":200}]*29)["decouple_recommended"] is False
 assert decision([{"alpha_ms":60,"cycle_ms":200}]*30)["decouple_recommended"] is True

def test_source_age():
 now=datetime(2026,10,6,tzinfo=timezone.utc)
 assert source_health({"last_outcome":"FETCHED","last_http_status":200,"last_observed_at":(now-timedelta(hours=2)).isoformat()},now)=="HEALTHY"
 assert source_health({"last_outcome":"FETCHED","last_http_status":200,"last_observed_at":(now-timedelta(hours=25)).isoformat()},now)=="STALE"
