import asyncio
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select

from app.alerts.discord import send_discord_alert
from app.alerts.chart_generator import generate_candlestick_chart
from app.analytics.anomaly import AnomalySignal
from app.analytics.decision_engine import decide_direction
from app.analytics.events import is_high_impact_window, event_context_message
from app.analytics.risk import calculate_position_size
from app.analytics.whale import (
    analyze_whale_flow,
    whale_boost_for_decision,
    format_whale_note,
)
from app.core.logging import get_logger
from app.core.redis import get_redis
from app.db.session import AsyncSessionLocal
from app.models.opportunity import Opportunity
from app.services.candle_service import store_candles
from app.services.paper_trade_tracker import paper_trade_tracker

logger = get_logger("opportunity_tracker")

MONITOR_MINUTES = 150
ALERT_COOLDOWN_MINUTES = 90
ACTIVE_PROFILE = "balanced"
EVENT_CONFIDENCE_BOOST = 8.0


class OpportunityTracker:
    def __init__(self):
        self._running = False
        self._task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info("Opportunity tracker started", profile=ACTIVE_PROFILE)

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Opportunity tracker stopped")

    async def create_from_signal(self, signal: AnomalySignal) -> None:
        if signal.price < 0.0001:
            return

        redis = await get_redis()
        cooldown_key = f"atlas:alert_cooldown:{signal.symbol}"
        if await redis.get(cooldown_key):
            logger.info("Cooldown active, skipping", symbol=signal.symbol)
            return

        async with AsyncSessionLocal() as session:
            existing = await session.execute(
                select(Opportunity).where(
                    Opportunity.symbol == signal.symbol,
                    Opportunity.status == "monitoring",
                )
            )
            if existing.scalar_one_or_none():
                return

            opp = Opportunity(
                symbol=signal.symbol,
                exchange="hyperliquid",
                initial_alert_type=signal.alert_type,
                initial_severity=signal.severity,
                initial_price=signal.price,
                initial_message=signal.message,
                status="monitoring",
                monitored_until=datetime.now(timezone.utc)
                + timedelta(minutes=MONITOR_MINUTES),
                indicators_at_detection=signal.indicators,
                fired_at=datetime.now(timezone.utc),
            )
            session.add(opp)
            await session.commit()

            logger.info("Opportunity created", symbol=signal.symbol, price=signal.price)
            await store_candles(signal.symbol, timeframe="5m", limit=60)

    async def _loop(self) -> None:
        while self._running:
            try:
                await self._check_active_opportunities()
            except Exception as e:
                logger.error("Opportunity tracker cycle failed", error=str(e))
            await asyncio.sleep(45)

    async def _check_active_opportunities(self) -> None:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Opportunity).where(Opportunity.status == "monitoring")
            )
            opportunities = result.scalars().all()
            if not opportunities:
                return

            now = datetime.now(timezone.utc)
            from app.adapters.registry import registry

            adapter = registry.get("hyperliquid")
            if not adapter:
                return

            high_impact = is_high_impact_window(now)
            event_msg = event_context_message(now)

            for opp in opportunities:
                if now > opp.monitored_until:
                    opp.status = "expired"
                    opp.recommendation = "NONE"
                    opp.recommendation_reason = "Monitoring window expired"
                    opp.last_checked_at = now
                    await session.commit()
                    logger.info("Opportunity expired", symbol=opp.symbol)
                    continue

                raw_5m = await adapter.get_candles(opp.symbol, interval="5m", limit=50)
                raw_15m = await adapter.get_candles(opp.symbol, interval="15m", limit=30)

                if len(raw_5m) < 20 or len(raw_15m) < 12:
                    continue

                def parse(raw):
                    ts, o, h, l, c, v = [], [], [], [], [], []
                    for candle in raw:
                        ts.append(
                            datetime.fromtimestamp(
                                candle["open_time"] / 1000, tz=timezone.utc
                            )
                        )
                        o.append(candle["open"])
                        h.append(candle["high"])
                        l.append(candle["low"])
                        c.append(candle["close"])
                        v.append(candle["volume"])
                    return ts, o, h, l, c, v

                ts5, o5, h5, l5, c5, v5 = parse(raw_5m)
                _, o15, h15, l15, c15, v15 = parse(raw_15m)

                await store_candles(opp.symbol, timeframe="5m", limit=50)

                decision = decide_direction(
                    symbol=opp.symbol,
                    closes_5m=c5,
                    highs_5m=h5,
                    lows_5m=l5,
                    volumes_5m=v5,
                    closes_15m=c15,
                    highs_15m=h15,
                    lows_15m=l15,
                    volumes_15m=v15,
                    entry_price=opp.initial_price,
                    profile_name=ACTIVE_PROFILE,
                )

                if decision.recommendation == "NONE":
                    opp.last_checked_at = now
                    await session.commit()
                    continue

                # Whale flow
                whale_flow = await analyze_whale_flow(opp.symbol)
                boost = whale_boost_for_decision(whale_flow, decision.recommendation)
                adjusted_confidence = min(96.0, decision.confidence + boost)

                required_confidence = 58.0
                if high_impact:
                    required_confidence += EVENT_CONFIDENCE_BOOST

                if adjusted_confidence < required_confidence:
                    opp.last_checked_at = now
                    await session.commit()
                    logger.info(
                        "Signal below whale-adjusted confidence",
                        symbol=opp.symbol,
                        confidence=adjusted_confidence,
                        whale_bias=whale_flow.bias,
                    )
                    continue

                whale_note = format_whale_note(whale_flow)

                opp.status = (
                    "long_signal"
                    if decision.recommendation == "LONG"
                    else "short_signal"
                )
                opp.recommendation = decision.recommendation
                opp.recommendation_confidence = adjusted_confidence
                opp.recommendation_reason = f"{decision.reason} | {whale_note}"
                opp.last_checked_at = now
                await session.commit()

                redis = await get_redis()
                await redis.set(
                    f"atlas:alert_cooldown:{opp.symbol}",
                    "1",
                    ex=ALERT_COOLDOWN_MINUTES * 60,
                )

                await paper_trade_tracker.open_trade(
                    symbol=opp.symbol,
                    side=decision.recommendation,
                    entry_price=opp.initial_price,
                    confidence=adjusted_confidence,
                    reason=f"{decision.reason} | {whale_note}",
                    opportunity_id=opp.id,
                )

                risk = calculate_position_size(
                    account_balance=10000.0,
                    risk_per_trade_pct=1.0,
                    entry_price=opp.initial_price,
                    invalidation=decision.invalidation or opp.initial_price * 0.98,
                    confidence=adjusted_confidence,
                )

                chart_bytes = generate_candlestick_chart(
                    symbol=opp.symbol,
                    timestamps=ts5,
                    opens=o5,
                    highs=h5,
                    lows=l5,
                    closes=c5,
                    volumes=v5,
                    entry_price=opp.initial_price,
                    current_price=c5[-1],
                    title=f"{opp.symbol} → {decision.recommendation} ({ACTIVE_PROFILE})",
                )

                message = (
                    f"**{decision.reason}**\n\n"
                    f"**Profile:** {ACTIVE_PROFILE}\n"
                    f"**Regime:** {decision.regime or 'unknown'}\n"
                    f"**Confidence:** {adjusted_confidence:.0f}%\n"
                    f"**Whale:** {whale_note}\n"
                    f"**Entry reference:** ${opp.initial_price:.4f}\n"
                    f"**Current price:** ${c5[-1]:.4f}\n"
                )
                if decision.invalidation:
                    message += f"**Invalidation:** ${decision.invalidation:.4f}\n"
                if decision.suggested_rr:
                    message += f"**Suggested R:R:** {decision.suggested_rr}\n"
                message += f"**Position size suggestion:** ~{risk.position_size_pct}% of account\n"
                message += f"**{risk.risk_amount_note}**\n"
                if risk.suggested_leverage:
                    message += f"**Note:** {risk.suggested_leverage}\n"
                if event_msg:
                    message += f"\n⚠️ **{event_msg}** — treat with extra caution.\n"

                signal = AnomalySignal(
                    symbol=opp.symbol,
                    alert_type=f"recommendation_{decision.recommendation.lower()}",
                    severity="high",
                    title=f"{opp.symbol} → {decision.recommendation} Recommended",
                    message=message,
                    opportunity_score=adjusted_confidence,
                    confidence_score=adjusted_confidence,
                    risk_score=40.0,
                    price=c5[-1],
                    indicators={
                        "entry_price": opp.initial_price,
                        "current_price": c5[-1],
                        "invalidation": decision.invalidation,
                        "suggested_rr": decision.suggested_rr,
                        "position_size_pct": risk.position_size_pct,
                        "profile": ACTIVE_PROFILE,
                        "regime": decision.regime,
                        "high_impact_event": high_impact,
                        "whale_bias": whale_flow.bias,
                        "whale_net_usd": whale_flow.net_usd,
                    },
                )

                await send_discord_alert(signal, chart_bytes=chart_bytes)

                logger.info(
                    "Multi-TF + whale recommendation sent",
                    symbol=opp.symbol,
                    recommendation=decision.recommendation,
                    confidence=round(adjusted_confidence, 1),
                    profile=ACTIVE_PROFILE,
                    regime=decision.regime,
                    whale_bias=whale_flow.bias,
                    whale_net=whale_flow.net_usd,
                    high_impact_event=high_impact,
                    position_size_pct=risk.position_size_pct,
                )


opportunity_tracker = OpportunityTracker()