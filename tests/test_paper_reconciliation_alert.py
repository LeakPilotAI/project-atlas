import asyncio
from datetime import datetime, timedelta, timezone

import app.services.paper_reconciliation_alert as alert_mod


async def _sender(**kwargs):
    return True


def setup_function():
    alert_mod.reset_reconciliation_alert_state()


def test_reconciliation_alert_skips_when_clean(monkeypatch):
    monkeypatch.setattr(alert_mod, "reconciliation_summary", lambda: {"reconciliation_ok": True})
    out=asyncio.run(alert_mod.alert_reconciliation_if_needed(sender=_sender))
    assert out["attempted"] == 0
    assert out["reconciliation_ok"] is True
    assert out["suppressed"] is False


def test_reconciliation_alert_sends_when_broken(monkeypatch):
    monkeypatch.setattr(alert_mod, "reconciliation_summary", lambda: {
        "reconciliation_ok": False,
        "duplicate_fill_count": 2,
        "duplicate_fill_instances": ["a", "b"],
        "journal_currently_open": 1,
    })
    out=asyncio.run(alert_mod.alert_reconciliation_if_needed(sender=_sender))
    assert out["attempted"] == 1
    assert out["delivered"] == 1
    assert out["reconciliation_ok"] is False
    assert out["suppressed"] is False


def test_reconciliation_alert_dedupes_inside_cooldown(monkeypatch):
    rec = {
        "reconciliation_ok": False,
        "duplicate_fill_count": 1,
        "duplicate_fill_instances": ["dup-1"],
        "journal_currently_open": 1,
    }
    monkeypatch.setattr(alert_mod, "reconciliation_summary", lambda: rec)
    t0 = datetime(2026, 9, 19, tzinfo=timezone.utc)
    first = asyncio.run(alert_mod.alert_reconciliation_if_needed(sender=_sender, cooldown_seconds=900, now=t0))
    second = asyncio.run(alert_mod.alert_reconciliation_if_needed(sender=_sender, cooldown_seconds=900, now=t0 + timedelta(seconds=60)))
    assert first["attempted"] == 1
    assert second["attempted"] == 0
    assert second["suppressed"] is True
    assert second["suppression_reason"] == "cooldown"


def test_reconciliation_alert_sends_immediately_when_signature_changes(monkeypatch):
    current = {
        "reconciliation_ok": False,
        "duplicate_fill_count": 1,
        "duplicate_fill_instances": ["dup-1"],
        "journal_currently_open": 1,
    }
    monkeypatch.setattr(alert_mod, "reconciliation_summary", lambda: current)
    t0 = datetime(2026, 9, 19, tzinfo=timezone.utc)
    asyncio.run(alert_mod.alert_reconciliation_if_needed(sender=_sender, cooldown_seconds=900, now=t0))
    current["duplicate_fill_count"] = 2
    current["duplicate_fill_instances"] = ["dup-1", "dup-2"]
    out = asyncio.run(alert_mod.alert_reconciliation_if_needed(sender=_sender, cooldown_seconds=900, now=t0 + timedelta(seconds=10)))
    assert out["attempted"] == 1
    assert out["suppressed"] is False
