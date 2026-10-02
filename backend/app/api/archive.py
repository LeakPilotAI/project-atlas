"""Read-only Archive APIs for investment research/PAPER history.

This surface never places broker orders and never rewrites investment or trading
journals. Investment history is intentionally honest about the current book:
Atlas records accumulation fills/open positions, but does not currently record
closed long-horizon investment exits suitable for realized win-rate/P&L claims.
"""
from __future__ import annotations

import asyncio
import csv
import io
import json
from collections import deque
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
