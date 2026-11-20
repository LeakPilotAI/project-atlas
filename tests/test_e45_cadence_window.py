from datetime import datetime,timezone,timedelta
from app.services.e45_cadence_window import current_window,POLICY

NOW=datetime(2026,10,6,12,tzinfo=timezone.utc)
def row(a,c,h=1):return {"observed_at":(NOW-timedelta(hours=h)).isoformat(),"alpha_ms":a,"cycle_ms":c}

def test_policy_is_frozen():
 assert POLICY["min_current_observations"]==30
 assert POLICY["max_observation_age_hours"]==24
 assert POLICY["alpha_p95_ms_threshold"]==50
 assert POLICY["alpha_cycle_share_p95_threshold"]==.20
 assert POLICY["drift_ratio_threshold"]==1.50

def test_legacy_stale_future_excluded():
 rows=[{"observed_at":None,"alpha_ms":1,"cycle_ms":10},row(1,10,25),{"observed_at":(NOW+timedelta(minutes=6)).isoformat(),"alpha_ms":1,"cycle_ms":10},row(2,100)]
 x=current_window(rows,now=NOW)
 assert x["current_observations"]==1 and x["legacy_untimestamped"]==1 and x["stale_timestamped"]==1 and x["future_timestamped"]==1
 assert not x["evidence_ready"]

def test_exact_24h_included():
 x=current_window([row(2,100,24)],now=NOW)
 assert x["current_observations"]==1 and x["stale_timestamped"]==0

def test_current_gate_and_threshold():
 rows=[row(60,100) for _ in range(30)]
 x=current_window(rows,now=NOW)
 assert x["evidence_ready"] and x["threshold_breach"] and x["decouple_recommended"]

def test_drift_informational_only():
 rows=[row(20,200) for _ in range(30)]
 x=current_window(rows,{"alpha_p95_ms":10,"alpha_cycle_share_p95":.05},NOW)
 assert x["drift_flag"] and not x["threshold_breach"] and not x["decouple_recommended"]
