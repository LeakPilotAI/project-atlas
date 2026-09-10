import pytest

from app.services.perp_alert_delivery import build_perp_alert, deliver_alert_candidates


def candidate(**overrides):
    row = {
        "setup_key": "BTC:LONG",
        "symbol": "BTC",
        "side": "LONG",
        "tier": "PRIME",
        "state": "PREPARE",
        "score": 88.4,
        "price": 100000.0,
        "alert_eligible": True,
        "alert_reason": "new actionable PRIME setup",
        "next_action": "Prepare L1; do not chase.",
        "levels": {"l1": 99500.0, "l2": 99000.0, "l3": 98500.0, "stop": 97500.0, "tp1": 103000.0, "tp2": 106000.0},
    }
    row.update(overrides)
    return row


def test_alert_payload_is_manual_hyperliquid_guidance():
    payload = build_perp_alert(candidate())
    assert payload["symbol"] == "BTC"
    assert "PRIME BTC LONG" in payload["title"]
    assert "L1" in payload["description"]
    assert "no order was placed" in payload["description"]
    assert payload["severity"] == "HIGH"


@pytest.mark.asyncio
async def test_successful_delivery_acknowledges_candidate():
    sent = []
    acked = []

    async def sender(**payload):
        sent.append(payload)
        return True

    result = await deliver_alert_candidates(
        [candidate()], acknowledge=lambda key: acked.append(key) or True, sender=sender
    )
    assert result == {"attempted": 1, "delivered": 1, "acknowledged": 1, "failed": 0}
    assert acked == ["BTC:LONG"]
    assert len(sent) == 1


@pytest.mark.asyncio
async def test_failed_delivery_is_not_acknowledged():
    acked = []

    async def sender(**payload):
        return False

    result = await deliver_alert_candidates(
        [candidate()], acknowledge=lambda key: acked.append(key) or True, sender=sender
    )
    assert result["failed"] == 1
    assert result["acknowledged"] == 0
    assert acked == []


@pytest.mark.asyncio
async def test_sender_exception_is_contained_and_not_acknowledged():
    async def sender(**payload):
        raise RuntimeError("discord unavailable")

    result = await deliver_alert_candidates([candidate()], acknowledge=lambda key: True, sender=sender)
    assert result == {"attempted": 1, "delivered": 0, "acknowledged": 0, "failed": 1}


@pytest.mark.asyncio
async def test_ineligible_candidate_is_never_sent():
    calls = 0

    async def sender(**payload):
        nonlocal calls
        calls += 1
        return True

    result = await deliver_alert_candidates(
        [candidate(alert_eligible=False)], acknowledge=lambda key: True, sender=sender
    )
    assert result["attempted"] == 0
    assert calls == 0
