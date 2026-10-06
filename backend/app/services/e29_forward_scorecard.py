"""Execution 29: append-only forward membership and baseline/challenger scorecard."""
from __future__ import annotations

import json, os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable

from app.services.e27_preregistration import (
    MIN_CLOSED_PER_ARM, MIN_DISTINCT_SYMBOLS, MIN_FORWARD_DAYS,
    MAX_SINGLE_SYMBOL_SHARE, MAX_EXTREME_LOSS_R,
)
from app.services.e28_challenger_workbench import (
    BASELINE_EXECUTION_MODEL, BASELINE_STRATEGY, CHALLENGER_VERSION,
    FREEZE_START_UTC, FROZEN_MOMENTUM_PCT_MIN, FROZEN_TREND_PCT_MIN, qualifies,
)
from app.services.paper_journal import JOURNAL_PATH, iter_jsonl

MEMBERSHIP_PATH=Path(__file__).resolve().parents[2]/"data"/"e29_perps_challenger_membership.jsonl"
SCORECARD_VERSION="perp-setup-v2-e29-forward-scorecard-v1"


def _ts(row):
    return str(row.get("entry_timestamp") or row.get("signal_timestamp") or "")


def _eligible_open(row):
    f=row.get("features") if isinstance(row.get("features"),dict) else {}
    return (row.get("event")=="open" and str(row.get("trade_type") or "PAPER").upper()=="PAPER"
            and row.get("strategy")==BASELINE_STRATEGY and row.get("side")=="LONG"
            and f.get("paper_execution_model_version")==BASELINE_EXECUTION_MODEL
            and _ts(row) >= FREEZE_START_UTC)


def _open_snapshot(row):
    f=row.get("features") if isinstance(row.get("features"),dict) else {}
    return {k:v for k,v in {
        "signal_score":row.get("signal_score"),"momentum_pct":f.get("momentum_pct"),
        "trend_pct":f.get("trend_pct"),"volatility_pct":f.get("volatility_pct")}.items()}


def classify_open(row, thresholds):
    snap=_open_snapshot(row)
    return {
        "event":"e29_membership","membership_version":SCORECARD_VERSION,
        "challenger_version":CHALLENGER_VERSION,"trade_id":str(row.get("trade_id") or ""),
        "symbol":str(row.get("symbol") or "UNKNOWN"),"entry_timestamp":_ts(row),
        "baseline_member":True,"challenger_member":bool(qualifies(snap,thresholds)),
        "open_snapshot":snap,"membership_frozen":True,
    }


def sync_membership(rows: Iterable[Dict[str,Any]], path: Path=MEMBERSHIP_PATH):
    existing={}
    if path.exists():
        for r in iter_jsonl(path):
            if r.get("event")=="e29_membership" and r.get("trade_id"):
                existing[str(r["trade_id"])]=r
    thresholds={"momentum_pct_min":FROZEN_MOMENTUM_PCT_MIN,"trend_pct_min":FROZEN_TREND_PCT_MIN}
    added=0
    for row in rows:
        if not _eligible_open(row):
            continue
        tid=str(row.get("trade_id") or "")
        if not tid or tid in existing:
            continue
        rec=classify_open(row,thresholds)
        path.parent.mkdir(parents=True,exist_ok=True)
        with path.open("a",encoding="utf-8") as f:
            f.write(json.dumps(rec,sort_keys=True,default=str)+"\n"); f.flush()
            try: os.fsync(f.fileno())
            except OSError: pass
        existing[tid]=rec; added+=1
    return existing,added


def _r(row): return float(row.get("net_pnl_r",row.get("R_multiple",0)) or 0)


def _overshoot(row):
    if row.get("exit_reason")!="SETUP_STOP": return None
    risk=abs(float(row.get("risk_price") or 0))
    if not risk:return None
    stop=float(row.get("initial_stop") or row.get("stop_price") or 0)
    px=float(row.get("actual_exit_price") or 0)
    return (stop-px)/risk if row.get("side")=="LONG" else (px-stop)/risk


def _metrics(closes):
    closes=sorted(closes,key=lambda r:str(r.get("exit_timestamp") or r.get("timestamp") or ""))
    vals=[_r(r) for r in closes]; n=len(vals); eq=peak=dd=0.0
    for x in vals:
        eq+=x; peak=max(peak,eq); dd=max(dd,peak-eq)
    syms=Counter(str(r.get("symbol") or "UNKNOWN") for r in closes)
    stops=[r for r in closes if r.get("exit_reason")=="SETUP_STOP"]
    overs=[x for x in (_overshoot(r) for r in stops) if x is not None]
    entries=[_ts(r) for r in closes if _ts(r)]
    days=0
    if entries:
        ds=[datetime.fromisoformat(x.replace("Z","+00:00")).date() for x in entries]
        days=(max(ds)-min(ds)).days+1
    return {
        "closed_trades":n,"net_pnl_r":round(sum(vals),4),
        "expectancy_r_after_recorded_costs":round(sum(vals)/n,4) if n else None,
        "win_rate":round(sum(x>0 for x in vals)/n,4) if n else None,
        "max_drawdown_r":round(dd,4) if n else None,"worst_trade_r":round(min(vals),4) if n else None,
        "avg_mfe_r":round(sum(float(r.get("mfe_r") or 0) for r in closes)/n,4) if n else None,
        "avg_mae_r":round(sum(float(r.get("mae_r") or 0) for r in closes)/n,4) if n else None,
        "setup_stop_rate":round(len(stops)/n,4) if n else None,
        "avg_stop_overshoot_r":round(sum(overs)/len(overs),4) if overs else None,
        "avg_execution_slippage_bps":round(sum(float(r.get("slippage_bps") or 0) for r in closes)/n,4) if n else None,
        "distinct_symbols":len(syms),"max_single_symbol_share":round(max(syms.values())/n,4) if n else None,
        "forward_calendar_days":days,
    }


def build_scorecard(rows, memberships):
    closes={str(r.get("trade_id") or ""):r for r in rows if r.get("event")=="close"}
    baseline=[closes[t] for t,m in memberships.items() if m.get("baseline_member") and t in closes]
    challenger=[closes[t] for t,m in memberships.items() if m.get("challenger_member") and t in closes]
    b,c=_metrics(baseline),_metrics(challenger)
    minimums={
        "baseline_min_closes":b["closed_trades"]>=MIN_CLOSED_PER_ARM,
        "challenger_min_closes":c["closed_trades"]>=MIN_CLOSED_PER_ARM,
        "baseline_min_symbols":b["distinct_symbols"]>=MIN_DISTINCT_SYMBOLS,
        "challenger_min_symbols":c["distinct_symbols"]>=MIN_DISTINCT_SYMBOLS,
        "baseline_min_days":b["forward_calendar_days"]>=MIN_FORWARD_DAYS,
        "challenger_min_days":c["forward_calendar_days"]>=MIN_FORWARD_DAYS,
        "baseline_symbol_concentration":b["max_single_symbol_share"] is not None and b["max_single_symbol_share"]<=MAX_SINGLE_SYMBOL_SHARE,
        "challenger_symbol_concentration":c["max_single_symbol_share"] is not None and c["max_single_symbol_share"]<=MAX_SINGLE_SYMBOL_SHARE,
    }
    evidence_ready=all(minimums.values())
    performance={
        "challenger_positive_expectancy": evidence_ready and c["expectancy_r_after_recorded_costs"] is not None and c["expectancy_r_after_recorded_costs"]>0,
        "challenger_beats_baseline_expectancy": evidence_ready and c["expectancy_r_after_recorded_costs"]>b["expectancy_r_after_recorded_costs"],
        "challenger_drawdown_not_worse": evidence_ready and c["max_drawdown_r"]<=b["max_drawdown_r"],
        "challenger_worst_trade_gate": evidence_ready and c["worst_trade_r"]>=-MAX_EXTREME_LOSS_R,
    }
    return {"status":"READY_FOR_GATE_EVALUATION" if evidence_ready else "NOT_READY",
            "minimum_evidence_gates":minimums,"performance_gates":performance,
            "baseline":b,"challenger":c,"promotion_allowed":False}


def e29_forward_scorecard(*, rows=None, membership_path=MEMBERSHIP_PATH):
    source=list(iter_jsonl(JOURNAL_PATH)) if rows is None else list(rows)
    memberships,added=sync_membership(source,membership_path)
    score=build_scorecard(source,memberships)
    return {"ok":True,"title":"ATLAS E29 FORWARD BASELINE VS CHALLENGER SCORECARD",
            "scorecard_version":SCORECARD_VERSION,"challenger_version":CHALLENGER_VERSION,
            "freeze_start_utc":FREEZE_START_UTC,"membership_path":str(membership_path),
            "membership_records":len(memberships),"membership_records_added":added,
            **score,"e27_acceptance_gate_unchanged":True,"thresholds_mutable":False,
            "historical_rows_count_as_prospective":False,"membership_classified_from_close":False,
            "production_strategy_modified":False,"live_capital_allowed":False,
            "automatic_real_money_execution":False}