import asyncio

from app.investment.quality_dips_v3_delivery import deliver_v3_events
from app.investment.quality_dips_v3_state import QualityDipsV3StateStore


async def _ok_sender(**kwargs):
    return True


async def _fail_sender(**kwargs):
    return False


def _event():
    return {
        "key": "V3:MSFT:LEVEL:L1",
        "event_type": "ENTRY_LEVEL_REACHED",
        "symbol": "MSFT",
        "message": "manual research only",
    }


def test_delivery_marks_success_and_skips_duplicate(tmp_path):
    store = QualityDipsV3StateStore(tmp_path / "v3.json")
    store.mark_event("V3:MSFT:LEVEL:L1", symbol="MSFT", event_type="ENTRY_LEVEL_REACHED", payload=_event())
    first = asyncio.run(deliver_v3_events([_event()], store=store, sender=_ok_sender))
    second = asyncio.run(deliver_v3_events([_event()], store=store, sender=_ok_sender))
    assert first == {"attempted": 1, "delivered": 1, "failed": 0, "skipped": 0}
    assert second["attempted"] == 0
    assert second["skipped"] == 1
    assert store.get_event("V3:MSFT:LEVEL:L1")["delivery"]["attempts"] == 1


def test_failed_delivery_remains_retryable(tmp_path):
    store = QualityDipsV3StateStore(tmp_path / "v3.json")
    store.mark_event("V3:MSFT:LEVEL:L1", symbol="MSFT", event_type="ENTRY_LEVEL_REACHED", payload=_event())
    failed = asyncio.run(deliver_v3_events([_event()], store=store, sender=_fail_sender))
    retried = asyncio.run(deliver_v3_events([_event()], store=store, sender=_ok_sender))
    assert failed["failed"] == 1
    assert retried["delivered"] == 1
    delivery = store.get_event("V3:MSFT:LEVEL:L1")["delivery"]
    assert delivery["attempts"] == 2
    assert delivery["delivered"] is True
