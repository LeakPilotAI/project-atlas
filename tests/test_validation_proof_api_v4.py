import asyncio

from app.api.validation_proof import validation_proof
from app.main import app


def _walk_routes(routes):
    for route in routes:
        if hasattr(route, "path"):
            yield route
        nested = getattr(route, "routes", None)
        if nested:
            yield from _walk_routes(nested)


def test_validation_proof_api_is_read_only_and_never_live_unlocks():
    body = asyncio.run(validation_proof())
    assert body["domain"] == "VALIDATION_ORCHESTRATION"
    assert body["live_capital_allowed"] is False
    assert body["perps"]["domain"] == "HYPERLIQUID_PERPS"
    assert body["perps"]["live_capital_allowed"] is False
    assert body["investments"]["domain"] == "EQUITY_INVESTMENT"
    assert body["investments"]["live_capital_allowed"] is False


def test_main_mounts_validation_proof_router_without_order_actions():
    routes = list(_walk_routes(app.routes))
    paths = {route.path for route in routes}
    assert "/api/validation/proof" in paths
    methods = next(route.methods for route in routes if route.path == "/api/validation/proof")
    assert methods == {"GET"}
