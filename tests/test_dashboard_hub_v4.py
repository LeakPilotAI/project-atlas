from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app


ROOT = Path(__file__).resolve().parents[1]
HUB = ROOT / "backend" / "app" / "static" / "dashboard_hub.html"


def test_dashboard_hub_has_three_isolated_domains():
    text = HUB.read_text(encoding="utf-8")
    assert "Perp Day Trade" in text
    assert "Quality Dips" in text
    assert "Command Center / Paper" in text
    assert 'src="/dashboard/perps"' in text
    assert 'src="/api/investments/quality-dips/view"' in text
    assert 'src="/dashboard/legacy"' in text
    assert "HYPERLIQUID_PERPS" in text
    assert "EQUITY_INVESTMENT" in text


def test_dashboard_routes_preserve_perp_and_legacy_views():
    client = TestClient(app)
    assert client.get("/dashboard").status_code == 200
    assert client.get("/dashboard/perps").status_code == 200
    assert client.get("/dashboard/legacy").status_code == 200


def test_root_advertises_domain_specific_dashboard_routes():
    client = TestClient(app)
    payload = client.get("/").json()
    assert payload["dashboard"] == "/dashboard"
    assert payload["dashboard_perps"] == "/dashboard/perps"
    assert payload["dashboard_quality_dips"] == "/api/investments/quality-dips/view"
    assert payload["dashboard_legacy"] == "/dashboard/legacy"
