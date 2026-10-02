from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app


ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "backend" / "app" / "static"

SURFACES = (
    "dashboard_shell.html",
    "quality_dips.html",
    "investment.html",
    "archive.html",
    "archive_export.html",
    "archive_paper_trades.html",
    "archive_research.html",
    "archive_snapshots.html",
    "command_center.html",
    "command_center_health.html",
    "command_center_risk.html",
    "future_overview.html",
    "prediction_paper.html",
)


def test_frontend_freeze_surfaces_have_responsive_runtime_contract():
    for name in SURFACES:
        text = (STATIC / name).read_text(encoding="utf-8")
        assert 'name="viewport"' in text, name
        assert "@media" in text, name
        assert "/static/runtime_poll.js" in text, name
        assert "atlasFetch(" in text, name


def test_shared_runtime_exposes_loading_ready_degraded_and_error_states():
    text = (STATIC / "runtime_poll.js").read_text(encoding="utf-8")
    for token in (
        "atlasSetSurfaceState",
        "Loading workspace",
        "Live data ready",
        "Data read failed",
        "Refresh failed",
        'data-state="degraded"',
        'data-state="error"',
        "prefers-reduced-motion",
        ":focus-visible",
    ):
        assert token in text


def test_dashboard_shell_has_lazy_loading_error_retry_and_mobile_contract():
    text = (STATIC / "dashboard_hub.html").read_text(encoding="utf-8")
    for token in (
        "paneState",
        "Retry workspace",
        "aria-busy",
        "aria-selected",
        "focus-visible",
        "prefers-reduced-motion",
        "overflow-x:auto",
        "frame.addEventListener('load'",
        "frame.addEventListener('error'",
    ):
        assert token in text


def test_frontend_freeze_routes_are_reachable():
    client = TestClient(app)
    routes = (
        "/dashboard",
        "/dashboard/perps",
        "/api/investments/quality-dips/view",
        "/dashboard/investment",
        "/dashboard/archive",
        "/dashboard/archive/export",
        "/dashboard/archive/paper-trades",
        "/dashboard/archive/research",
        "/dashboard/archive/snapshots",
        "/dashboard/command-center",
        "/dashboard/command-center/health",
        "/dashboard/command-center/risk",
        "/dashboard/future",
        "/dashboard/prediction-paper",
    )
    for route in routes:
        response = client.get(route)
        assert response.status_code == 200, route
