import asyncio

from app.api.diagnostics import diagnostics_paper_reconciliation
from app.services.paper_execution_model import PAPER_EXECUTION_MODEL_VERSION, execution_assumptions
from app.services.perp_alert_delivery import PerpAlertDeliveryService


def test_execution_assumptions_are_versioned():
    assumptions = execution_assumptions()
    assert assumptions["version"] == PAPER_EXECUTION_MODEL_VERSION
    assert assumptions["execution"] == "PAPER_ONLY"


def test_runtime_reconciliation_status_is_operator_safe():
    service = PerpAlertDeliveryService(interval_seconds=5)
    service.last_reconciliation_result = {
        "attempted": 0,
        "delivered": 0,
        "reconciliation_ok": False,
        "suppressed": True,
    }
    out = service.reconciliation_status()
    assert out["last_result"]["reconciliation_ok"] is False
    assert out["execution"] == "PAPER_ONLY"
    assert out["live_capital_allowed"] is False


def test_reconciliation_diagnostics_exposes_current_and_runtime(monkeypatch):
    import app.services.perp_paper_observability as obs
    import app.services.perp_alert_delivery as delivery

    monkeypatch.setattr(obs, "reconciliation_summary", lambda: {
        "reconciliation_ok": True,
        "duplicate_fill_count": 0,
    })
    delivery.perp_alert_delivery_service.last_reconciliation_result = {
        "attempted": 0,
        "delivered": 0,
        "reconciliation_ok": True,
    }
    out = asyncio.run(diagnostics_paper_reconciliation())
    assert out["current"]["reconciliation_ok"] is True
    assert out["runtime"]["last_result"]["reconciliation_ok"] is True
    assert out["automatic_real_money_execution"] is False


def test_reconciliation_diagnostics_offloads_durable_history_scan():
    text = (ROOT / "backend/app/api/diagnostics.py").read_text(encoding="utf-8")
    assert "await asyncio.to_thread(reconciliation_summary)" in text
