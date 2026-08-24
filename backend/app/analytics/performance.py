"""Paper-trade and alert performance analytics for Project Atlas."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional


@dataclass
class LaneStats:
    lane: str
    trades: int = 0
    wins: int = 0
    losses: int = 0
    scratches: int = 0
    win_rate: float = 0.0
    avg_pnl_pct: float = 0.0
    total_pnl_pct: float = 0.0
    avg_win_pct: float = 0.0
    avg_loss_pct: float = 0.0
    expectancy_pct: float = 0.0
    max_win_pct: float = 0.0
    max_loss_pct: float = 0.0
    symbols: dict[str, int] = field(default_factory=dict)


@dataclass
class PerformanceReport:
    generated_at: str
    total_trades: int
    overall: LaneStats
    by_lane: list[LaneStats]
    by_symbol: list[dict[str, Any]]
    notes: list[str] = field(default_factory=list)


def _f(x: Any, default: float = 0.0) -> float:
    try:
        if x is None:
            return default
        return float(x)
    except (TypeError, ValueError):
        return default


def _classify_pnl(pnl_pct: float, eps: float = 0.05) -> str:
    if pnl_pct > eps:
        return "win"
    if pnl_pct < -eps:
        return "loss"
    return "scratch"


def summarize_trades(
    trades: list[dict[str, Any]],
    *,
    lane_key: str = "lane",
    symbol_key: str = "symbol",
    pnl_key: str = "pnl_pct",
) -> PerformanceReport:
    """
    Aggregate closed paper trades.

    Each trade dict should include at least:
      symbol, pnl_pct, optional lane (perp|day_trade|quality_dip|unknown)
    """
    now = datetime.now(timezone.utc).isoformat()
    if not trades:
        empty = LaneStats(lane="overall")
        return PerformanceReport(
            generated_at=now,
            total_trades=0,
            overall=empty,
            by_lane=[],
            by_symbol=[],
            notes=["No closed paper trades yet — keep logging outcomes."],
        )

    lanes: dict[str, list[float]] = {}
    symbols: dict[str, list[float]] = {}
    all_pnls: list[float] = []

    for t in trades:
        pnl = _f(t.get(pnl_key))
        lane = str(t.get(lane_key) or t.get("source") or "unknown").lower()
        sym = str(t.get(symbol_key) or "?").upper()
        all_pnls.append(pnl)
        lanes.setdefault(lane, []).append(pnl)
        symbols.setdefault(sym, []).append(pnl)

    def _stats(name: str, pnls: list[float]) -> LaneStats:
        wins = [p for p in pnls if _classify_pnl(p) == "win"]
        losses = [p for p in pnls if _classify_pnl(p) == "loss"]
        scratches = [p for p in pnls if _classify_pnl(p) == "scratch"]
        n = len(pnls)
        wr = (len(wins) / n * 100.0) if n else 0.0
        avg = sum(pnls) / n if n else 0.0
        avg_w = sum(wins) / len(wins) if wins else 0.0
        avg_l = sum(losses) / len(losses) if losses else 0.0
        # Expectancy per trade in %
        p_win = len(wins) / n if n else 0.0
        p_loss = len(losses) / n if n else 0.0
        exp = p_win * avg_w + p_loss * avg_l
        return LaneStats(
            lane=name,
            trades=n,
            wins=len(wins),
            losses=len(losses),
            scratches=len(scratches),
            win_rate=round(wr, 1),
            avg_pnl_pct=round(avg, 3),
            total_pnl_pct=round(sum(pnls), 3),
            avg_win_pct=round(avg_w, 3),
            avg_loss_pct=round(avg_l, 3),
            expectancy_pct=round(exp, 3),
            max_win_pct=round(max(pnls), 3) if pnls else 0.0,
            max_loss_pct=round(min(pnls), 3) if pnls else 0.0,
        )

    overall = _stats("overall", all_pnls)
    by_lane = [_stats(k, v) for k, v in sorted(lanes.items(), key=lambda x: -len(x[1]))]

    by_symbol: list[dict[str, Any]] = []
    for sym, pnls in sorted(symbols.items(), key=lambda x: -len(x[1])):
        s = _stats(sym, pnls)
        by_symbol.append(
            {
                "symbol": sym,
                "trades": s.trades,
                "win_rate": s.win_rate,
                "avg_pnl_pct": s.avg_pnl_pct,
                "total_pnl_pct": s.total_pnl_pct,
                "expectancy_pct": s.expectancy_pct,
            }
        )

    notes: list[str] = []
    if overall.trades < 30:
        notes.append("Sample size small — treat stats as directional only.")
    if overall.expectancy_pct > 0:
        notes.append("Positive expectancy on paper — keep process, refine filters.")
    elif overall.trades >= 20:
        notes.append("Non-positive expectancy — tighten score thresholds before sizing up.")

    return PerformanceReport(
        generated_at=now,
        total_trades=len(all_pnls),
        overall=overall,
        by_lane=by_lane,
        by_symbol=by_symbol[:25],
        notes=notes,
    )


def report_to_dict(report: PerformanceReport) -> dict[str, Any]:
    def lane_dict(s: LaneStats) -> dict[str, Any]:
        return {
            "lane": s.lane,
            "trades": s.trades,
            "wins": s.wins,
            "losses": s.losses,
            "scratches": s.scratches,
            "win_rate": s.win_rate,
            "avg_pnl_pct": s.avg_pnl_pct,
            "total_pnl_pct": s.total_pnl_pct,
            "avg_win_pct": s.avg_win_pct,
            "avg_loss_pct": s.avg_loss_pct,
            "expectancy_pct": s.expectancy_pct,
            "max_win_pct": s.max_win_pct,
            "max_loss_pct": s.max_loss_pct,
        }

    return {
        "generated_at": report.generated_at,
        "total_trades": report.total_trades,
        "overall": lane_dict(report.overall),
        "by_lane": [lane_dict(x) for x in report.by_lane],
        "by_symbol": report.by_symbol,
        "notes": report.notes,
    }


def format_report_text(report: PerformanceReport) -> str:
    o = report.overall
    lines = [
        f"**Paper performance** · {report.total_trades} closed trades",
        f"Win rate **{o.win_rate}%** · Avg PnL **{o.avg_pnl_pct}%** · Expectancy **{o.expectancy_pct}%**",
        f"Total paper PnL **{o.total_pnl_pct}%** · Max win {o.max_win_pct}% · Max loss {o.max_loss_pct}%",
        "",
    ]
    if report.by_lane:
        lines.append("**By lane**")
        for s in report.by_lane:
            lines.append(
                f"• `{s.lane}` — n={s.trades} WR {s.win_rate}% exp {s.expectancy_pct}%"
            )
        lines.append("")
    if report.by_symbol:
        lines.append("**Top symbols**")
        for row in report.by_symbol[:8]:
            lines.append(
                f"• `{row['symbol']}` — n={row['trades']} WR {row['win_rate']}% avg {row['avg_pnl_pct']}%"
            )
        lines.append("")
    for n in report.notes:
        lines.append(f"_{n}_")
    lines.append("Research only — not financial advice.")
    return "\n".join(lines)