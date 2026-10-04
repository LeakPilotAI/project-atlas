from pathlib import Path
import re
import subprocess

from fastapi.testclient import TestClient

from app.main import app


ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "backend" / "app" / "static" / "command_center_risk.html"


def test_command_center_risk_page_contract():
    text = PAGE.read_text(encoding="utf-8")
    for label in (
        "Risk Limits",
        "Daily PAPER Risk Monitor",
        "Automated PAPER Guards",
        "Open Position Risk",
        "Policy Headroom",
        "Recent PAPER Risk Events",
        "Risk Boundary Scenarios",
        "PAPER Kill Switch",
        "CORRELATION / MARGIN RISK NOT INSTRUMENTED",
        "SIMULATION ONLY",
    ):
        assert label in text

    for endpoint in (
        "/api/perps/paper-risk",
        "/api/live",
        "/api/perps/manual/board?limit=25",
        "/api/archive/paper-trades?limit=500",
        "/diagnostics/paper-reconciliation",
        "/api/perps/paper-risk/kill-switch?enabled=",
    ):
        assert endpoint in text

    assert "blocks new auto-mirrored PAPER fills" in text
    assert "does not close existing PAPER positions" in text
    assert "automatic real-money execution disabled" in text
    assert "Total Risk Exposure" not in text
    assert "18.4%" not in text
    assert "Correlation Matrix" not in text
    assert "3x" not in text
    assert "method:'POST'" in text


def test_command_center_risk_route_serves_no_cache_html():
    response = TestClient(app).get("/dashboard/command-center/risk")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "no-store" in response.headers["cache-control"]
    assert "Command Center / Risk Controls" in response.text


def test_command_center_risk_inline_javascript_compiles_with_node():
    html = PAGE.read_text(encoding="utf-8")
    scripts = re.findall(r"<script(?:[^>]*)>([\s\S]*?)</script>", html)
    inline = "\n".join(script for script in scripts if script.strip())
    result = subprocess.run(
        ["node", "-e", "new Function(" + repr(inline) + "); console.log('command-risk-js-ok')"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "command-risk-js-ok" in result.stdout
