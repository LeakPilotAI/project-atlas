import asyncio
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select, func

from app.alerts.discord import bot as discord_bot, get_subscriber_ids
from app.core.logging import get_logger
from app.db.session import AsyncSessionLocal
from app.models.paper_trade import PaperTrade

logger = get_logger("weekly_summary")


class WeeklySummaryService:
    def __init__(self):
        self._running = False
        self._task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info("Weekly summary service started")

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Weekly summary service stopped")

    async def _loop(self) -> None:
        while self._running:
            try:
                now = datetime.now(timezone.utc)
                # Monday 14:00 UTC (~ morning US)
                if now.weekday() == 0 and now.hour == 14 and now.minute < 5:
                    await self._send_weekly_report()
                    await asyncio.sleep(3600)  # avoid double-send
                else:
                    await asyncio.sleep(60)
            except Exception as e:
                logger.error("Weekly summary loop error", error=str(e))
                await asyncio.sleep(60)

    async def _send_weekly_report(self) -> None:
        logger.info("Generating weekly performance report")

        now = datetime.now(timezone.utc)
        week_ago = now - timedelta(days=7)

        async with AsyncSessionLocal() as session:
            # Last 7 days
            result = await session.execute(
                select(PaperTrade).where(
                    PaperTrade.status == "closed",
                    PaperTrade.exit_time >= week_ago,
                )
            )
            week_trades = result.scalars().all()

            # All-time closed
            result_all = await session.execute(
                select(PaperTrade).where(PaperTrade.status == "closed")
            )
            all_trades = result_all.scalars().all()

        def stats(trades):
            if not trades:
                return {
                    "count": 0,
                    "win_rate": 0.0,
                    "avg_pnl": 0.0,
                    "best": 0.0,
                    "worst": 0.0,
                    "total_pnl": 0.0,
                }
            pnls = [t.pnl_pct or 0.0 for t in trades]
            winners = sum(1 for p in pnls if p > 0)
            return {
                "count": len(pnls),
                "win_rate": round(winners / len(pnls) * 100, 1),
                "avg_pnl": round(sum(pnls) / len(pnls), 2),
                "best": round(max(pnls), 2),
                "worst": round(min(pnls), 2),
                "total_pnl": round(sum(pnls), 2),
            }

        week = stats(week_trades)
        overall = stats(all_trades)

        # Best / worst symbol this week
        by_symbol = {}
        for t in week_trades:
            by_symbol.setdefault(t.symbol, []).append(t.pnl_pct or 0.0)

        best_symbol = None
        worst_symbol = None
        if by_symbol:
            ranked = sorted(
                by_symbol.items(),
                key=lambda x: sum(x[1]) / len(x[1]),
                reverse=True,
            )
            best_symbol = ranked[0]
            worst_symbol = ranked[-1]

        message = (
            f"**📊 Project Atlas — Weekly Report**\n"
            f"Period: {(week_ago).strftime('%Y-%m-%d')} → {now.strftime('%Y-%m-%d')}\n\n"
            f"**This Week**\n"
            f"• Closed trades: **{week['count']}**\n"
            f"• Win rate: **{week['win_rate']}%**\n"
            f"• Avg PnL: **{week['avg_pnl']:+.2f}%**\n"
            f"• Total PnL: **{week['total_pnl']:+.2f}%**\n"
            f"• Best: **+{week['best']}%** | Worst: **{week['worst']}%**\n\n"
        )

        if best_symbol:
            avg_best = sum(best_symbol[1]) / len(best_symbol[1])
            message += f"• Best symbol: **{best_symbol[0]}** ({avg_best:+.2f}% avg)\n"
        if worst_symbol and worst_symbol[0] != (best_symbol[0] if best_symbol else None):
            avg_worst = sum(worst_symbol[1]) / len(worst_symbol[1])
            message += f"• Weakest symbol: **{worst_symbol[0]}** ({avg_worst:+.2f}% avg)\n"

        message += (
            f"\n**All-Time**\n"
            f"• Closed trades: **{overall['count']}**\n"
            f"• Win rate: **{overall['win_rate']}%**\n"
            f"• Avg PnL: **{overall['avg_pnl']:+.2f}%**\n"
            f"• Total PnL: **{overall['total_pnl']:+.2f}%**\n\n"
            f"_Keep collecting data. Do not change rules mid-week._"
        )

        # Send DM to all subscribers
        try:
            subscriber_ids = await get_subscriber_ids()
            if not subscriber_ids:
                logger.warning("No Discord subscribers for weekly report")
                return

            for user_id in subscriber_ids:
                try:
                    user = await discord_bot.fetch_user(int(user_id))
                    if user:
                        await user.send(message)
                except Exception as e:
                    logger.warning("Failed to DM weekly report", user_id=user_id, error=str(e))

            logger.info("Weekly report sent", recipients=len(subscriber_ids))
        except Exception as e:
            logger.error("Failed to send weekly report", error=str(e))


weekly_summary_service = WeeklySummaryService()