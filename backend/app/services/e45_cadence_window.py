"""E45 preregistered current-window cadence/drift policy.

Frozen before live E45 outcome inspection.
"""
from datetime import datetime,timezone

POLICY={
 "version":"e45-current-cadence-v1",
 "min_current_observations":30,
 "max_observation_age_hours":24.0,
 "alpha_p95_ms_threshold":50.0,
 "alpha_cycle_share_p95_threshold":0.20,
 "drift_ratio_threshold":1.50,
}

def _dt(value):
 try:
  d=datetime.fromisoformat(str(value).replace("Z","+00:00"))
 except Exception:return None
 if d.tzinfo is None:d=d.replace(tzinfo=timezone.utc)
 return d.astimezone(timezone.utc)

def _p95(values):
 if not values:return None
 s=sorted(values);return s[min(len(s)-1,int((len(s)-1)*.95))]

def current_window(rows, historical=None, now=None):
 now=(now or datetime.now(timezone.utc)).astimezone(timezone.utc);current=[];future=0;stale=0;legacy=0
 for row in rows:
  stamp=_dt(row.get("observed_at"))
  if stamp is None:legacy+=1;continue
  age=(now-stamp).total_seconds()/3600
  if age < -5/60:future+=1;continue
  if age>POLICY["max_observation_age_hours"]:stale+=1;continue
  try:a=float(row["alpha_ms"]);c=float(row["cycle_ms"])
  except Exception:continue
  if a>=0 and c>0 and a<=c:current.append({"alpha_ms":a,"cycle_ms":c})
 a95=_p95([x["alpha_ms"] for x in current]);q95=_p95([x["alpha_ms"]/x["cycle_ms"] for x in current])
 ready=len(current)>=POLICY["min_current_observations"]
 breach=bool(ready and ((a95 or 0)>POLICY["alpha_p95_ms_threshold"] or (q95 or 0)>POLICY["alpha_cycle_share_p95_threshold"]))
 h=(historical or {});ha=h.get("alpha_p95_ms");hq=h.get("alpha_cycle_share_p95")
 drift_alpha=(a95/ha) if a95 is not None and ha else None;drift_share=(q95/hq) if q95 is not None and hq else None
 drift=bool(ready and ((drift_alpha or 0)>POLICY["drift_ratio_threshold"] or (drift_share or 0)>POLICY["drift_ratio_threshold"]))
 return {"policy":POLICY,"current_observations":len(current),"legacy_untimestamped":legacy,"stale_timestamped":stale,"future_timestamped":future,"alpha_p95_ms":a95,"alpha_cycle_share_p95":q95,"evidence_ready":ready,"threshold_breach":breach,"drift_alpha_ratio":drift_alpha,"drift_share_ratio":drift_share,"drift_flag":drift,"decouple_recommended":breach,"execution_authority":False}
