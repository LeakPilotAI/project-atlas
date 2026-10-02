from pathlib import Path
import re
import subprocess

from fastapi.testclient import TestClient

from app.main import app


ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "backend" / "app" / "static" / "future_overview.html"


def test_future_overview_contract():
    text = PAGE.read_text(encoding="utf-8")
    for label in (
        "Future / Expanded Atlas Overview",
        "Prediction Markets",
        "Market Overview",
        "Price Chart",
        "Current Setup / Prediction Research",
        "Recent PAPER Trades",
        "Performance",
        "Expanded Atlas Roadmap",
        "Quality Dips Watch",
        "Integration Status",
        "News & Events",
    ):
        assert label in text

    for endpoint in (
        "/api/command-center/summary",
        "/api/live",
        "/api/perps/manual/board?limit=10",
        "/api/archive/paper-trades?limit=100",
        "/api/investments/quality-dips?limit=8",
        "/api/perps/candles?symbol=",
        "/api/prediction/status",
        "/api/prediction/markets?status=open&limit=6",
    ):
        assert endpoint in text

    assert "Kalshi Public Market Research" in text
    assert "Public market discovery / normalized metadata" in text
    assert "No Kalshi API key or portfolio access" in text
    assert "No order submission or live execution" in text
    assert "PAPER outcome ledger, settlement verification and calibration remain" in text
    assert "no automatic real-money execution" in text
    assert "body.embedded .domainNav{display:none}" in text
    assert "new URLSearchParams(location.search).get('embed')==='1'" in text

    # Reference mock telemetry must not be copied into the real future shell.
    assert "$426,318.24" not in text
    assert "64.2%" not in text
    assert "111 wins / 62 losses" not in text
    # Guard the mock "234 markets tracked" telemetry without matching incidental
    # CSS hex fragments such as "#23434d".
    assert ">234<" not in text
    assert "234 markets" not in text.lower()
    assert "PLACE PAPER ORDER" not in text
    assert "Create Custom Markets" not in text
    assert "Trade Event Outcomes" not in text
    assert "method:'POST'" not in text


def test_future_overview_route_serves_no_cache_html():
    response = TestClient(app).get("/dashboard/future")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "no-store" in response.headers["cache-control"]
    assert "Future / Expanded Atlas Overview" in response.text


def test_future_overview_inline_javascript_compiles_with_node():
    html = PAGE.read_text(encoding="utf-8")
    scripts = re.findall(r"<script(?:[^>]*)>([\s\S]*?)</script>", html)
    inline = "\n".join(script for script in scripts if script.strip())
    result = subprocess.run(
        ["node", "-e", "new Function(" + repr(inline) + "); console.log('future-overview-js-ok')"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "future-overview-js-ok" in result.stdout
