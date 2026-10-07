"""E42 time-aware Alpha source health."""
from datetime import datetime,timezone

def source_health(source,now=None):
    source=source or {}; outcome=str(source.get("last_outcome") or ""); status=source.get("last_http_status")
    if not outcome:return "UNKNOWN"
    if outcome=="COOLDOWN":return "COOLDOWN"
    if outcome!="FETCHED" or status!=200:return "DEGRADED"
    stamp=source.get("last_observed_at") or source.get("last_fetched_at")
    try: seen=datetime.fromisoformat(str(stamp).replace("Z","+00:00"))
    except Exception:return "UNKNOWN"
    if seen.tzinfo is None:seen=seen.replace(tzinfo=timezone.utc)
    age=((now or datetime.now(timezone.utc))-seen.astimezone(timezone.utc)).total_seconds()
    if age < -300:return "FUTURE"
    return "STALE" if age>86400 else "HEALTHY"
