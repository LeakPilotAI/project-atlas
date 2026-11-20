from pathlib import Path
import re
import subprocess

from fastapi.testclient import TestClient

from app.main import app


ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "backend" / "app" / "static" / "command_center.html"


def test_command_center_overview_page_contract():
    text = PAGE.read_text(encoding="utf-8")
    for label in (
        "Domain Overview",
        "PAPER Performance",
        "Active Systems",
        "Open PAPER Positions",
        "Execution Queue",
        "Recent Alerts",
        "Guardrails",
        "Top Setups",
        "Quick Actions",
        "NO ORDER ACTIONS",
    ):
        assert label in text

    for endpoint in (
        "/api/command-center/summary",
        "/api/live",
        "/api/perps/manual/board?limit=8",
        "/api/perps/paper-risk",
        "/diagnostics/paper-reconciliation",
        "/health",
        "/api/archive/paper-trades?limit=500",
    ):
        assert endpoint in text

    assert "MANUAL / PAPER" in text
    assert "real-money auto execution disabled" in text
    assert "Command Center places no orders" in text
    assert "navigation only" in text
    assert "TOTAL PORTFOLIO (PAPER)" not in text
    assert "$426,318.24" not in text
    assert "99.98%" not in text
    assert "EMERGENCY STOP" not in text
    assert "fetch('/api/" not in text or "method:'POST'" not in text


def test_command_center_overview_route_serves_no_cache_html():
    response = TestClient(app).get("/dashboard/command-center")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "no-store" in response.headers["cache-control"]
    assert "Command Center / Overview" in response.text


def test_command_center_overview_inline_javascript_compiles_with_node():
    html = PAGE.read_text(encoding="utf-8")
    scripts = re.findall(r"<script(?:[^>]*)>([\s\S]*?)</script>", html)
    inline = "\n".join(script for script in scripts if script.strip())
    result = subprocess.run(
        ["node", "-e", "new Function(" + repr(inline) + "); console.log('command-overview-js-ok')"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "command-overview-js-ok" in result.stdout
