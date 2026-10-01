from pathlib import Path
import asyncio

import app.api.perp_manual as perp_api


def _read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def test_dashboard_shell_is_hyperliquid_manual_only():
    html = _read("backend/app/static/dashboard_shell.html")
    assert "Perp Day Trade" in html
    assert "HYPERLIQUID ONLY · MANUAL EXECUTION" in html
    assert "/api/perps/manual/board" in html
    assert "/api/perps/manual/setups/" in html
    assert "/api/perps/manual/plans/" in html
    assert "Atlas never places an order" in html


def test_dashboard_shell_preserves_existing_dashboard_workspace():
    html = _read("backend/app/static/dashboard_shell.html")
    assert 'src="/dashboard/legacy"' in html
    assert "Command Center / Paper / Quality Dips" in html


def test_main_serves_shell_and_legacy_dashboard():
    main = _read("backend/app/main.py")
    assert 'DASHBOARD_HTML = STATIC_DIR / "dashboard_hub.html"' in main
    assert 'PERP_DASHBOARD_HTML = STATIC_DIR / "dashboard_shell.html"' in main
    assert 'LEGACY_DASHBOARD_HTML = STATIC_DIR / "dashboard.html"' in main
    assert '@app.get("/dashboard/legacy")' in main


def test_perp_shell_has_no_equity_data_endpoints():
    html = _read("backend/app/static/dashboard_shell.html")
    assert "yahoo" not in html.lower()
    assert "/api/live" not in html
    assert "equity_majors" not in html


def test_perp_shell_renders_authoritative_manual_instruction_and_blocks_unsafe_entry():
    html = _read("backend/app/static/dashboard_shell.html")
    assert "manual_instruction" in html
    assert "NO NEW ORDER" in html
    assert "PLACE_RESTING_L1" in html
    assert "RESTING L1 VERIFIED" in html
    assert "MARK FILLED AFTER AXIOM FILLS" in html
    assert "Only use this AFTER your Axiom limit actually fills" in html


def test_perp_shell_uses_auto_paper_counter_instead_of_manual_fill_counter():
    html = _read("backend/app/static/dashboard_shell.html")
    assert "Auto paper open" in html
    assert "AUTO-PAPER IS AUTOMATIC" in html
    assert "S.auto_paper" in html
    assert "arms valid manual L1; fills only on touch" in html
    assert "regardless of display tier" in html
    assert "paper opens only when price touches or crosses L1" in html
    assert "PRIME/QUALIFIED manual setup" not in html
    assert '<div class="label">Manual fills</div>' not in html


def test_perp_shell_has_contextual_views_and_real_candle_chart_contract():
    html = _read("backend/app/static/dashboard_shell.html")
    for label in ("Live Board", "Open Positions", "Paper Journal", "Risk Monitor", "Market Map", "Scanner", "Alerts"):
        assert label in html
    assert "/api/perps/paper-risk" in html
    assert "/api/perps/candles" in html
    assert "REAL HYPERLIQUID CANDLES" in html
    assert "ATLAS LEVEL OVERLAYS" in html
    for timeframe in ("1m", "5m", "15m", "1h", "4h"):
        assert f"'{timeframe}'" in html
    assert "CANDLE HISTORY TEMPORARILY UNAVAILABLE" in html
    assert "No positions, journal rows, or health figures are fabricated." in html


def test_perp_candle_endpoint_uses_registered_hyperliquid_adapter(monkeypatch):
    class FakeAdapter:
        async def get_candles(self, symbol, interval="15m", lookback=96):
            assert symbol == "BTC"
            assert interval == "5m"
            assert lookback == 24
            return [
                {
                    "time": 1_700_000_000_000,
                    "open": 100.0,
                    "high": 105.0,
                    "low": 99.0,
                    "close": 103.0,
                    "volume": 1234.0,
                }
            ]

    monkeypatch.setattr(perp_api.registry, "get", lambda name: FakeAdapter() if name == "hyperliquid" else None)
    payload = asyncio.run(perp_api.perp_candles(symbol="BTC", interval="5m", lookback=24))

    assert payload["source"] == "hyperliquid"
    assert payload["symbol"] == "BTC"
    assert payload["interval"] == "5m"
    assert payload["count"] == 1
    assert payload["live_execution"] is False
    assert payload["candles"][0]["close"] == 103.0
