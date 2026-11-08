from pathlib import Path


def test_main_runtime_does_not_import_legacy_equity_day_trade_worker():
    text = Path("backend/app/main.py").read_text(encoding="utf-8")
    assert "from app.services.day_trade_assistant import day_trade_assistant" not in text
    assert '("day_trade", day_trade_assistant.start)' not in text
    assert '("day_trade", day_trade_assistant.stop)' not in text


def test_health_contract_maps_day_trade_to_hyperliquid_manual_perps():
    text = Path("backend/app/main.py").read_text(encoding="utf-8")
    assert '"day_trade_running": bool(getattr(perp_manual_service, "running", False))' in text
    assert '"day_trade_domain": "HYPERLIQUID_PERPS"' in text
    assert '"legacy_equity_day_trade_running": False' in text


def test_legacy_equity_research_source_is_preserved_but_not_runtime_owned():
    text = Path("backend/app/services/day_trade_assistant.py").read_text(encoding="utf-8")
    assert "import yfinance as yf" in text
    assert "class DayTradeAssistant" in text
    main_text = Path("backend/app/main.py").read_text(encoding="utf-8")
    assert "day_trade_assistant" not in main_text
