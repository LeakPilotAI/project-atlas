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
    assert "fills automatically at active L1/L2/L3" in html
    assert '<div class="label">Manual fills</div>' not in html
