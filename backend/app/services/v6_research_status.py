"""Lightweight Command Center status for V6 research infrastructure.

This intentionally does not run historical challenger/edge recomputation during a
normal Command Center refresh. It reports service availability plus durable
prospective cohort state. Research health is never trading readiness.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from app.services.challenger_prospective import MARKER_PATH, MEMBERSHIP_PATH, COHORT_NAME
from app.services.paper_journal import iter_jsonl


def _marker(path: Path) -> Optional[dict[str, Any]]:
    if not path.exists(): return None
    try:
        row=json.loads(path.read_text(encoding="utf-8"))
        return row if isinstance(row,dict) else None
    except Exception: return None


def _membership_counts(path: Path) -> dict[str, Any]:
    unique={}
    if path.exists():
        for row in iter_jsonl(path):
            if row.get("event")=="membership" and row.get("trade_id"):
                unique[str(row["trade_id"])]=row
    by={"trend_regime":0,"extension_3pct":0,"quality_85":0,"trend_extension_quality":0}
    for row in unique.values():
        for name in row.get("challengers") or []:
            if name in by: by[name]+=1
    return {"unique_memberships":len(unique),"by_challenger":by}


def research_status(*, marker_path: Path=MARKER_PATH, membership_path: Path=MEMBERSHIP_PATH)->dict[str,Any]:
    marker=_marker(marker_path); counts=_membership_counts(membership_path)
    return {
        "domain":"V6_RESEARCH","mode":"READ_ONLY_STATUS","heavy_retrospective_recompute":False,
        "services":{"challenger_lab":True,"prospective_cohort":True,"point_in_time_exit_replay":True,"shadow_paper_interactions":True},
        "prospective":{"cohort":(marker or {}).get("cohort") or COHORT_NAME,"started_at":(marker or {}).get("started_at"),"initialized":bool(marker),**counts},
        "research_collection_healthy":bool(marker),
        "research_health_meaning":"Infrastructure/cutoff status only; not evidence of positive expectancy.",
        "trading_readiness":"NOT_READY","stable_positive_expectancy_established":False,"automatic_promotion":False,
        "production_strategy_modified":False,"live_capital_allowed":False,"automatic_real_money_execution":False,
    }
