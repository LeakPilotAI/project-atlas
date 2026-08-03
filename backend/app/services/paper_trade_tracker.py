import asyncio
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select

from app.alerts.discord import send_discord_alert
from app.analytics.anomaly import AnomalySignal
from app.core.logging import get_logger
from app.db.session import AsyncSessionLocal
from app.models.paper_trade import PaperTrade
from app.services.candle_service import store_candles, get_recent_closes

logger = get_logger("paper_trade_tracker")


class PaperTradeTracker:
    def __init__(self):
        self._running = False
        self._task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info("Paper trade tracker started")

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Paper trade tracker stopped")

    async def open_trade(
        self,
        symbol: str,
        side: str,
        entry_price: float,
        confidence: float,
        reason: str,
        opportunity_id: Optional[int] = None,
    ) -> None:
        # Adaptive evaluation window based on confidence
        if confidence >= 80:
            minutes = 35
        elif confidence >= 65:
            minutes = 55
        else:
            minutes = 90

        evaluate_after = datetime.now(timezone.utc) + timedelta(minutes=minutes)

        async with AsyncSessionLocal() as session:
            trade = PaperTrade(
                symbol=symbol,
                side=side.upper(),
                entry_price=entry_price,
                entry_time=datetime.now(timezone.utc),
                status="open",
                confidence_at_entry=confidence,
                reason=reason,
                opportunity_id=opportunity_id,
                evaluate_after=evaluate_after,
            )
            session.add(trade)
            await session.commit()

            logger.info(
                "Paper trade opened",
                symbol=symbol,
                side=side,
                entry=entry_price,
                evaluate_in_minutes=minutes,
            )

    async def _loop(self) -> None:
        while self._running:
            try:
                await self._evaluate_open_trades()
            except Exception as e:
                logger.error("Paper trade evaluation failed", error=str(e))
            await asyncio.sleep(60)

    async def _evaluate_open_trades(self) -> None:
        async with AsyncSessionLocal() as session:
            now = datetime.now(timezone.utc)
            result = await session.execute(
                select(PaperTrade).where(
                    PaperTrade.status == "open",
                    PaperTrade.evaluate_after <= now,
                )
            )
            trades = result.scalars().all()

            for trade in trades:
                await self._close_and_report(trade, session)

    async def _close_and_report(self, trade: PaperTrade, session) -> None:
        await store_candles(trade.symbol, timeframe="5m", limit=50)
        closes = await get_recent_closes(trade.symbol, timeframe="5m", limit=40)

        if len(closes) < 8:
            trade.status = "expired"
            trade.notes = "Not enough data to evaluate"
            await session.commit()
            return

        current_price = closes[-1]
        entry = trade.entry_price

        # Structure-aware exit metrics
        if trade.side == "LONG":
            pnl_pct = ((current_price - entry) / entry) * 100
            max_price = max(closes)
            min_price = min(closes)
            mfe = ((max_price - entry) / entry) * 100
            mae = ((min_price - entry) / entry) * 100

            # Trailing concept: did price make a higher high then pull back significantly?
            recent_high = max(closes[-8:])
            pullback = ((recent_high - current_price) / recent_high) * 100 if recent_high > 0 else 0
        else:
            pnl_pct = ((entry - current_price) / entry) * 100
            max_price = max(closes)
            min_price = min(closes)
            mfe = ((entry - min_price) / entry) * 100
            mae = ((entry - max_price) / entry) * 100

            recent_low = min(closes[-8:])
            pullback = ((current_price - recent_low) / recent_low) * 100 if recent_low > 0 else 0

        is_winner = pnl_pct > 0.15  # small buffer against noise

        trade.exit_price = current_price
        trade.exit_time = datetime.now(timezone.utc)
        trade.pnl_pct = round(pnl_pct, 2)
        trade.max_favorable_pct = round(mfe, 2)
        trade.max_adverse_pct = round(mae, 2)
        trade.is_winner = is_winner
        trade.status = "closed"
        trade.notes = f"Pullback from extreme: {pullback:.2f}%"
        await session.commit()

        result_emoji = "✅" if is_winner else "❌"
        result_text = "You would have made money" if is_winner else "You would have lost money"

        message = (
            f"{result_emoji} **Signal Result: {pnl_pct:+.2f}%**\n\n"
            f"{result_text}.\n\n"
            f"**Side:** {trade.side}\n"
            f"**Entry:** ${entry:.4f}\n"
            f"**Exit:** ${current_price:.4f}\n"
            f"**Max Favorable (MFE):** {mfe:+.2f}%\n"
            f"**Max Adverse (MAE):** {mae:+.2f}%\n"
            f"**Pullback from extreme:** {pullback:.2f}%"
        )

        signal = AnomalySignal(
            symbol=trade.symbol,
            alert_type="paper_trade_result",
            severity="medium" if is_winner else "low",
            title=f"{trade.symbol} Paper Trade Result",
            message=message,
            opportunity_score=abs(pnl_pct),
            confidence_score=trade.confidence_at_entry or 50,
            risk_score=40.0,
            price=current_price,
            indicators={
                "pnl_pct": pnl_pct,
                "mfe": mfe,
                "mae": mae,
                "side": trade.side,
                "pullback": pullback,
            },
        )

        await send_discord_alert(signal)

        logger.info(
            "Paper trade closed and reported",
            symbol=trade.symbol,
            side=trade.side,
            pnl_pct=round(pnl_pct, 2),
            winner=is_winner,
        )


paper_trade_tracker = PaperTradeTracker()