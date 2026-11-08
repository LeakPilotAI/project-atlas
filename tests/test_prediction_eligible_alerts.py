from __future__ import annotations

import asyncio

from app.prediction.eligible_alerts import (
    ALERT_EVENT,
    build_prediction_eligible_alert,
    deliver_prediction_eligible_alerts,
)
from app.prediction.paper_engine import PredictionPaperJournal
from app.prediction.prediction_paper_automation import PredictionPaperAutomation


def _evaluation() -> dict:
    return {
        "eligible": True,
        "ticker": "KXTEST-A",
        "side": "YES",
        "score": 88,
        "quantity_contracts": "10",
        "occurrence_datetime": "2026-10-02T18:00:00+00:00",
        "flat_deadline": "2026-10-02T17:30:00+00:00",
        "strategy": "PRE_EVENT_RECENT_RECLAIM_V1",
        "entry_fill": {"vwap_dollars": "0.42"},
        "current_quote": {"spread_dollars": "0.03"},
        "projected": {"net_edge_dollars_per_contract": "0.04"},
        "activity": {
            "volume_24h_contracts": "500",
            "open_interest_contracts": "300",
        },
    }


def _journal(tmp_path):
    return PredictionPaperJournal(
        journal_path=tmp_path / "paper.jsonl",
        candidate_path=tmp_path / "candidates.jsonl",
    )


def test_prediction_eligible_alert_payload_is_notification_only():
    payload = build_prediction_eligible_alert(_evaluation())
    assert payload["title"].startswith("Atlas Prediction PAPER")
    assert "Manual review required. Atlas did not open a position." in payload["description"]
    assert "Unattended Prediction PAPER opening remains locked." in payload["description"]
    assert "Live capital is OFF." in payload["description"]


def test_prediction_eligible_alert_delivers_once_and_durably_dedupes(tmp_path):
    journal = _journal(tmp_path)
    sent = []

    async def sender(**payload):
        sent.append(payload)
        return True

    first = asyncio.run(deliver_prediction_eligible_alerts(
        [_evaluation()], journal=journal, sender=sender
    ))
    second = asyncio.run(deliver_prediction_eligible_alerts(
        [_evaluation()], journal=journal, sender=sender
    ))

    assert first["attempted"] == 1
    assert first["delivered"] == 1
    assert first["failed"] == 0
    assert second["attempted"] == 0
    assert second["delivered"] == 0
    assert second["deduped"] == 1
    assert len(sent) == 1
    events = journal._rows(journal.journal_path)
    delivered = [row for row in events if row.get("event") == ALERT_EVENT]
    assert len(delivered) == 1
    assert delivered[0]["notification_only"] is True
    assert delivered[0]["automatic_paper_position_opening"] is False
    assert delivered[0]["live_capital_allowed"] is False
    assert journal.open_trade() is None


def test_prediction_eligible_alert_failed_send_is_retryable(tmp_path):
    journal = _journal(tmp_path)
    attempts = {"count": 0}

    async def sender(**payload):
        attempts["count"] += 1
        return attempts["count"] > 1

    first = asyncio.run(deliver_prediction_eligible_alerts(
        [_evaluation()], journal=journal, sender=sender
    ))
    second = asyncio.run(deliver_prediction_eligible_alerts(
        [_evaluation()], journal=journal, sender=sender
    ))

    assert first["attempted"] == 1
    assert first["failed"] == 1
    assert first["delivered"] == 0
    assert second["attempted"] == 1
    assert second["delivered"] == 1
    assert attempts["count"] == 2
    assert journal.open_trade() is None


def test_prediction_automation_status_keeps_alerts_notification_only():
    status = PredictionPaperAutomation().status()
    alerts = status["eligible_notifications"]
    assert alerts["channel"] == "DISCORD_DM"
    assert alerts["notification_only"] is True
    assert alerts["manual_review_required"] is True
    assert alerts["durable_success_dedupe"] is True
    assert alerts["retry_failed_delivery"] is True
    assert alerts["automatic_paper_position_opening"] is False
    assert alerts["live_execution"] is False
    assert alerts["live_capital_allowed"] is False
    assert status["unattended_paper_open_enabled"] is False
    assert status["automatic_paper_position_opening"] is False
