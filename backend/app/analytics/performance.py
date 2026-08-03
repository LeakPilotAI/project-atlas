from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from sqlalchemy import select, func, and_
from app.db.session import AsyncSessionLocal
from app.models.paper_trade import PaperTrade


@dataclass
class PerformanceBreakdown:
    total_trades: int = 0
    winners: int = 0
    losers: int = 0
    win_rate: float = 0.0
    avg_pnl: float = 0.0
    avg_winner: float = 0.0
    avg_loser: float = 0.0
    best_trade: float = 0.0
    worst_trade: float = 0.0
    expectancy: float = 0.0
    profit_factor: float = 0.0
    max_drawdown_approx: float = 0.0


@dataclass
class SymbolStats:
    symbol: str
    trades: int
    win_rate: float
    avg_pnl: float
    total_pnl: float


@dataclass
class FullPerformanceReport:
    overall: PerformanceBreakdown
    by_side: Dict[str, PerformanceBreakdown]
    by_symbol: List[SymbolStats]
    last_7_days: PerformanceBreakdown
    last_30_days: PerformanceBreakdown


async def compute_performance(
    since: Optional[datetime] = None,
) -> PerformanceBreakdown:
    async with AsyncSessionLocal() as session:
        query = select(PaperTrade).where(PaperTrade.status == "closed")
        if since:
            query = query.where(PaperTrade.exit_time >= since)

        result = await session.execute(query)
        trades = result.scalars().all()

    return _from_trades(trades)


def _from_trades(trades: List[PaperTrade]) -> PerformanceBreakdown:
    if not trades:
        return PerformanceBreakdown()

    pnls = [t.pnl_pct or 0.0 for t in trades]
    winners = [p for p in pnls if p > 0]
    losers = [p for p in pnls if p <= 0]

    total = len(pnls)
    win_count = len(winners)
    loss_count = len(losers)

    avg_pnl = sum(pnls) / total
    avg_win = sum(winners) / win_count if winners else 0.0
    avg_loss = sum(losers) / loss_count if losers else 0.0

    gross_profit = sum(winners)
    gross_loss = abs(sum(losers))
    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else 0.0

    # Simple sequential drawdown approximation
    equity = 0.0
    peak = 0.0
    max_dd = 0.0
    for p in pnls:
        equity += p
        peak = max(peak, equity)
        dd = peak - equity
        max_dd = max(max_dd, dd)

    return PerformanceBreakdown(
        total_trades=total,
        winners=win_count,
        losers=loss_count,
        win_rate=round(win_count / total * 100, 1) if total else 0.0,
        avg_pnl=round(avg_pnl, 2),
        avg_winner=round(avg_win, 2),
        avg_loser=round(avg_loss, 2),
        best_trade=round(max(pnls), 2) if pnls else 0.0,
        worst_trade=round(min(pnls), 2) if pnls else 0.0,
        expectancy=round(avg_pnl, 2),
        profit_factor=round(profit_factor, 2),
        max_drawdown_approx=round(max_dd, 2),
    )


async def get_full_performance_report() -> FullPerformanceReport:
    now = datetime.now(timezone.utc)

    overall = await compute_performance()
    last_7 = await compute_performance(since=now - timedelta(days=7))
    last_30 = await compute_performance(since=now - timedelta(days=30))

    # By side
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(PaperTrade).where(PaperTrade.status == "closed")
        )
        all_trades = result.scalars().all()

    longs = [t for t in all_trades if (t.side or "").upper() == "LONG"]
    shorts = [t for t in all_trades if (t.side or "").upper() == "SHORT"]

    by_side = {
        "LONG": _from_trades(longs),
        "SHORT": _from_trades(shorts),
    }

    # By symbol
    symbol_map: Dict[str, List[PaperTrade]] = {}
    for t in all_trades:
        symbol_map.setdefault(t.symbol, []).append(t)

    by_symbol: List[SymbolStats] = []
    for symbol, trades in symbol_map.items():
        pnls = [t.pnl_pct or 0.0 for t in trades]
        wins = sum(1 for p in pnls if p > 0)
        by_symbol.append(
            SymbolStats(
                symbol=symbol,
                trades=len(trades),
                win_rate=round(wins / len(trades) * 100, 1) if trades else 0.0,
                avg_pnl=round(sum(pnls) / len(pnls), 2) if pnls else 0.0,
                total_pnl=round(sum(pnls), 2),
            )
        )

    by_symbol.sort(key=lambda x: x.total_pnl, reverse=True)

    return FullPerformanceReport(
        overall=overall,
        by_side=by_side,
        by_symbol=by_symbol[:15],
        last_7_days=last_7,
        last_30_days=last_30,
    )