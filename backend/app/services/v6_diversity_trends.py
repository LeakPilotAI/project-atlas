"""Longitudinal diversity diagnostics derived from append-only V6 forward snapshots.

Each snapshot is evaluated only against prospective memberships that existed at or
before that snapshot timestamp. Historical memberships are never reclassified.
"""
from __future__ import annotations
from collections import Counter
from pathlib import Path
from typing import Any, Dict
from app.services.paper_journal import iter_jsonl
from app.services.challenger_prospective import MEMBERSHIP_PATH
from app.services.v6_forward_monitor import HISTORY_PATH
from app.services.v6_window_diversity import _parse,MIN_DAYS,MIN_REGIMES,MIN_REGIME_CLOSES

MIN_LONGITUDINAL_SNAPSHOTS=3


def _state(rows:list[dict[str,Any]])->dict[str,Any]:
    days=Counter();regimes=Counter()
    for r in rows:
        ts=_parse(r.get("entry_timestamp"));regime=((r.get("pre_entry_snapshot") or {}).get("regime"))
        if ts:days[ts.date().isoformat()]+=1
        if regime:regimes[str(regime)]+=1
    qualifying={k:v for k,v in regimes.items() if v>=MIN_REGIME_CLOSES}
    temporal=len(days)>=MIN_DAYS;regime_ok=len(qualifying)>=MIN_REGIMES
    return {"membership_count":len(rows),"calendar_day_count":len(days),"qualifying_regime_count":len(qualifying),"temporal_diversity_established":temporal,"regime_diversity_established":regime_ok,"diversity_established":bool(temporal and regime_ok)}


def diversity_trends(*,membership_path:Path=MEMBERSHIP_PATH,history_path:Path=HISTORY_PATH)->Dict[str,Any]:
    memberships=[r for r in iter_jsonl(membership_path) if r.get("event")=="membership"] if membership_path.exists() else []
    snapshots=[]
    if history_path.exists():
        snapshots=[r for r in iter_jsonl(history_path) if r.get("event")=="v6_forward_evidence_snapshot" and _parse(r.get("timestamp"))]
    snapshots.sort(key=lambda r:_parse(r.get("timestamp")))
    series:dict[str,list[dict[str,Any]]]={}
    for snap in snapshots:
        cutoff=_parse(snap.get("timestamp"));forward=((snap.get("evidence") or {}).get("forward") or {})
        for name in forward:
            rows=[r for r in memberships if name in (r.get("challengers") or []) and (lambda t:t is not None and t<=cutoff)(_parse(r.get("entry_timestamp")))]
            point={"timestamp":snap.get("timestamp"),**_state(rows)}
            series.setdefault(name,[]).append(point)
    candidates={}
    for name,points in series.items():
        enough=len(points)>=MIN_LONGITUDINAL_SNAPSHOTS
        recent=points[-MIN_LONGITUDINAL_SNAPSHOTS:] if enough else points
        flags=[bool(p["diversity_established"]) for p in recent]
        if not enough:trend="INSUFFICIENT_LONGITUDINAL_EVIDENCE"
        elif all(flags):trend="STABLE_DIVERSE"
        elif flags[-1] and not flags[0]:trend="BROADENING"
        elif flags[0] and not flags[-1]:trend="COLLAPSED"
        else:trend="MIXED_OR_CONCENTRATED"
        candidates[name]={"snapshot_count":len(points),"required_longitudinal_snapshots":MIN_LONGITUDINAL_SNAPSHOTS,"trend":trend,"longitudinal_evidence_sufficient":enough,"latest":points[-1] if points else None,"series":points,"human_review_only":True,"production_promoted":False}
    return {"ok":True,"title":"ATLAS V6 FORWARD DIVERSITY TRENDS","mode":"APPEND_ONLY_POINT_IN_TIME","snapshot_count":len(snapshots),"candidates":candidates,"retrospective_reclassification":False,"automatic_promotion":False,"production_strategy_modified":False,"trading_readiness":"NOT_READY","live_capital_allowed":False,"automatic_real_money_execution":False,"note":"Trend labels describe point-in-time forward diversity progression only. They do not establish statistical independence, positive expectancy, production approval, or live readiness."}
