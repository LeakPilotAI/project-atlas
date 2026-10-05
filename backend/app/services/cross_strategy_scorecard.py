"""Read-only cross-strategy PAPER evidence health scorecard.

The lanes intentionally retain their native accounting semantics. No universal
win-rate or expectancy is calculated because R-multiples, long-horizon equity
returns, and prediction-market dollar repricing are not interchangeable.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

from app.investment.quality_dips_paper import portfolio_snapshot
from app.investment.storage import QUALITY_DIPS_PAPER_JOURNAL_PATH
from app.prediction.paper_engine import JOURNAL_PATH as PREDICTION_JOURNAL_PATH, prediction_paper_journal
from app.services.edge_diagnostics import load_paper_closes_safe
from app.services.paper_journal import JOURNAL_PATH as DAY_JOURNAL_PATH
from app.services.paper_validation import metrics

SCORECARD_VERSION = "cross-strategy-evidence-health-v3"


def _journal_integrity(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {"status": "MISSING_EMPTY", "readable_records": 0, "malformed_records": 0, "last_durable_evidence_at": None}
    readable = malformed = 0
    latest = None
    try:
        with path.open(encoding="utf-8") as stream:
            for raw in stream:
                if not raw.strip():
                    continue
                try:
                    row = json.loads(raw)
                    if not isinstance(row, dict):
                        raise ValueError("non-object JSONL row")
                    readable += 1
                    candidate = _dt(row.get("exit_timestamp") or row.get("timestamp") or row.get("entry_timestamp"))
                    if candidate is not None and (latest is None or candidate > latest):
                        latest = candidate
                except Exception:
                    malformed += 1
    except OSError:
        return {"status": "UNREADABLE", "readable_records": 0, "malformed_records": None, "last_durable_evidence_at": None}
    return {"status": "OK" if malformed == 0 else "PARTIAL", "readable_records": readable, "malformed_records": malformed, "last_durable_evidence_at": latest.isoformat() if latest else None}


def _checkpoint(sample_size: int, freshness: Dict[str, Any], previous: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    prior = previous or {}
    prior_n = prior.get("sample_size")
    movement = "BASELINE" if prior_n is None else ("GROWING" if sample_size > int(prior_n) else "UNCHANGED" if sample_size == int(prior_n) else "RECONSTRUCTION_WARNING")
    return {"sample_size": sample_size, "latest_evidence_at": freshness.get("latest_evidence_at"), "age_hours": freshness.get("age_hours"), "movement": movement, "performance_interpretation": None}


def _dt(value: Any) -> Optional[datetime]:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None


def _freshness(rows: Iterable[Dict[str, Any]], keys: tuple[str, ...]) -> Dict[str, Any]:
    timestamps = []
    for row in rows:
        for key in keys:
            parsed = _dt(row.get(key))
            if parsed is not None:
                timestamps.append(parsed)
                break
    latest = max(timestamps) if timestamps else None
    age_hours = None
    if latest is not None:
        age_hours = max(0.0, (datetime.now(timezone.utc) - latest).total_seconds() / 3600.0)
    return {
        "latest_evidence_at": latest.isoformat() if latest else None,
        "age_hours": round(age_hours, 2) if age_hours is not None else None,
        "timestamp_coverage": round(len(timestamps) / max(1, len(list(rows))), 4),
    }


def _evidence_health(sample_size: int, freshness: Dict[str, Any]) -> Dict[str, Any]:
    coverage = float(freshness.get("timestamp_coverage") or 0.0)
    age = freshness.get("age_hours")
    if sample_size <= 0:
        band, reason = "NO_EVIDENCE", "No closed sample exists."
    elif coverage < 0.8:
        band, reason = "LIMITED", "Timestamp coverage is below 80%."
    elif age is None:
        band, reason = "LIMITED", "Evidence freshness cannot be established."
    elif age > 720:
        band, reason = "STALE", "Newest evidence is older than 30 days."
    elif sample_size < 20:
        band, reason = "THIN", "Fewer than 20 closed observations."
    elif sample_size < 50:
        band, reason = "DEVELOPING", "20-49 closed observations."
    else:
        band, reason = "SUBSTANTIAL", "At least 50 closed observations with usable timestamp coverage."
    return {
        "band": band,
        "reason": reason,
        "interpretation_only": True,
        "strategy_action": None,
        "threshold_change": None,
        "sizing_change": None,
        "promotion_allowed": False,
    }


def build_cross_strategy_scorecard(
    *,
    day_rows: Optional[list[Dict[str, Any]]] = None,
    investment_snapshot: Optional[Dict[str, Any]] = None,
    prediction_snapshot: Optional[Dict[str, Any]] = None,
    malformed_day_rows: int = 0,
    previous_checkpoints: Optional[Dict[str, Dict[str, Any]]] = None,
    integrity: Optional[Dict[str, Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    if day_rows is None:
        day_rows, malformed, _counts = load_paper_closes_safe()
        malformed_day_rows = len(malformed)
    investment = investment_snapshot if investment_snapshot is not None else portfolio_snapshot()
    prediction = prediction_snapshot if prediction_snapshot is not None else prediction_paper_journal.snapshot(limit=1000)
    previous_checkpoints = previous_checkpoints or {}
    integrity = integrity or {
        "DAY_TRADING": _journal_integrity(DAY_JOURNAL_PATH),
        "INVESTMENT_QUALITY_DIPS_V1": _journal_integrity(QUALITY_DIPS_PAPER_JOURNAL_PATH),
        "PREDICTION": _journal_integrity(PREDICTION_JOURNAL_PATH),
    }

    day = metrics(day_rows)
    inv_summary = investment.get("summary") or {}
    pred_summary = prediction.get("summary") or {}
    inv_events = list(investment.get("timeline") or [])
    pred_events = list(prediction.get("events") or [])

    day_fresh = _freshness(day_rows, ("exit_timestamp", "timestamp", "entry_timestamp"))
    inv_fresh = _freshness(inv_events, ("timestamp",))
    pred_fresh = _freshness(pred_events, ("timestamp", "observed_at", "created_at"))

    day_closed = int(day.get("n") or 0)
    inv_closed = int(inv_summary.get("closed_lots") or 0)
    inv_open = int(inv_summary.get("open_lots") or 0)
    pred_closed = int(pred_summary.get("closed_trades") or 0)
    pred_open = int(pred_summary.get("open_positions") or 0)

    lanes = [
        {
            "lane": "DAY_TRADING",
            "accounting_unit": "R_MULTIPLE",
            "sample_size": day_closed,
            "open_sample_size": 0,
            "realized_status": "AVAILABLE" if day_closed else "NO_CLOSED_SAMPLE",
            "unrealized_status": "NOT_APPLICABLE",
            "expectancy": day.get("expectancy") if day_closed else None,
            "expectancy_unit": "R_PER_CLOSED_TRADE",
            "win_rate": day.get("winrate") if day_closed else None,
            "freshness": day_fresh,
            "evidence_health": _evidence_health(day_closed, day_fresh),
            "evidence_checkpoint": _checkpoint(day_closed, day_fresh, previous_checkpoints.get("DAY_TRADING")),
            "journal_integrity": integrity.get("DAY_TRADING", {"status": "UNKNOWN"}),
            "coverage": {
                "malformed_records": int(malformed_day_rows),
                "finite_closed_records": day_closed,
            },
            "provenance": {
                "durable_source": "DAY_TRADING_PAPER_JOURNAL",
                "record_class": "paper_close",
                "metric_basis": "finite closed PAPER trades only",
                "reconstruction": "append-only journal -> validated closes -> R metrics",
            }
        },
        {
            "lane": "INVESTMENT_QUALITY_DIPS_V1",
            "accounting_unit": "DOLLARS_AND_PERCENT_RETURN",
            "sample_size": inv_closed,
            "open_sample_size": inv_open,
            "realized_status": "AVAILABLE" if inv_closed else "NO_CLOSED_SAMPLE",
            "unrealized_status": "AVAILABLE" if inv_open else "NO_OPEN_SAMPLE",
            "expectancy": (
                round(sum(float(x.get("realized_return_pct") or 0.0) for x in investment.get("closed_lots") or []) / inv_closed, 8)
                if inv_closed else None
            ),
            "expectancy_unit": "MEAN_REALIZED_RETURN_PCT_PER_CLOSED_LOT",
            "win_rate": (
                round(sum(float(x.get("realized_pnl") or 0.0) > 0 for x in investment.get("closed_lots") or []) / inv_closed, 4)
                if inv_closed else None
            ),
            "freshness": inv_fresh,
            "evidence_health": _evidence_health(inv_closed, inv_fresh),
            "evidence_checkpoint": _checkpoint(inv_closed, inv_fresh, previous_checkpoints.get("INVESTMENT_QUALITY_DIPS_V1")),
            "journal_integrity": integrity.get("INVESTMENT_QUALITY_DIPS_V1", {"status": "UNKNOWN"}),
            "coverage": {
                "lifecycle_events": len(inv_events),
                "paper_policy_version": investment.get("paper_policy_version"),
            },
            "provenance": {
                "durable_source": "QUALITY_DIPS_PAPER_V1_JOURNAL",
                "record_class": "open_lot/mark_lot/close_lot",
                "metric_basis": "terminally closed prospective V1 lots only",
                "reconstruction": "append-only lifecycle journal -> portfolio snapshot",
            }
        },
        {
            "lane": "PREDICTION",
            "accounting_unit": "NET_REPRICING_DOLLARS",
            "sample_size": pred_closed,
            "open_sample_size": pred_open,
            "realized_status": "AVAILABLE" if pred_closed else "NO_CLOSED_SAMPLE",
            "unrealized_status": "OPEN_POSITION_PRESENT" if pred_open else "NO_OPEN_SAMPLE",
            "expectancy": (
                round(float(pred_summary.get("net_pnl_dollars") or 0.0) / pred_closed, 8)
                if pred_closed else None
            ),
            "expectancy_unit": "NET_DOLLARS_PER_CLOSED_REPRICING_TRADE",
            "win_rate": pred_summary.get("win_rate") if pred_closed else None,
            "freshness": pred_fresh,
            "evidence_health": _evidence_health(pred_closed, pred_fresh),
            "evidence_checkpoint": _checkpoint(pred_closed, pred_fresh, previous_checkpoints.get("PREDICTION")),
            "journal_integrity": integrity.get("PREDICTION", {"status": "UNKNOWN"}),
            "coverage": {
                "journal_events": len(pred_events),
                "expired_unclosed_trades": int(pred_summary.get("expired_unclosed_trades") or 0),
                "engine_version": prediction.get("engine_version"),
            },
            "provenance": {
                "durable_source": "PREDICTION_PAPER_TRADE_JOURNAL",
                "record_class": "entry/expired_unclosed/close",
                "metric_basis": "depth/fee-aware closed PAPER repricing trades only",
                "reconstruction": "isolated prediction journal -> PAPER snapshot",
            }
        },
    ]

    return {
        "title": "ATLAS CROSS-STRATEGY PAPER EVIDENCE HEALTH",
        "scorecard_version": SCORECARD_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "lanes": lanes,
        "comparison_rules": {
            "universal_win_rate": None,
            "universal_expectancy": None,
            "pool_lane_pnl": False,
            "native_accounting_units_preserved": True,
            "thin_samples_are_proof": False,
            "missing_metrics_are_zero": False,
            "evidence_health_is_strategy_action": False,
            "thresholds_modified": False,
            "production_strategy_modified": False,
        },
        "execution": "READ_ONLY_PAPER_RESEARCH",
        "live_capital_allowed": False,
        "automatic_real_money_execution": False,
    }


def cross_strategy_scorecard() -> Dict[str, Any]:
    """Build each lane defensively so one damaged journal cannot contaminate peers."""
    day_rows, malformed, _counts = load_paper_closes_safe()
    integrity = {
        "DAY_TRADING": _journal_integrity(DAY_JOURNAL_PATH),
        "INVESTMENT_QUALITY_DIPS_V1": _journal_integrity(QUALITY_DIPS_PAPER_JOURNAL_PATH),
        "PREDICTION": _journal_integrity(PREDICTION_JOURNAL_PATH),
    }
    try:
        investment = portfolio_snapshot()
    except Exception:
        investment = {"paper_policy_version": "QUALITY_DIPS_PAPER_V1", "summary": {"open_lots": 0, "closed_lots": 0}, "closed_lots": [], "timeline": []}
        integrity["INVESTMENT_QUALITY_DIPS_V1"]["reconstruction_status"] = "FAILED_ISOLATED"
    try:
        prediction = prediction_paper_journal.snapshot(limit=1000)
    except Exception:
        prediction = {"engine_version": None, "summary": {"open_positions": 0, "closed_trades": 0, "net_pnl_dollars": 0.0}, "events": []}
        integrity["PREDICTION"]["reconstruction_status"] = "FAILED_ISOLATED"
    for lane in integrity.values():
        lane.setdefault("reconstruction_status", "OK" if lane.get("status") in {"OK", "MISSING_EMPTY"} else "PARTIAL")
    return build_cross_strategy_scorecard(day_rows=day_rows, malformed_day_rows=len(malformed), investment_snapshot=investment, prediction_snapshot=prediction, integrity=integrity)
