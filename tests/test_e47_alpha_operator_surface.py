from pathlib import Path
from fastapi.testclient import TestClient
from app.main import app

client=TestClient(app)
DASH=Path(__file__).parents[1]/"backend"/"app"/"static"/"dashboard.html"

def test_e47_governance_exposes_read_only_source_observability():
    r=client.get("/api/validation/e42-alpha-governance")
    assert r.status_code==200
    data=r.json()
    assert "source_observability" in data
    for row in data["source_observability"].values():
        assert set(("health","last_observed_at","last_fetched_at","last_finished_at","last_outcome","last_http_status","last_parse_result")) <= set(row)
    assert data["execution_authority"] is False
    assert data["paper_entry_authority"] is False
    assert data["strategy_mutation_authority"] is False
    assert data["membership_mutation_authority"] is False
    assert data["threshold_mutation_authority"] is False
    assert data["live_capital_allowed"] is False

def test_e47_dashboard_renders_cadence_drift_sources_and_context_only_guardrails():
    html=DASH.read_text(encoding="utf-8")
    for token in ("Read-only intelligence","source_observability","current≤24h","threshold ${C.threshold_breach","drift ${C.drift_flag","split ${C.decouple_recommended","Corroboration: ${support}","official provenance"):
        assert token in html
    assert "no order, PAPER-entry, strategy, membership, threshold, promotion, or live-capital authority" in html

def test_e47_dashboard_handles_zero_corroboration_explicitly():
    html=DASH.read_text(encoding="utf-8")
    assert 'join(", ")||"none"' in html
    assert "No current governed Alpha events." in html