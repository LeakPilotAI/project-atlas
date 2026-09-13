from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app


ROOT = Path(__file__).resolve().parents[1]
HUB = ROOT / "backend" / "app" / "static" / "dashboard_hub.html"
LEGACY = ROOT / "backend" / "app" / "static" / "dashboard.html"


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


def test_legacy_paper_ui_distinguishes_micro_recovery_from_other_paper():
    text = LEGACY.read_text(encoding="utf-8")
    assert "Micro recovery: persisted" in text
    assert "other paper" in text
    assert "Other paper strategies are isolated" in text
    assert "startup-recovered" in text


def test_legacy_dashboard_escapes_dynamic_html():
    text = LEGACY.read_text(encoding="utf-8")
    assert "'&':'&amp;'" in text
    assert "'<':'&lt;'" in text
    assert "'>':'&gt;'" in text
    assert "'\"':'&quot;'" in text
