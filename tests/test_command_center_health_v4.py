from pathlib import Path
import re
import subprocess

from fastapi.testclient import TestClient

from app.main import app


ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "backend" / "app" / "static" / "command_center_health.html"


def test_command_center_health_page_contract():
    text = PAGE.read_text(encoding="utf-8")
    for label in (
        "Core Services",
        "Request Performance",
        "Data Feed Status",
        "Endpoint Response Times",
        "PAPER Execution Health",
        "Current Health Findings",
        "Archive Data Stores",
        "Instrumentation Coverage",
        "Health Actions",
        "HOST CPU / MEMORY / NETWORK NOT INSTRUMENTED",
        "NO RESTART / CACHE-CLEAR ACTIONS HERE",
    ):
        assert label in text

    for endpoint in (
        "/health",
        "/api/command-center/summary",
        "/api/live",
        "/api/perps/manual/board?limit=8",
        "/api/perps/paper-risk",
        "/diagnostics/paper-reconciliation",
        "/api/archive/export/summary",
    ):
        assert endpoint in text

    assert "page-observed average" in text
    assert "page session samples" in text
    assert "live capital OFF" in text
    assert "99.98%" not in text
    assert "42 ms" not in text
    assert "247 (100%)" not in text
    assert "RESTART MODULE" not in text
    assert "CLEAR CACHE" not in text
    assert "method:'POST'" not in text


def test_command_center_health_route_serves_no_cache_html():
    response = TestClient(app).get("/dashboard/command-center/health")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "no-store" in response.headers["cache-control"]
    assert "Command Center / System Health" in response.text


def test_command_center_health_inline_javascript_compiles_with_node():
    html = PAGE.read_text(encoding="utf-8")
    scripts = re.findall(r"<script(?:[^>]*)>([\s\S]*?)</script>", html)
    inline = "\n".join(script for script in scripts if script.strip())
    result = subprocess.run(
        ["node", "-e", "new Function(" + repr(inline) + "); console.log('command-health-js-ok')"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "command-health-js-ok" in result.stdout
