"""Read-only Archive APIs for investment research/PAPER history.

This surface never places broker orders and never rewrites investment or trading
journals. Investment history is intentionally honest about the current book:
Atlas records accumulation fills/open positions, but does not currently record
closed long-horizon investment exits suitable for realized win-rate/P&L claims.
"""
from __future__ import annotations

import asyncio
import csv
import hashlib
import io
import json
from collections import Counter, deque
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

from app.investment.daily_research_plan import PLAN_PATH
from app.investment.history import load_bars
from app.investment.paper_book import PaperBook
from app.investment.storage import (
    LEDGER_PATH,
    OPPORTUNITIES_PATH,
    PAPER_STATE_PATH,
    SNAPSHOTS_PATH,
    UNIVERSE_PATH,
)
from app.services.paper_journal import JOURNAL_PATH

router = APIRouter(prefix="/api/archive", tags=["archive"])


def _tail_jsonl(path: Path, limit: int) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: deque[dict[str, Any]] = deque(maxlen=max(1, int(limit)))
    try:
        with path.open("r", encoding="utf-8") as handle:
            for raw in handle:
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    row = json.loads(raw)
                except Exception:
                    continue
                if isinstance(row, dict):
                    rows.append(row)
    except OSError:
        return []
    return list(rows)


def _event_row(row: dict[str, Any]) -> dict[str, Any]:
    kind = str(row.get("kind") or "UNKNOWN").upper()
    price = row.get("price")
    if price is None:
        price = row.get("limit")
    shares = row.get("shares")
    usd = row.get("usd")
    if usd is None and isinstance(price, (int, float)) and isinstance(shares, (int, float)):
        usd = float(price) * float(shares)
    status = {
        "RESEARCH_BUY": "PAPER_FILLED",
        "FILL": "PAPER_FILLED",
        "ORDER": "OPEN_LIMIT",
        "CANCEL": "CANCELLED",
    }.get(kind, kind)
    return {
        "at": row.get("at"),
        "symbol": row.get("symbol"),
        "event": kind,
        "status": status,
        "price": price,
        "shares": shares,
        "usd": usd,
        "reason": row.get("reason"),
        "session": row.get("session"),
        "order_id": row.get("order_id"),
        # The current investment paper book does not implement closed long-horizon
        # exits, so realized exit/return fields must stay unavailable.
        "exit_price": None,
        "realized_return_pct": None,
        "realized_pnl": None,
        "hold_time": None,
    }


def _build_investment_history(limit: int) -> Dict[str, Any]:
    book = PaperBook.load(PAPER_STATE_PATH)
    snapshot = book.snapshot()
    ledger = _tail_jsonl(LEDGER_PATH, limit)
    plans = _tail_jsonl(PLAN_PATH, min(limit, 120))

    positions = []
    for symbol, row in (snapshot.get("positions") or {}).items():
        shares = float(row.get("shares") or 0.0)
        avg_cost = float(row.get("avg_cost") or 0.0)
        market_price = float(row.get("market_price") or 0.0)
        market_value = float(row.get("value") or 0.0)
        cost_basis = shares * avg_cost
        unrealized = market_value - cost_basis
        return_pct = ((market_price / avg_cost) - 1.0) * 100.0 if avg_cost > 0 and market_price > 0 else None
        positions.append(
            {
                "symbol": str(symbol),
                "shares": shares,
                "avg_cost": avg_cost,
                "market_price": market_price,
                "market_value": market_value,
                "cost_basis": cost_basis,
                "unrealized_pnl": unrealized,
                "unrealized_return_pct": return_pct,
                "status": "OPEN_PAPER_INVESTMENT",
            }
        )
    positions.sort(key=lambda row: abs(float(row.get("market_value") or 0.0)), reverse=True)

    events = [_event_row(row) for row in reversed(ledger)]
    fill_count = sum(1 for row in ledger if str(row.get("kind") or "").lower() in {"fill", "research_buy"})
    open_orders = int(snapshot.get("open_orders") or 0)
    latest_plan = plans[-1] if plans else None

    return {
        "domain": "INVESTMENT_ARCHIVE",
        "execution": "PAPER_RESEARCH_ONLY",
        "live_capital_allowed": False,
        "automatic_real_money_execution": False,
        "summary": {
            "open_positions": len(positions),
            "paper_fills": fill_count,
            "ledger_events": len(ledger),
            "portfolio_value": snapshot.get("portfolio_value"),
            "cash": snapshot.get("cash"),
            "invested": snapshot.get("invested"),
            "unrealized_pnl": snapshot.get("unrealized_pnl"),
            "realized_pnl": snapshot.get("realized_pnl"),
            "drawdown": snapshot.get("drawdown"),
            "open_orders": open_orders,
            "closed_investment_positions": None,
            "win_rate": None,
            "average_realized_return": None,
            "realized_performance_supported": False,
        },
        "positions": positions,
        "events": events,
        "daily_plan_history": list(reversed(plans)),
        "latest_daily_plan": latest_plan,
        "capabilities": {
            "paper_accumulation_fills": True,
            "open_position_marking": True,
            "closed_long_horizon_investment_exits": False,
            "realized_investment_win_rate": False,
            "realized_investment_return_series": False,
            "broker_history": False,
        },
        "note": (
            "Investment Archive is read-only. Atlas currently records simulated "
            "accumulation fills/open positions and daily research plans, but not "
            "closed long-horizon investment exits. Realized win rate, realized "
            "returns and closed-position charts therefore remain unavailable."
        ),
    }


@router.get("/investment-history")
async def investment_history(limit: int = Query(300, ge=25, le=1000)) -> Dict[str, Any]:
    return await asyncio.to_thread(_build_investment_history, limit)


@router.get("/investment-history/{symbol}/bars")
async def investment_history_bars(
    symbol: str,
    limit: int = Query(120, ge=20, le=400),
) -> Dict[str, Any]:
    safe = "".join(ch for ch in str(symbol).upper() if ch.isalnum() or ch in ".-^")[:20]
    if not safe:
        return {
            "symbol": "",
            "bars": [],
            "source": "investment_daily_history",
            "execution": "READ_ONLY",
        }
    bars = await asyncio.to_thread(load_bars, safe)
    selected = bars[-limit:]
    return {
        "symbol": safe,
        "bars": [
            {
                "date": bar.session_date,
                "open": bar.open,
                "high": bar.high,
                "low": bar.low,
                "close": bar.close,
                "volume": bar.volume,
                "quality": bar.quality,
                "issues": list(bar.issues or []),
            }
            for bar in selected
        ],
        "source": "investment_daily_history",
        "execution": "READ_ONLY",
        "live_capital_allowed": False,
    }


# --------------------------------
# Read-only Hyperliquid PAPER archive
# --------------------------------

def _paper_trade_setup(row: dict[str, Any]) -> str:
    features = row.get("features") if isinstance(row.get("features"), dict) else {}
    return str(
        row.get("setup_type")
        or features.get("setup_type")
        or row.get("strategy")
        or row.get("source")
        or row.get("exit_mode")
        or "UNKNOWN"
    ).upper()


def _paper_trade_r(row: dict[str, Any]) -> float:
    raw = row.get("net_pnl_r")
    if raw is None:
        raw = row.get("R_multiple")
    try:
        return float(raw or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _paper_close_time(row: dict[str, Any]) -> datetime | None:
    for key in ("exit_timestamp", "timestamp", "entry_timestamp"):
        raw = row.get(key)
        if not raw:
            continue
        try:
            value = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
            if value.tzinfo is None:
                value = value.replace(tzinfo=timezone.utc)
            return value.astimezone(timezone.utc)
        except Exception:
            continue
    return None


def _eligible_paper_close(row: dict[str, Any]) -> bool:
    if str(row.get("event") or "").lower() != "close":
        return False
    if str(row.get("trade_type") or "PAPER").upper() == "TEST":
        return False
    if bool(row.get("session_roll")):
        return False
    if str(row.get("result") or "").upper() in {"SESSION_ROLL", "INTERRUPTED"}:
        return False
    return True


def _paper_trade_row(row: dict[str, Any]) -> dict[str, Any]:
    r = _paper_trade_r(row)
    scratch = bool(row.get("scratch")) or str(row.get("result") or "").upper() in {"BE", "SCRATCH"} or abs(r) < 1e-12
    status = "SCRATCH" if scratch else ("WIN" if r > 0 else "LOSS")
    entry = row.get("actual_entry_price")
    if entry is None:
        entry = row.get("entry")
    exit_price = row.get("actual_exit_price")
    return {
        "trade_id": row.get("trade_id"),
        "entry_timestamp": row.get("entry_timestamp") or row.get("signal_timestamp"),
        "exit_timestamp": row.get("exit_timestamp") or row.get("timestamp"),
        "symbol": str(row.get("symbol") or "").upper(),
        "setup": _paper_trade_setup(row),
        "direction": str(row.get("side") or "UNKNOWN").upper(),
        "entry": entry,
        "exit": exit_price,
        "stop": row.get("initial_stop") if row.get("initial_stop") is not None else row.get("stop_price"),
        "target": row.get("working_target") if row.get("working_target") is not None else row.get("tp1_price"),
        "r": round(r, 4),
        "gross_r": row.get("gross_pnl_r"),
        "result": row.get("result"),
        "status": status,
        "exit_reason": row.get("exit_reason"),
        "notes": row.get("notes") or row.get("exit_reason") or "",
        "risk_dollars": row.get("risk_dollars"),
        "position_size": row.get("position_size"),
        "holding_time_sec": row.get("holding_time_sec") or row.get("duration_sec"),
        "mfe_r": row.get("mfe_r"),
        "mae_r": row.get("mae_r"),
        "exit_mode": row.get("exit_mode"),
        "strategy": row.get("strategy"),
        "adaptive_stage": row.get("adaptive_stage"),
        "adaptive_exit_policy_version": row.get("adaptive_exit_policy_version"),
        "counts_for_live": bool(row.get("counts_for_live")),
    }


def _paper_filtered_rows(
    *,
    date_range: str = "all",
    symbol: str = "",
    setup: str = "",
) -> list[dict[str, Any]]:
    rows = [row for row in _read_dataset(JOURNAL_PATH) if _eligible_paper_close(row)]
    token = str(date_range or "all").lower()
    days = {"30d": 30, "90d": 90, "365d": 365}.get(token)
    cutoff = datetime.now(timezone.utc) - timedelta(days=days) if days else None
    sym = str(symbol or "").upper().strip()
    setup_token = str(setup or "").upper().strip()
    selected = []
    for row in rows:
        if cutoff is not None:
            ts = _paper_close_time(row)
            if ts is not None and ts < cutoff:
                continue
        if sym and str(row.get("symbol") or "").upper() != sym:
            continue
        if setup_token and _paper_trade_setup(row) != setup_token:
            continue
        selected.append(row)
    selected.sort(key=lambda row: _paper_close_time(row) or datetime.min.replace(tzinfo=timezone.utc))
    return selected


def _paper_archive_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    mapped = [_paper_trade_row(row) for row in rows]
    wins = [row for row in mapped if row["status"] == "WIN"]
    losses = [row for row in mapped if row["status"] == "LOSS"]
    scratches = [row for row in mapped if row["status"] == "SCRATCH"]
    total = len(mapped)
    sum_r = sum(float(row["r"]) for row in mapped)
    avg_r = sum_r / total if total else 0.0
    avg_win = sum(float(row["r"]) for row in wins) / len(wins) if wins else 0.0
    avg_loss = sum(float(row["r"]) for row in losses) / len(losses) if losses else 0.0
    profit_factor = (
        sum(float(row["r"]) for row in wins) / abs(sum(float(row["r"]) for row in losses))
        if losses and abs(sum(float(row["r"]) for row in losses)) > 1e-12
        else None
    )

    cumulative = 0.0
    peak = 0.0
    max_drawdown = 0.0
    equity_curve = []
    daily: dict[str, float] = {}
    win_series = []
    running_wins = 0
    consec_wins = consec_losses = max_consec_wins = max_consec_losses = 0
    for idx, row in enumerate(mapped, start=1):
        r = float(row["r"])
        cumulative += r
        peak = max(peak, cumulative)
        max_drawdown = min(max_drawdown, cumulative - peak)
        ts = row.get("exit_timestamp")
        day = str(ts or "")[:10] or f"trade-{idx}"
        daily[day] = daily.get(day, 0.0) + r
        if row["status"] == "WIN":
            running_wins += 1
            consec_wins += 1
            consec_losses = 0
        elif row["status"] == "LOSS":
            consec_losses += 1
            consec_wins = 0
        else:
            consec_wins = 0
            consec_losses = 0
        max_consec_wins = max(max_consec_wins, consec_wins)
        max_consec_losses = max(max_consec_losses, consec_losses)
        win_series.append(round(running_wins / idx, 4))
        equity_curve.append(
            {
                "index": idx,
                "timestamp": ts,
                "cumulative_r": round(cumulative, 4),
                "drawdown_r": round(cumulative - peak, 4),
                "win_rate": win_series[-1],
            }
        )

    def breakdown(key: str) -> list[dict[str, Any]]:
        grouped: dict[str, list[dict[str, Any]]] = {}
        for row in mapped:
            grouped.setdefault(str(row.get(key) or "UNKNOWN"), []).append(row)
        out = []
        for name, items in grouped.items():
            n = len(items)
            w = sum(1 for row in items if row["status"] == "WIN")
            out.append(
                {
                    key: name,
                    "trades": n,
                    "wins": w,
                    "losses": sum(1 for row in items if row["status"] == "LOSS"),
                    "scratches": sum(1 for row in items if row["status"] == "SCRATCH"),
                    "win_rate": round(w / n, 4) if n else 0.0,
                    "sum_r": round(sum(float(row["r"]) for row in items), 4),
                    "avg_r": round(sum(float(row["r"]) for row in items) / n, 4) if n else 0.0,
                }
            )
        return sorted(out, key=lambda item: (-int(item["trades"]), str(item.get(key))))

    best = max(mapped, key=lambda row: float(row["r"]), default=None)
    worst = min(mapped, key=lambda row: float(row["r"]), default=None)
    symbols = sorted({row["symbol"] for row in mapped if row["symbol"]})
    setups = sorted({row["setup"] for row in mapped if row["setup"]})
    return {
        "total": total,
        "wins": len(wins),
        "losses": len(losses),
        "scratches": len(scratches),
        "win_rate": round(len(wins) / total, 4) if total else 0.0,
        "sum_r": round(sum_r, 4),
        "avg_r": round(avg_r, 4),
        "avg_win_r": round(avg_win, 4),
        "avg_loss_r": round(avg_loss, 4),
        "profit_factor": round(profit_factor, 4) if profit_factor is not None else None,
        "max_drawdown_r": round(max_drawdown, 4),
        "max_consecutive_wins": max_consec_wins,
        "max_consecutive_losses": max_consec_losses,
        "best_trade": best,
        "worst_trade": worst,
        "by_setup": breakdown("setup"),
        "by_direction": breakdown("direction"),
        "symbols": symbols,
        "setups": setups,
        "equity_curve": equity_curve,
        "daily_r": [{"date": day, "r": round(value, 4)} for day, value in sorted(daily.items())],
    }


def _build_paper_trades_archive(
    *,
    date_range: str,
    symbol: str,
    setup: str,
    limit: int,
) -> dict[str, Any]:
    rows = _paper_filtered_rows(date_range=date_range, symbol=symbol, setup=setup)
    summary = _paper_archive_summary(rows)
    trades = [_paper_trade_row(row) for row in reversed(rows[-limit:])]
    return {
        "domain": "PAPER_TRADE_ARCHIVE",
        "execution": "PAPER_ONLY",
        "live_capital_allowed": False,
        "automatic_real_money_execution": False,
        "filters": {
            "date_range": date_range,
            "symbol": symbol or "ALL",
            "setup": setup or "ALL",
        },
        "summary": summary,
        "trades": trades,
        "note": (
            "Closed Hyperliquid PAPER trades only. TEST, SESSION_ROLL and INTERRUPTED "
            "rows are excluded from performance statistics."
        ),
    }


@router.get("/paper-trades")
async def paper_trades_archive(
    date_range: str = Query("all"),
    symbol: str = Query(""),
    setup: str = Query(""),
    limit: int = Query(500, ge=25, le=2000),
) -> Dict[str, Any]:
    return await asyncio.to_thread(
        _build_paper_trades_archive,
        date_range=date_range,
        symbol=symbol,
        setup=setup,
        limit=limit,
    )


@router.get("/paper-trades/{trade_id}")
async def paper_trade_detail(trade_id: str) -> Dict[str, Any]:
    requested = str(trade_id or "").strip()
    if not requested:
        raise HTTPException(status_code=404, detail="Paper trade not found")
    events = [
        row
        for row in _read_dataset(JOURNAL_PATH)
        if str(row.get("trade_id") or "") == requested
        and str(row.get("trade_type") or "PAPER").upper() != "TEST"
    ]
    if not events:
        raise HTTPException(status_code=404, detail="Paper trade not found")
    open_row = next((row for row in events if str(row.get("event") or "").lower() == "open"), {})
    close_row = next((row for row in reversed(events) if str(row.get("event") or "").lower() == "close"), {})
    source = close_row or open_row
    marks = []
    for row in events:
        event = str(row.get("event") or "").lower()
        if event == "open":
            price = row.get("actual_entry_price")
            timestamp = row.get("entry_timestamp") or row.get("timestamp")
        elif event == "mark":
            price = row.get("mark")
            timestamp = row.get("timestamp")
        elif event == "close":
            price = row.get("actual_exit_price")
            timestamp = row.get("exit_timestamp") or row.get("timestamp")
        else:
            continue
        try:
            price_value = float(price)
        except (TypeError, ValueError):
            continue
        marks.append(
            {
                "event": event.upper(),
                "timestamp": timestamp,
                "price": price_value,
                "mfe_r": row.get("mfe_r"),
                "mae_r": row.get("mae_r"),
                "adaptive_stage": row.get("adaptive_stage"),
                "working_stop": row.get("working_stop"),
                "working_target": row.get("working_target"),
            }
        )
    return {
        "trade": _paper_trade_row(source) if close_row else {
            **_paper_trade_row({**open_row, "event": "close", "result": "OPEN"}),
            "status": "OPEN",
        },
        "marks": marks,
        "event_count": len(events),
        "execution": "PAPER_ONLY",
        "live_capital_allowed": False,
    }


# --------------------------------
# Read-only investment research archive
# --------------------------------

def _research_record_id(row: dict[str, Any]) -> str:
    raw = "|".join(
        [
            str(row.get("timestamp") or ""),
            str(row.get("symbol") or ""),
            str(row.get("scoring_version") or ""),
            str(row.get("classification") or ""),
        ]
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _research_sector(row: dict[str, Any]) -> str:
    snap = row.get("input_snapshot") if isinstance(row.get("input_snapshot"), dict) else {}
    asset = snap.get("asset") if isinstance(snap.get("asset"), dict) else {}
    return str(asset.get("sector") or "").strip()


def _research_name(row: dict[str, Any]) -> str:
    value = str(row.get("name") or "").strip()
    if value:
        return value
    snap = row.get("input_snapshot") if isinstance(row.get("input_snapshot"), dict) else {}
    asset = snap.get("asset") if isinstance(snap.get("asset"), dict) else {}
    return str(asset.get("name") or "").strip()


def _research_ts(row: dict[str, Any]) -> datetime | None:
    raw = row.get("timestamp")
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except Exception:
        return None


def _research_archive_row(row: dict[str, Any]) -> dict[str, Any]:
    explain = row.get("explain") if isinstance(row.get("explain"), dict) else {}
    components = row.get("components") if isinstance(row.get("components"), dict) else {}
    drawdown = row.get("drawdown") if isinstance(row.get("drawdown"), dict) else {}
    score = row.get("opportunity_score")
    try:
        score = int(score) if score is not None else None
    except (TypeError, ValueError):
        score = None
    return {
        "record_id": _research_record_id(row),
        "timestamp": row.get("timestamp"),
        "symbol": str(row.get("symbol") or "").upper(),
        "name": _research_name(row),
        "asset_type": str(row.get("asset_type") or "UNKNOWN").upper(),
        "sector": _research_sector(row),
        "classification": str(row.get("classification") or "UNKNOWN").upper(),
        "opportunity_score": score,
        "evidence_quality": str(row.get("evidence_quality") or "UNKNOWN").upper(),
        "thesis": str(row.get("thesis") or "UNKNOWN").upper(),
        "price": row.get("price"),
        "scoring_version": row.get("scoring_version"),
        "coverage_label": row.get("coverage_label"),
        "components": components,
        "drawdown": drawdown,
        "why_this_asset": list(explain.get("why_this_asset") or []),
        "why_interesting": list(explain.get("why_interesting") or []),
        "why_now": list(explain.get("why_now") or []),
        "supports_thesis": list(explain.get("supports_thesis") or []),
        "weakens_thesis": list(explain.get("weakens_thesis") or []),
        "missing_data": list(explain.get("missing_data") or row.get("missing_critical") or []),
        "invalidation": list(explain.get("invalidation") or []),
        "risks": list(explain.get("risks") or []),
        "data_quality_notes": list(explain.get("data_quality_notes") or []),
        "generational_blockers": list(row.get("generational_blockers") or []),
        "disclaimer": row.get("disclaimer"),
    }


def _research_filtered_rows(
    *,
    date_range: str = "all",
    asset_type: str = "",
    sector: str = "",
    classification: str = "",
    evidence: str = "",
    thesis: str = "",
    scoring_version: str = "",
    search: str = "",
) -> list[dict[str, Any]]:
    rows = _read_dataset(OPPORTUNITIES_PATH)
    token = str(date_range or "all").lower()
    days = {"30d": 30, "90d": 90, "365d": 365}.get(token)
    cutoff = datetime.now(timezone.utc) - timedelta(days=days) if days else None
    a = str(asset_type or "").upper().strip()
    sec = str(sector or "").upper().strip()
    cls = str(classification or "").upper().strip()
    ev = str(evidence or "").upper().strip()
    th = str(thesis or "").upper().strip()
    ver = str(scoring_version or "").strip()
    q = str(search or "").upper().strip()
    selected = []
    for row in rows:
        if cutoff is not None:
            ts = _research_ts(row)
            if ts is not None and ts < cutoff:
                continue
        mapped = _research_archive_row(row)
        if a and mapped["asset_type"] != a:
            continue
        if sec and mapped["sector"].upper() != sec:
            continue
        if cls and mapped["classification"] != cls:
            continue
        if ev and mapped["evidence_quality"] != ev:
            continue
        if th and mapped["thesis"] != th:
            continue
        if ver and str(mapped.get("scoring_version") or "") != ver:
            continue
        if q:
            haystack = " ".join(
                [
                    mapped["symbol"],
                    mapped["name"],
                    mapped["sector"],
                    mapped["classification"],
                    mapped["evidence_quality"],
                    mapped["thesis"],
                    " ".join(mapped["why_now"]),
                    " ".join(mapped["supports_thesis"]),
                    " ".join(mapped["risks"]),
                ]
            ).upper()
            if q not in haystack:
                continue
        selected.append(mapped)
    selected.sort(
        key=lambda row: (
            _research_ts(row) or datetime.min.replace(tzinfo=timezone.utc),
            str(row.get("symbol") or ""),
        )
    )
    return selected


def _build_research_archive(
    *,
    date_range: str,
    asset_type: str,
    sector: str,
    classification: str,
    evidence: str,
    thesis: str,
    scoring_version: str,
    search: str,
    limit: int,
) -> dict[str, Any]:
    rows = _research_filtered_rows(
        date_range=date_range,
        asset_type=asset_type,
        sector=sector,
        classification=classification,
        evidence=evidence,
        thesis=thesis,
        scoring_version=scoring_version,
        search=search,
    )
    symbols = sorted({row["symbol"] for row in rows if row["symbol"]})
    sectors = sorted({row["sector"] for row in rows if row["sector"]})
    asset_types = sorted({row["asset_type"] for row in rows if row["asset_type"]})
    classifications = sorted({row["classification"] for row in rows if row["classification"]})
    evidence_levels = sorted({row["evidence_quality"] for row in rows if row["evidence_quality"]})
    thesis_states = sorted({row["thesis"] for row in rows if row["thesis"]})
    versions = sorted({str(row["scoring_version"]) for row in rows if row.get("scoring_version")})

    class_counts = Counter(row["classification"] for row in rows)
    sector_counts = Counter(row["sector"] or "UNCLASSIFIED" for row in rows)
    evidence_counts = Counter(row["evidence_quality"] for row in rows)
    monthly_counts = Counter(
        str(row.get("timestamp") or "")[:7]
        for row in rows
        if str(row.get("timestamp") or "")[:7]
    )

    scored = [row for row in rows if row.get("opportunity_score") is not None]
    top_scores = sorted(
        scored,
        key=lambda row: (
            int(row.get("opportunity_score") or 0),
            str(row.get("timestamp") or ""),
        ),
        reverse=True,
    )[:8]
    latest = max((str(row.get("timestamp") or "") for row in rows), default=None)
    high_evidence = sum(1 for row in rows if row.get("evidence_quality") == "HIGH")
    thesis_intact = sum(1 for row in rows if row.get("thesis") in {"STRONG", "INTACT"})

    return {
        "domain": "INVESTMENT_RESEARCH_ARCHIVE",
        "execution": "RESEARCH_ONLY",
        "live_capital_allowed": False,
        "automatic_real_money_execution": False,
        "summary": {
            "records": len(rows),
            "tracked_symbols": len(symbols),
            "classification_count": len(class_counts),
            "high_evidence_records": high_evidence,
            "intact_or_strong_thesis_records": thesis_intact,
            "last_updated": latest,
            "outcome_linkage_supported": False,
            "research_win_rate": None,
        },
        "filters": {
            "date_range": date_range,
            "asset_type": asset_type or "ALL",
            "sector": sector or "ALL",
            "classification": classification or "ALL",
            "evidence": evidence or "ALL",
            "thesis": thesis or "ALL",
            "scoring_version": scoring_version or "ALL",
            "search": search,
        },
        "facets": {
            "symbols": symbols,
            "sectors": sectors,
            "asset_types": asset_types,
            "classifications": classifications,
            "evidence_levels": evidence_levels,
            "thesis_states": thesis_states,
            "scoring_versions": versions,
        },
        "breakdowns": {
            "classification": [
                {"name": key, "count": count}
                for key, count in class_counts.most_common()
            ],
            "sector": [
                {"name": key, "count": count}
                for key, count in sector_counts.most_common()
            ],
            "evidence": [
                {"name": key, "count": count}
                for key, count in evidence_counts.most_common()
            ],
            "monthly_activity": [
                {"month": month, "count": monthly_counts[month]}
                for month in sorted(monthly_counts)
            ],
        },
        "top_research_scores": top_scores,
        "records": list(reversed(rows[-limit:])),
        "note": (
            "Append-only scored investment research records. Opportunity scores are ordinal "
            "research rankings, not probabilities, recommendations, or realized-return claims."
        ),
        "outcome_note": (
            "Atlas does not currently persist a one-to-one executed-outcome linkage for these "
            "research records, so research win rate and executed-idea performance remain unavailable."
        ),
    }


@router.get("/research-archive")
async def research_archive(
    date_range: str = Query("all"),
    asset_type: str = Query(""),
    sector: str = Query(""),
    classification: str = Query(""),
    evidence: str = Query(""),
    thesis: str = Query(""),
    scoring_version: str = Query(""),
    search: str = Query(""),
    limit: int = Query(500, ge=25, le=2000),
) -> Dict[str, Any]:
    return await asyncio.to_thread(
        _build_research_archive,
        date_range=date_range,
        asset_type=asset_type,
        sector=sector,
        classification=classification,
        evidence=evidence,
        thesis=thesis,
        scoring_version=scoring_version,
        search=search,
        limit=limit,
    )


@router.get("/research-archive/{record_id}")
async def research_archive_detail(record_id: str) -> Dict[str, Any]:
    requested = str(record_id or "").strip()
    for row in reversed(_read_dataset(OPPORTUNITIES_PATH)):
        if _research_record_id(row) == requested:
            return {
                "record": _research_archive_row(row),
                "execution": "RESEARCH_ONLY",
                "live_capital_allowed": False,
                "automatic_real_money_execution": False,
            }
    raise HTTPException(status_code=404, detail="Research record not found")


# -----------------------------
# Read-only investment snapshots
# -----------------------------

def _snapshot_record_id(row: dict[str, Any]) -> str:
    asset = row.get("asset") if isinstance(row.get("asset"), dict) else {}
    price = row.get("price") if isinstance(row.get("price"), dict) else {}
    raw = "|".join(
        [
            str(row.get("retrieved_at") or ""),
            str(asset.get("symbol") or row.get("symbol") or ""),
            str(price.get("source") or ""),
            str(price.get("value") or ""),
        ]
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _snapshot_ts(row: dict[str, Any]) -> datetime | None:
    raw = row.get("retrieved_at")
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except Exception:
        return None


def _measured_value(row: dict[str, Any] | None) -> Any:
    if not isinstance(row, dict):
        return None
    return row.get("value")


def _measured_quality(row: dict[str, Any] | None) -> str:
    if not isinstance(row, dict):
        return "UNKNOWN"
    return str(row.get("quality") or "UNKNOWN").upper()


def _measured_source(row: dict[str, Any] | None) -> str:
    if not isinstance(row, dict):
        return ""
    return str(row.get("source") or "").strip()


def _snapshot_archive_row(row: dict[str, Any]) -> dict[str, Any]:
    asset = row.get("asset") if isinstance(row.get("asset"), dict) else {}
    price = row.get("price") if isinstance(row.get("price"), dict) else {}
    market_cap = row.get("market_cap") if isinstance(row.get("market_cap"), dict) else {}
    latest_bar = row.get("latest_bar") if isinstance(row.get("latest_bar"), dict) else {}
    fundamentals = row.get("fundamentals") if isinstance(row.get("fundamentals"), dict) else {}
    valuation = row.get("valuation") if isinstance(row.get("valuation"), dict) else {}
    failures = row.get("failures") if isinstance(row.get("failures"), list) else []

    usable_fundamentals = sum(
        1
        for value in fundamentals.values()
        if isinstance(value, dict)
        and bool(value.get("availability"))
        and value.get("value") is not None
    )
    usable_valuation = sum(
        1
        for value in valuation.values()
        if isinstance(value, dict)
        and bool(value.get("availability"))
        and value.get("value") is not None
    )
    sources = sorted(
        {
            str(value.get("source") or "").strip()
            for value in [price, market_cap, *fundamentals.values(), *valuation.values()]
            if isinstance(value, dict) and str(value.get("source") or "").strip()
        }
    )
    return {
        "record_id": _snapshot_record_id(row),
        "retrieved_at": row.get("retrieved_at"),
        "symbol": str(asset.get("symbol") or row.get("symbol") or "").upper(),
        "name": str(asset.get("name") or "").strip(),
        "asset_type": str(asset.get("asset_type") or "UNKNOWN").upper(),
        "sector": str(asset.get("sector") or "").strip(),
        "industry": str(asset.get("industry") or "").strip(),
        "exchange": str(asset.get("exchange") or "").strip(),
        "currency": str(asset.get("currency") or "USD").strip(),
        "price": _measured_value(price),
        "price_quality": _measured_quality(price),
        "price_source": _measured_source(price),
        "price_timestamp": price.get("effective_timestamp") or price.get("timestamp"),
        "market_cap": _measured_value(market_cap),
        "market_cap_quality": _measured_quality(market_cap),
        "latest_bar": latest_bar or None,
        "history_rows_stored": int(row.get("history_rows_stored") or 0),
        "fundamental_fields": len(fundamentals),
        "usable_fundamental_fields": usable_fundamentals,
        "valuation_fields": len(valuation),
        "usable_valuation_fields": usable_valuation,
        "failure_count": len(failures),
        "failures": failures,
        "sources": sources,
        "fundamentals": fundamentals,
        "valuation": valuation,
    }


def _snapshot_filtered_rows(
    *,
    date_range: str = "all",
    asset_type: str = "",
    symbol: str = "",
    sector: str = "",
    quality: str = "",
    source: str = "",
    search: str = "",
) -> list[dict[str, Any]]:
    token = str(date_range or "all").lower()
    days = {"30d": 30, "90d": 90, "365d": 365}.get(token)
    cutoff = datetime.now(timezone.utc) - timedelta(days=days) if days else None
    at = str(asset_type or "").upper().strip()
    sym = str(symbol or "").upper().strip()
    sec = str(sector or "").upper().strip()
    qual = str(quality or "").upper().strip()
    src = str(source or "").upper().strip()
    q = str(search or "").upper().strip()

    selected = []
    for raw in _read_dataset(SNAPSHOTS_PATH):
        if cutoff is not None:
            ts = _snapshot_ts(raw)
            if ts is not None and ts < cutoff:
                continue
        row = _snapshot_archive_row(raw)
        if at and row["asset_type"] != at:
            continue
        if sym and row["symbol"] != sym:
            continue
        if sec and row["sector"].upper() != sec:
            continue
        if qual and row["price_quality"] != qual:
            continue
        if src and src not in {item.upper() for item in row["sources"]}:
            continue
        if q:
            haystack = " ".join(
                [
                    row["symbol"],
                    row["name"],
                    row["asset_type"],
                    row["sector"],
                    row["industry"],
                    row["exchange"],
                    row["price_source"],
                    " ".join(row["sources"]),
                ]
            ).upper()
            if q not in haystack:
                continue
        selected.append(row)

    selected.sort(
        key=lambda row: (
            _snapshot_ts({"retrieved_at": row.get("retrieved_at")})
            or datetime.min.replace(tzinfo=timezone.utc),
            row.get("symbol") or "",
        )
    )
    return selected


def _build_snapshot_archive(
    *,
    date_range: str,
    asset_type: str,
    symbol: str,
    sector: str,
    quality: str,
    source: str,
    search: str,
    limit: int,
) -> dict[str, Any]:
    rows = _snapshot_filtered_rows(
        date_range=date_range,
        asset_type=asset_type,
        symbol=symbol,
        sector=sector,
        quality=quality,
        source=source,
        search=search,
    )

    symbols = sorted({row["symbol"] for row in rows if row["symbol"]})
    sectors = sorted({row["sector"] for row in rows if row["sector"]})
    asset_types = sorted({row["asset_type"] for row in rows if row["asset_type"]})
    qualities = sorted({row["price_quality"] for row in rows if row["price_quality"]})
    sources = sorted({source_name for row in rows for source_name in row["sources"]})
    quality_counts = Counter(row["price_quality"] for row in rows)
    asset_type_counts = Counter(row["asset_type"] for row in rows)
    asset_counts = Counter(row["symbol"] for row in rows if row["symbol"])
    monthly_counts = Counter(
        str(row.get("retrieved_at") or "")[:7]
        for row in rows
        if str(row.get("retrieved_at") or "")[:7]
    )
    latest = max((str(row.get("retrieved_at") or "") for row in rows), default=None)
    with_failures = sum(1 for row in rows if int(row.get("failure_count") or 0) > 0)
    fresh = sum(1 for row in rows if row.get("price_quality") == "FRESH")

    # A lightweight real price-history map for gallery sparklines and preview context.
    price_history: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        if not row["symbol"]:
            continue
        try:
            price_value = float(row["price"])
        except (TypeError, ValueError):
            continue
        price_history.setdefault(row["symbol"], []).append(
            {
                "retrieved_at": row["retrieved_at"],
                "price": price_value,
                "quality": row["price_quality"],
            }
        )

    return {
        "domain": "INVESTMENT_SNAPSHOT_ARCHIVE",
        "execution": "READ_ONLY",
        "live_capital_allowed": False,
        "automatic_real_money_execution": False,
        "summary": {
            "snapshots": len(rows),
            "tracked_symbols": len(symbols),
            "asset_type_count": len(asset_type_counts),
            "fresh_price_records": fresh,
            "records_with_failures": with_failures,
            "last_updated": latest,
        },
        "filters": {
            "date_range": date_range,
            "asset_type": asset_type or "ALL",
            "symbol": symbol or "ALL",
            "sector": sector or "ALL",
            "quality": quality or "ALL",
            "source": source or "ALL",
            "search": search,
        },
        "facets": {
            "symbols": symbols,
            "sectors": sectors,
            "asset_types": asset_types,
            "qualities": qualities,
            "sources": sources,
        },
        "breakdowns": {
            "asset_type": [
                {"name": key, "count": count}
                for key, count in asset_type_counts.most_common()
            ],
            "quality": [
                {"name": key, "count": count}
                for key, count in quality_counts.most_common()
            ],
            "monthly_activity": [
                {"month": month, "count": monthly_counts[month]}
                for month in sorted(monthly_counts)
            ],
            "top_assets": [
                {"symbol": key, "count": count}
                for key, count in asset_counts.most_common(8)
            ],
        },
        "price_history": price_history,
        "records": list(reversed(rows[-limit:])),
        "note": (
            "Structured InvestmentSnapshot records only. Atlas does not currently archive "
            "user-created screenshots, chart images, notes, favorites, or arbitrary attachments "
            "in this snapshot store."
        ),
    }


@router.get("/snapshots")
async def snapshots_archive(
    date_range: str = Query("all"),
    asset_type: str = Query(""),
    symbol: str = Query(""),
    sector: str = Query(""),
    quality: str = Query(""),
    source: str = Query(""),
    search: str = Query(""),
    limit: int = Query(500, ge=25, le=2000),
) -> Dict[str, Any]:
    return await asyncio.to_thread(
        _build_snapshot_archive,
        date_range=date_range,
        asset_type=asset_type,
        symbol=symbol,
        sector=sector,
        quality=quality,
        source=source,
        search=search,
        limit=limit,
    )


@router.get("/snapshots/{record_id}")
async def snapshot_archive_detail(record_id: str) -> Dict[str, Any]:
    requested = str(record_id or "").strip()
    for raw in reversed(_read_dataset(SNAPSHOTS_PATH)):
        if _snapshot_record_id(raw) == requested:
            return {
                "record": _snapshot_archive_row(raw),
                "execution": "READ_ONLY",
                "live_capital_allowed": False,
                "automatic_real_money_execution": False,
            }
    raise HTTPException(status_code=404, detail="Snapshot record not found")


# ----------------------------
# Read-only Archive export API
# ----------------------------

_EXPORT_LABELS = {
    "paper_trades": "Paper Trades",
    "investment_history": "Investment History",
    "research_archive": "Research Archive",
    "snapshots": "Snapshots",
    "daily_plans": "Daily Research Plans",
    "investment_universe": "Investment Universe",
}


def _export_sources() -> dict[str, Path]:
    # Kept as a function so tests may monkeypatch the module-level paths safely.
    return {
        "paper_trades": JOURNAL_PATH,
        "investment_history": LEDGER_PATH,
        "research_archive": OPPORTUNITIES_PATH,
        "snapshots": SNAPSHOTS_PATH,
        "daily_plans": PLAN_PATH,
        "investment_universe": UNIVERSE_PATH,
    }


def _count_rows(path: Path) -> int:
    if not path.exists():
        return 0
    if path.suffix.lower() == ".json":
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return 0
        if isinstance(payload, list):
            return len(payload)
        if isinstance(payload, dict):
            for key in ("symbols", "items", "rows", "data"):
                value = payload.get(key)
                if isinstance(value, dict):
                    return len(value)
                if isinstance(value, list):
                    return len(value)
            return len(payload)
        return 0
    count = 0
    try:
        with path.open("r", encoding="utf-8") as handle:
            for raw in handle:
                if raw.strip():
                    count += 1
    except OSError:
        return 0
    return count


def _read_dataset(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    if path.suffix.lower() == ".json":
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return []
        if isinstance(payload, list):
            return [row for row in payload if isinstance(row, dict)]
        if isinstance(payload, dict):
            for key in ("symbols", "items", "rows", "data"):
                value = payload.get(key)
                if isinstance(value, dict):
                    rows = []
                    for name, row in value.items():
                        if isinstance(row, dict):
                            item = dict(row)
                            item.setdefault("symbol", name)
                            rows.append(item)
                    return rows
                if isinstance(value, list):
                    return [row for row in value if isinstance(row, dict)]
            return [payload]
        return []
    rows: list[dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8") as handle:
            for raw in handle:
                if not raw.strip():
                    continue
                try:
                    row = json.loads(raw)
                except Exception:
                    continue
                if isinstance(row, dict):
                    rows.append(row)
    except OSError:
        return []
    return rows


def _timestamp_value(row: dict[str, Any]) -> datetime | None:
    for key in (
        "timestamp",
        "at",
        "retrieved_at",
        "entry_timestamp",
        "exit_timestamp",
        "source_timestamp",
        "date",
    ):
        raw = row.get(key)
        if not raw:
            continue
        try:
            parsed = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        except Exception:
            continue
    return None


def _filter_date_range(rows: list[dict[str, Any]], date_range: str) -> list[dict[str, Any]]:
    token = str(date_range or "all").lower()
    days = {"30d": 30, "90d": 90, "365d": 365}.get(token)
    if days is None:
        return rows
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    filtered = []
    for row in rows:
        ts = _timestamp_value(row)
        if ts is None or ts >= cutoff:
            # Preserve rows with no parseable timestamp rather than silently deleting data.
            filtered.append(row)
    return filtered


def _csv_cell(value: Any) -> Any:
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, default=str, separators=(",", ":"))
    return value


def _csv_bytes(rows: list[dict[str, Any]]) -> bytes:
    keys: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for key in row:
            if key not in seen:
                seen.add(key)
                keys.append(str(key))
    stream = io.StringIO(newline="")
    if keys:
        writer = csv.DictWriter(stream, fieldnames=keys, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: _csv_cell(row.get(key)) for key in keys})
    return stream.getvalue().encode("utf-8-sig")


def _jsonl_bytes(rows: list[dict[str, Any]]) -> bytes:
    if not rows:
        return b""
    return ("\n".join(json.dumps(row, default=str, ensure_ascii=False) for row in rows) + "\n").encode("utf-8")


def _export_summary() -> dict[str, Any]:
    sources = []
    total_bytes = 0
    total_rows = 0
    for key, path in _export_sources().items():
        try:
            size = int(path.stat().st_size) if path.exists() else 0
        except OSError:
            size = 0
        rows = _count_rows(path)
        total_bytes += size
        total_rows += rows
        sources.append(
            {
                "key": key,
                "label": _EXPORT_LABELS[key],
                "rows": rows,
                "bytes": size,
                "available": path.exists(),
                "format": "JSON" if path.suffix.lower() == ".json" else "JSONL",
            }
        )
    return {
        "domain": "ARCHIVE_EXPORT",
        "mode": "READ_ONLY_DOWNLOAD",
        "sources": sources,
        "totals": {
            "sources": len(sources),
            "available_sources": sum(1 for row in sources if row["available"]),
            "rows": total_rows,
            "bytes": total_bytes,
        },
        "capabilities": {
            "csv": True,
            "jsonl": True,
            "persistent_export_history": False,
            "scheduled_exports": False,
            "background_export_jobs": False,
        },
        "note": (
            "Exports are generated on demand from existing Atlas archive files. "
            "Atlas does not persist download history or scheduled export jobs."
        ),
    }


@router.get("/export/summary")
async def export_summary() -> Dict[str, Any]:
    return await asyncio.to_thread(_export_summary)


@router.get("/export/preview")
async def export_preview(
    dataset: str = Query("paper_trades"),
    date_range: str = Query("all"),
    limit: int = Query(12, ge=1, le=50),
) -> Dict[str, Any]:
    sources = _export_sources()
    if dataset not in sources:
        raise HTTPException(status_code=404, detail="Unknown archive export dataset")
    rows = await asyncio.to_thread(_read_dataset, sources[dataset])
    rows = _filter_date_range(rows, date_range)
    return {
        "dataset": dataset,
        "label": _EXPORT_LABELS[dataset],
        "rows": rows[-limit:][::-1],
        "row_count": len(rows),
        "date_range": date_range,
        "mode": "READ_ONLY_PREVIEW",
    }


@router.get("/export/download")
async def export_download(
    dataset: str = Query("paper_trades"),
    format: str = Query("csv"),
    date_range: str = Query("all"),
) -> Response:
    sources = _export_sources()
    if dataset not in sources:
        raise HTTPException(status_code=404, detail="Unknown archive export dataset")
    fmt = str(format or "csv").lower()
    if fmt not in {"csv", "jsonl"}:
        raise HTTPException(status_code=400, detail="Supported formats are csv and jsonl")
    rows = await asyncio.to_thread(_read_dataset, sources[dataset])
    rows = _filter_date_range(rows, date_range)
    if fmt == "csv":
        body = _csv_bytes(rows)
        media_type = "text/csv; charset=utf-8"
        ext = "csv"
    else:
        body = _jsonl_bytes(rows)
        media_type = "application/x-ndjson; charset=utf-8"
        ext = "jsonl"
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    filename = f"atlas_{dataset}_{stamp}.{ext}"
    return Response(
        content=body,
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store, no-cache, must-revalidate",
        },
    )
