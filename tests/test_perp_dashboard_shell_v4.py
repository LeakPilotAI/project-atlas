from pathlib import Path


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
    assert 'DASHBOARD_HTML = STATIC_DIR / "dashboard_shell.html"' in main
    assert 'LEGACY_DASHBOARD_HTML = STATIC_DIR / "dashboard.html"' in main
    assert '@app.get("/dashboard/legacy")' in main


def test_perp_shell_has_no_equity_data_endpoints():
    html = _read("backend/app/static/dashboard_shell.html")
    assert "yahoo" not in html.lower()
    assert "/api/live" not in html
    assert "equity_majors" not in html
