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
