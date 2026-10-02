from pathlib import Path
import re
import subprocess

from fastapi.testclient import TestClient

from app.main import app


ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "backend" / "app" / "static" / "investment.html"


def test_investment_workspace_is_dedicated_and_honest():
    text = PAGE.read_text(encoding="utf-8")
    for label in (
        "Accumulation Plan",
        "Research Pipeline",
        "Sector Analysis",
        "Macro Filters",
        "Entry Models",
        "Watchlist",
        "Alerts",
        "MANUAL ONLY",
        "Live Execution",
        "DISABLED",
    ):
        assert label in text
    assert "/api/live" in text
    assert "/api/investments/quality-dips?limit=50" in text
    assert "/api/investments/prospective/report" in text
    assert "/api/perps/" not in text
    assert "UNKNOWN remains unknown" in text
    assert "candidate distribution, not portfolio exposure" in text
    assert "no automatic broker execution" in text
    assert "SECTOR CLASSIFICATION UNAVAILABLE" in text
    assert "Atlas will not infer portfolio or sector exposure." in text
    assert "entryGrid" in text


def test_investment_workspace_route_serves_no_cache_html():
    response = TestClient(app).get("/dashboard/investment")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "no-store" in response.headers["cache-control"]
    assert "Investment / Accumulation Plan" in response.text


def test_investment_inline_javascript_compiles_with_node():
    html = PAGE.read_text(encoding="utf-8")
    scripts = re.findall(r"<script(?:[^>]*)>([\s\S]*?)</script>", html)
    inline = "\n".join(script for script in scripts if script.strip())
    result = subprocess.run(
        ["node", "-e", "new Function(" + repr(inline) + "); console.log('investment-js-ok')"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "investment-js-ok" in result.stdout
