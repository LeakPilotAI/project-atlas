from pathlib import Path


def test_perp_router_has_no_deprecated_event_hooks() -> None:
    text = Path("backend/app/api/perp_manual.py").read_text(encoding="utf-8")
    assert '@router.on_event("startup")' not in text
    assert '@router.on_event("shutdown")' not in text


def test_app_lifespan_owns_perp_alert_delivery_worker() -> None:
    text = Path("backend/app/main.py").read_text(encoding="utf-8")
    assert "from app.services.perp_alert_delivery import perp_alert_delivery_service" in text
    assert '("perp_alert_delivery", perp_alert_delivery_service.start)' in text
    assert '("perp_alert_delivery", perp_alert_delivery_service.stop)' in text
    assert '"perp_alert_delivery_running"' in text
