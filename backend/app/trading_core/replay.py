from __future__ import annotations

from typing import Any, Dict, Iterable, List

from .models import MarketQuote, PaperExecutionConfig, TradeIntent
from .paper_engine import PaperEngine


_REPORT_DECIMALS = 10


def _canon(value: Any) -> Any:
    """Canonicalize floating-point values at the reporting boundary.

    Execution math stays full precision inside PaperEngine. Replay/report JSON should
    not expose binary floating-point artifacts such as 1.7999999999999972 for 1.8R.
    """
    if value is None:
        return None
    if isinstance(value, float):
        return round(value, _REPORT_DECIMALS)
    return value


def replay_summary(intent: TradeIntent, quotes: Iterable[MarketQuote], config: PaperExecutionConfig | None = None) -> Dict[str, Any]:
    """Replay one V4 trade and return a stable JSON-friendly summary."""
    engine = PaperEngine(config)
    steps = engine.replay(intent, list(quotes))
    final = steps[-1].position
    return {
        "trade_id": final.trade_id,
        "symbol": final.symbol,
        "side": final.side.value,
        "strategy_version": final.strategy_version,
        "opened_at": final.opened_at.isoformat(),
        "status": final.status.value,
        "entry_price": _canon(final.entry_price),
        "initial_stop": _canon(final.initial_stop),
        "working_stop": _canon(final.working_stop),
        "target_price": _canon(final.target_price),
        "target_r": _canon(final.target_r),
        "mfe_r": _canon(final.mfe_r),
        "mae_r": _canon(final.mae_r),
        "closed_at": final.closed_at.isoformat() if final.closed_at else None,
        "exit_price": _canon(final.exit_price),
        "exit_reason": final.exit_reason.value if final.exit_reason else None,
        "gross_r": _canon(final.gross_r),
        "net_r": _canon(final.net_r),
        "fees_usd": _canon(final.fees_usd),
        "events": [step.event for step in steps],
    }


def compare_to_legacy(v4: Dict[str, Any], legacy: Dict[str, Any]) -> Dict[str, Any]:
    """Compare a V4 replay summary to one legacy close record.

    This is research-only and intentionally does not declare either implementation
    correct. It highlights behavioral divergence for review.
    """
    legacy_r = legacy.get("net_pnl_r")
    if legacy_r is None:
        legacy_r = legacy.get("R_multiple")
    try:
        legacy_r = float(legacy_r) if legacy_r is not None else None
    except (TypeError, ValueError):
        legacy_r = None
    v4_r = v4.get("net_r")
    delta_r = None if legacy_r is None or v4_r is None else _canon(float(v4_r) - legacy_r)
    legacy_reason = str(legacy.get("exit_reason") or legacy.get("result") or "") or None
    return {
        "trade_id": v4.get("trade_id") or legacy.get("trade_id"),
        "symbol": v4.get("symbol") or legacy.get("symbol"),
        "legacy_r": _canon(legacy_r),
        "v4_r": _canon(v4_r),
        "delta_r": delta_r,
        "legacy_exit_reason": legacy_reason,
        "v4_exit_reason": v4.get("exit_reason"),
        "exit_reason_match": legacy_reason == v4.get("exit_reason") if legacy_reason is not None else None,
        "status": "MATCH" if (delta_r is not None and abs(delta_r) < 1e-9 and (legacy_reason is None or legacy_reason == v4.get("exit_reason"))) else "DIVERGED",
    }


def compare_many(pairs: Iterable[tuple[Dict[str, Any], Dict[str, Any]]]) -> Dict[str, Any]:
    rows: List[Dict[str, Any]] = [compare_to_legacy(v4, legacy) for v4, legacy in pairs]
    known = [r for r in rows if r["delta_r"] is not None]
    return {
        "n": len(rows),
        "comparable_n": len(known),
        "matches": sum(1 for r in rows if r["status"] == "MATCH"),
        "diverged": sum(1 for r in rows if r["status"] == "DIVERGED"),
        "mean_delta_r": _canon(sum(r["delta_r"] for r in known) / len(known)) if known else None,
        "max_abs_delta_r": _canon(max((abs(r["delta_r"]) for r in known), default=None)),
        "rows": rows,
    }
