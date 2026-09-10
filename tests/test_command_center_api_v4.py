from pathlib import Path

from fastapi.routing import iter_route_contexts

from app.main import app
from app.services.command_center import CommandCenterService


def test_command_center_summary_api_is_mounted_and_read_only():
    routes = list(iter_route_contexts(app.routes))
    paths = {route.path for route in routes}
    assert "/api/command-center/summary" in paths
    methods = next(route.methods for route in routes if route.path == "/api/command-center/summary")
    assert methods == {"GET"}


def test_command_center_source_has_no_legacy_hard_coded_portfolio_posture():
    text = Path("backend/app/services/command_center.py").read_text(encoding="utf-8")
    assert "Target cash ≥40%" not in text
    assert "Max one name ≤15%" not in text
    assert "perp_allowlist" not in text
    assert "NO_ORDER_ACTIONS" not in text  # service renders summary; API owns contract label


def test_command_center_body_uses_domain_labels_and_no_execution_language():
    summary = {
        "perps": {
            "running": True,
            "market_count": 150,
            "prime_count": 1,
            "qualified_count": 2,
            "actionable_count": 2,
            "entered_count": 1,
            "top_setup": {"symbol": "ETH", "side": "SHORT", "tier": "PRIME", "state": "PREPARE"},
        },
        "investments": {
            "asset_count": 5,
            "counts": {"ACCUMULATE": 1, "PREPARE": 1, "WATCH": 2, "STAND_DOWN": 1},
            "top_opportunity": {"symbol": "NVDA", "stance": "ACCUMULATE", "evidence_quality": "HIGH", "thesis": "INTACT"},
        },
    }
    body = CommandCenterService._body(summary)
    assert "HYPERLIQUID_PERPS" in body
    assert "EQUITY_INVESTMENT" in body
    assert "ETH SHORT" in body
    assert "NVDA" in body
    assert "Atlas places no orders" in body
    assert "40%" not in body
    assert "15%" not in body
