from datetime import datetime, timezone

from app.analytics.anomaly import AnomalySignal
from app.alerts.discord import send_discord_alert
from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.session import AsyncSessionLocal
from app.models.alert import Alert
from app.services.opportunity_tracker import opportunity_tracker

logger = get_logger("alerts")
settings = get_settings()


async def dispatch_alert(signal: AnomalySignal) -> None:
    async with AsyncSessionLocal() as session:
        alert = Alert(
            market_symbol=signal.symbol,
            alert_type=signal.alert_type,
            severity=signal.severity,
            title=signal.title,
            message=signal.message,
            opportunity_score=signal.opportunity_score,
            confidence_score=signal.confidence_score,
            risk_score=signal.risk_score,
            price_at_alert=signal.price,
            indicators=signal.indicators,
            sent_discord=False,
            sent_telegram=False,
            fired_at=datetime.now(timezone.utc),
        )
        session.add(alert)
        await session.commit()

    logger.info(
        "Alert generated",
        symbol=signal.symbol,
        type=signal.alert_type,
        severity=signal.severity,
        title=signal.title,
    )

    # Send Discord DM
    try:
        await send_discord_alert(signal)
    except Exception as e:
        logger.error("Discord delivery failed", error=str(e))

    # Create opportunity for further monitoring + later Long/Short recommendation
    try:
        await opportunity_tracker.create_from_signal(signal)
    except Exception as e:
        logger.error("Failed to create opportunity", error=str(e))