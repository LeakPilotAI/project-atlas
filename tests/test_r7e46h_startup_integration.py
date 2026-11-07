"""R7E46H source-level lifecycle integration contract."""

import ast
import asyncio
from pathlib import Path

from app.services.extended_hours_research import (
    ExtendedHoursResearchService,
    enabled_from_environment,
)

ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT / "backend" / "app" / "main.py"
SERVICE = ROOT / "backend" / "app" / "services" / "extended_hours_research.py"


def test_main_has_one_start_and_one_stop():
    tree = ast.parse(MAIN.read_text(encoding="utf-8"))

    starts = []
    stops = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        func = node.func
        if not isinstance(func.value, ast.Name) or func.value.id != "extended_hours_research_service":
            continue
        if func.attr == "start":
            starts.append(node)
        elif func.attr == "stop":
            stops.append(node)

    assert len(starts) == 1
    assert len(stops) == 1


def test_startup_and_shutdown_order():
    text = MAIN.read_text(encoding="utf-8")

    assert text.index("await start_investment_scanner()") < text.index(
        "await extended_hours_research_service.start()"
    )

    assert text.index('shutdown_report.run("investment", stop_investment_scanner)') < text.index(
        'shutdown_report.run("research",'
    )


def test_feature_is_disabled_by_default(monkeypatch):
    monkeypatch.delenv(
        "ATLAS_EXTENDED_HOURS_RESEARCH_ENABLED",
        raising=False,
    )
    assert enabled_from_environment() is False


def test_invalid_enable_values_fail_closed(monkeypatch):
    for value in ("", "false", "0", "disabled", "unexpected"):
        monkeypatch.setenv(
            "ATLAS_EXTENDED_HOURS_RESEARCH_ENABLED",
            value,
        )
        assert enabled_from_environment() is False


def test_disabled_start_creates_no_task(monkeypatch):
    monkeypatch.delenv(
        "ATLAS_EXTENDED_HOURS_RESEARCH_ENABLED",
        raising=False,
    )

    class ForbiddenCollector:
        async def collect_once(self, *args, **kwargs):
            raise AssertionError("Disabled service fetched quotes")

    service = ExtendedHoursResearchService(
        collector=ForbiddenCollector(),
        universe_loader=lambda: None,
    )

    async def scenario():
        assert await service.start() is False
        assert service._task is None
        await service.stop()

    asyncio.run(scenario())


def test_service_has_no_trading_or_delivery_imports():
    tree = ast.parse(SERVICE.read_text(encoding="utf-8"))

    imported = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module.lower())
        elif isinstance(node, ast.Import):
            imported.extend(alias.name.lower() for alias in node.names)

    forbidden = (
        "order_execution",
        "live_trading",
        "discord_delivery",
        "discord_bot",
        "broker_order",
    )

    assert not any(
        term in module
        for module in imported
        for term in forbidden
    )