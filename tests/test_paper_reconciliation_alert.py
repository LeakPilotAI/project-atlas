import asyncio

import app.services.paper_reconciliation_alert as alert_mod


async def _sender(**kwargs):
    return True


def test_reconciliation_alert_skips_when_clean(monkeypatch):
    monkeypatch.setattr(alert_mod, "reconciliation_summary", lambda: {"reconciliation_ok": True})
    out=asyncio.run(alert_mod.alert_reconciliation_if_needed(sender=_sender))
    assert out["attempted"] == 0
    assert out["reconciliation_ok"] is True


def test_reconciliation_alert_sends_when_broken(monkeypatch):
    monkeypatch.setattr(alert_mod, "reconciliation_summary", lambda: {
        "reconciliation_ok": False,
        "duplicate_fill_count": 2,
        "journal_currently_open": 1,
    })
    out=asyncio.run(alert_mod.alert_reconciliation_if_needed(sender=_sender))
    assert out["attempted"] == 1
    assert out["delivered"] == 1
    assert out["reconciliation_ok"] is False
