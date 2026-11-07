"""Forward-only temporal/regime diversity diagnostics for V6 research evidence."""
from __future__ import annotations
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict
from app.services.paper_journal import iter_jsonl
from app.services.challenger_prospective import MEMBERSHIP_PATH
from app.services.v6_forward_monitor import HISTORY_PATH

MIN_DAYS=3
MIN_REGIMES=2
MIN_REGIME_CLOSES=10


def _parse(v:Any):
    try:
        dt=datetime.fromisoformat(str(v).replace("Z","+00:00"))
        if dt.tzinfo is None:dt=dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:return None


def _latest_snapshot(path:Path)->Dict[str,Any]|None:
    last=None
    if path.exists():
        for row in iter_jsonl(path):
            if row.get("event")=="v6_forward_evidence_snapshot":last=row
    return last


def diversity_report(*,membership_path:Path=MEMBERSHIP_PATH,history_path:Path=HISTORY_PATH)->Dict[str,Any]:
    latest=_latest_snapshot(history_path)
    memberships=[r for r in iter_jsonl(membership_path) if r.get("event")=="membership"] if membership_path.exists() else []
    candidates={}
    names=[]
    if latest:
        names=list((((latest.get("evidence") or {}).get("forward") or {}).keys()))
    for name in names:
        rows=[r for r in memberships if name in (r.get("challengers") or [])]
        days=Counter(); regimes=Counter()
        for r in rows:
            ts=_parse(r.get("entry_timestamp")); regime=((r.get("pre_entry_snapshot") or {}).get("regime"))
            if ts:days[ts.date().isoformat()]+=1
            if regime:regimes[str(regime)]+=1
        qualifying_regimes={k:v for k,v in regimes.items() if v>=MIN_REGIME_CLOSES}
        temporal_diverse=len(days)>=MIN_DAYS
        regime_diverse=len(qualifying_regimes)>=MIN_REGIMES
        candidates[name]={"membership_count":len(rows),"calendar_days":dict(sorted(days.items())),"regimes":dict(sorted(regimes.items())),"qualifying_regimes":qualifying_regimes,"required_calendar_days":MIN_DAYS,"required_regimes":MIN_REGIMES,"minimum_memberships_per_regime":MIN_REGIME_CLOSES,"temporal_diversity_established":temporal_diverse,"regime_diversity_established":regime_diverse,"diversity_established":bool(temporal_diverse and regime_diverse),"human_review_only":True,"production_promoted":False}
    return {"ok":True,"title":"ATLAS V6 FORWARD WINDOW DIVERSITY","mode":"FORWARD_MEMBERSHIP_ONLY","snapshot_available":latest is not None,"candidates":candidates,"diversity_established":[n for n,v in candidates.items() if v["diversity_established"]],"retrospective_substitution":False,"automatic_promotion":False,"production_strategy_modified":False,"trading_readiness":"NOT_READY","live_capital_allowed":False,"automatic_real_money_execution":False,"note":"Diversity is descriptive research evidence only. It requires forward memberships spanning >=3 calendar days and >=2 contemporaneously recorded regimes with >=10 memberships each; it is not production approval."}
