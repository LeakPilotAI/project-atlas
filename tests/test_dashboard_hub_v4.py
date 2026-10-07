from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app


ROOT = Path(__file__).resolve().parents[1]
HUB = ROOT / "backend" / "app" / "static" / "dashboard_hub.html"
LEGACY = ROOT / "backend" / "app" / "static" / "dashboard.html"


def test_dashboard_hub_has_three_isolated_domains():
    text = HUB.read_text(encoding="utf-8")
    for name in ("Perp Day Trade", "Quality Dips", "Investment", "Archive", "Command Center", "Prediction Markets"):
        assert name in text
    assert 'src="/dashboard/perps?embed=1"' in text
    assert 'data-src="/api/investments/quality-dips/view"' in text
    assert 'data-src="/dashboard/investment"' in text
    assert 'data-src="/dashboard/archive"' in text
    assert "COMING SOON" in text
    assert 'data-src="/dashboard/command-center"' in text
    assert 'data-src="/dashboard/prediction-paper"' in text
    assert 'Prediction Markets <span class="soon">PAPER</span>' in text
    assert '.nav .tab[data-pane="analytics"],.nav .tab[data-pane="portfolio"]{display:none}' in text
    assert '.nav .tab[data-pane="prediction"]' not in text.split('{display:none}', 1)[0].splitlines()[-1]
    command_pos = text.index('data-pane="command"')
    prediction_pos = text.index('data-pane="prediction"')
    assert command_pos < prediction_pos
    command = text.split('id="pane-command"', 1)[1].split("</section>", 1)[0]
    assert "<iframe" in command
    assert "if(frame && !frame.getAttribute('src'))" in text


def test_dashboard_routes_preserve_perp_and_legacy_views():
    client = TestClient(app)
    assert client.get("/dashboard").status_code == 200
    assert client.get("/dashboard/perps").status_code == 200
    assert client.get("/dashboard/investment").status_code == 200
    assert client.get("/dashboard/archive").status_code == 200
    assert client.get("/dashboard/archive/export").status_code == 200
    assert client.get("/dashboard/archive/paper-trades").status_code == 200
    assert client.get("/dashboard/archive/research").status_code == 200
    assert client.get("/dashboard/archive/snapshots").status_code == 200
    assert client.get("/dashboard/command-center").status_code == 200
    assert client.get("/dashboard/command-center/health").status_code == 200
    assert client.get("/dashboard/command-center/risk").status_code == 200
    assert client.get("/dashboard/future").status_code == 200
    assert client.get("/dashboard/prediction-paper").status_code == 200
    assert client.get("/dashboard/legacy").status_code == 200


def test_perp_decorative_backdrop_is_served_as_an_image():
    response = TestClient(app).get("/static/atlas-perp-backdrop.png")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.content.startswith(b"\x89PNG\r\n\x1a\n")


def test_root_advertises_domain_specific_dashboard_routes():
    client = TestClient(app)
    payload = client.get("/").json()
    assert payload["dashboard"] == "/dashboard"
    assert payload["dashboard_perps"] == "/dashboard/perps"
    assert payload["dashboard_quality_dips"] == "/api/investments/quality-dips/view"
    assert payload["dashboard_investment"] == "/dashboard/investment"
    assert payload["dashboard_archive"] == "/dashboard/archive"
    assert payload["dashboard_archive_export"] == "/dashboard/archive/export"
    assert payload["dashboard_archive_paper_trades"] == "/dashboard/archive/paper-trades"
    assert payload["dashboard_archive_research"] == "/dashboard/archive/research"
    assert payload["dashboard_archive_snapshots"] == "/dashboard/archive/snapshots"
    assert payload["dashboard_command_center"] == "/dashboard/command-center"
    assert payload["dashboard_command_center_health"] == "/dashboard/command-center/health"
    assert payload["dashboard_command_center_risk"] == "/dashboard/command-center/risk"
    assert payload["dashboard_future"] == "/dashboard/future"
    assert payload["dashboard_prediction_paper"] == "/dashboard/prediction-paper"
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


def test_prediction_paper_workspace_is_read_only_evidence_surface():
    text = (ROOT / "backend" / "app" / "static" / "prediction_paper.html").read_text(encoding="utf-8")
    for token in (
        "AUTO-OPEN LOCKED · LIVE OFF",
        "/api/prediction/paper/status?limit=100",
        "/api/prediction/paper/candidates?limit=200",
        "Recent Candidate Evidence",
        "PAPER Position / Trade Events",
        "depth-aware",
        "atlasPoll(refresh,10000)",
    ):
        assert token in text
    assert "/paper/open/" not in text
    assert "/paper/close" not in text
    assert "LIVE CAPITAL OFF" in text
