import asyncio

import app.services.perp_alert_delivery as delivery_mod


def test_runtime_loop_tracks_reconciliation_result(monkeypatch):
    service=delivery_mod.PerpAlertDeliveryService(interval_seconds=5.0)
    service.running=True

    async def fake_paper_once():
        service.running=False
        return {}
    async def fake_deliver_once():
        return {}
    async def fake_reconcile():
        return {"attempted":1,"delivered":1,"reconciliation_ok":False}

    monkeypatch.setattr(service,"paper_once",fake_paper_once)
    monkeypatch.setattr(service,"deliver_once",fake_deliver_once)
    import app.services.paper_reconciliation_alert as alert_mod
    monkeypatch.setattr(alert_mod,"alert_reconciliation_if_needed",fake_reconcile)

    asyncio.run(service._loop())
    assert service.last_reconciliation_result["attempted"] == 1
    assert service.last_reconciliation_result["reconciliation_ok"] is False


def test_runtime_reconciliation_alert_stays_on_main_event_loop():
    from pathlib import Path
    text = (Path(__file__).resolve().parents[1] / "backend/app/services/perp_alert_delivery.py").read_text(encoding="utf-8")
    assert "self.last_reconciliation_result = await alert_reconciliation_if_needed()" in text
    assert "asyncio.run(alert_reconciliation_if_needed())" not in text


def test_runtime_loop_records_step_timings():
    service = delivery_mod.PerpAlertDeliveryService(interval_seconds=5.0)
    service.running = True

    async def fake_paper_once():
        return {}
    async def fake_deliver_once():
        return {}

    async def fake_reconcile():
        service.running = False
        return {"attempted": 0, "delivered": 0, "reconciliation_ok": True}

    async def run():
        import app.services.paper_reconciliation_alert as alert_mod
        old = alert_mod.alert_reconciliation_if_needed
        alert_mod.alert_reconciliation_if_needed = fake_reconcile
        try:
            await service._loop()
        finally:
            alert_mod.alert_reconciliation_if_needed = old

    asyncio.run(run())
    status = service.reconciliation_status()
    assert set(status["last_step_timings_ms"]) >= {"paper_once", "deliver_once", "reconciliation"}
    assert status["last_cycle_elapsed_ms"] >= 0
