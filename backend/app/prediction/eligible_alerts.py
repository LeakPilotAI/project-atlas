"""Discord DM notification for genuinely eligible Prediction PAPER candidates.

Notification-only. This module cannot open PAPER positions and has no authenticated
provider or live-order surface.
"""
from __future__ import annotations

from typing import Any, Awaitable, Callable, Iterable

from app.alerts.discord import send_discord_alert
from app.prediction.paper_engine import PredictionPaperJournal, prediction_paper_journal

Sender = Callable[..., Awaitable[bool]]
ALERT_EVENT = "eligible_candidate_alert_delivered"


def prediction_alert_key(evaluation: dict[str, Any]) -> str:
    ticker = str(evaluation.get("ticker") or "").strip().upper()
    side = str(evaluation.get("side") or "").strip().upper()
    occurrence = str(evaluation.get("occurrence_datetime") or "").strip()
    strategy = str(evaluation.get("strategy") or "").strip()
    if not ticker or side not in {"YES", "NO"} or not occurrence or not strategy:
        raise ValueError("eligible Prediction alert is missing identity fields")
    return "|".join((ticker, side, occurrence, strategy))


def build_prediction_eligible_alert(evaluation: dict[str, Any]) -> dict[str, Any]:
    if evaluation.get("eligible") is not True:
        raise ValueError("Prediction notification requires eligible=true")
    key = prediction_alert_key(evaluation)
    ticker = str(evaluation.get("ticker") or "").strip().upper()
    side = str(evaluation.get("side") or "").strip().upper()
    score = int(evaluation.get("score") or 0)
    fill = evaluation.get("entry_fill") if isinstance(evaluation.get("entry_fill"), dict) else {}
    quote = evaluation.get("current_quote") if isinstance(evaluation.get("current_quote"), dict) else {}
    projected = evaluation.get("projected") if isinstance(evaluation.get("projected"), dict) else {}
    activity = evaluation.get("activity") if isinstance(evaluation.get("activity"), dict) else {}
    description = (
        f"**Eligible Prediction PAPER candidate detected**\n"
        f"Side: {side} · score {score}/100 · qty {evaluation.get('quantity_contracts')}\n"
        f"Entry VWAP: USD {fill.get('vwap_dollars') or 'n/a'} · "
        f"spread USD {quote.get('spread_dollars') or 'n/a'}\n"
        f"Projected net edge/contract: USD {projected.get('net_edge_dollars_per_contract') or 'n/a'}\n"
        f"24h volume: {activity.get('volume_24h_contracts') or 'n/a'} · "
        f"OI: {activity.get('open_interest_contracts') or 'n/a'}\n"
        f"Flat deadline: {evaluation.get('flat_deadline') or 'n/a'}\n\n"
        "**Manual review required. Atlas did not open a position.**\n"
        "Unattended Prediction PAPER opening remains locked. Live capital is OFF."
    )
    return {
        "alert_key": key,
        "symbol": ticker,
        "title": f"Atlas Prediction PAPER · {ticker} {side}",
        "description": description,
        "severity": "HIGH",
        "opportunity": max(0, min(100, score)),
        "confidence": max(0, min(100, score)),
        "risk": 50,
    }


def _delivered_keys(journal: PredictionPaperJournal, *, limit: int = 1000) -> set[str]:
    rows = journal._tail_rows(journal.journal_path, limit)
    return {
        str(row.get("alert_key") or "")
        for row in rows
        if row.get("event") == ALERT_EVENT and row.get("alert_key")
    }


async def deliver_prediction_eligible_alerts(
    candidates: Iterable[dict[str, Any]],
    *,
    journal: PredictionPaperJournal = prediction_paper_journal,
    sender: Sender = send_discord_alert,
) -> dict[str, Any]:
    """Deliver eligible Discord DMs, durably deduping only successful sends."""
    attempted = delivered = deduped = failed = 0
    last_alert_key: str | None = None
    last_error: str | None = None
    delivered_keys = _delivered_keys(journal)

    for evaluation in list(candidates):
        if evaluation.get("eligible") is not True:
            continue
        try:
            payload = build_prediction_eligible_alert(evaluation)
            key = str(payload.pop("alert_key"))
        except Exception as exc:
            failed += 1
            last_error = type(exc).__name__
            continue
        if key in delivered_keys:
            deduped += 1
            continue

        attempted += 1
        try:
            ok = bool(await sender(**payload))
        except Exception as exc:
            ok = False
            last_error = type(exc).__name__
        if not ok:
            failed += 1
            last_error = last_error or "DELIVERY_NOT_CONFIRMED"
            continue

        journal.log_event({
            "event": ALERT_EVENT,
            "alert_key": key,
            "ticker": evaluation.get("ticker"),
            "side": evaluation.get("side"),
            "score": evaluation.get("score"),
            "occurrence_datetime": evaluation.get("occurrence_datetime"),
            "flat_deadline": evaluation.get("flat_deadline"),
            "strategy": evaluation.get("strategy"),
            "mode": "PAPER_RESEARCH_ONLY",
            "notification_channel": "DISCORD_DM",
            "notification_only": True,
            "manual_review_required": True,
            "automatic_paper_position_opening": False,
            "live_execution": False,
            "live_capital_allowed": False,
            "automatic_real_money_execution": False,
        })
        delivered_keys.add(key)
        delivered += 1
        last_alert_key = key
        last_error = None

    return {
        "attempted": attempted,
        "delivered": delivered,
        "deduped": deduped,
        "failed": failed,
        "last_alert_key": last_alert_key,
        "last_error": last_error,
        "notification_only": True,
        "automatic_paper_position_opening": False,
        "live_capital_allowed": False,
    }
