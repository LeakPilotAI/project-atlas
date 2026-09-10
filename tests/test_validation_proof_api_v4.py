from fastapi.testclient import TestClient

from app.main import app


def test_validation_proof_api_is_read_only_and_never_live_unlocks():
    with TestClient(app) as client:
        response = client.get("/api/validation/proof")
    assert response.status_code == 200
    body = response.json()
    assert body["domain"] == "VALIDATION_ORCHESTRATION"
    assert body["live_capital_allowed"] is False
    assert body["perps"]["domain"] == "HYPERLIQUID_PERPS"
    assert body["perps"]["live_capital_allowed"] is False
    assert body["investments"]["domain"] == "EQUITY_INVESTMENT"
    assert body["investments"]["live_capital_allowed"] is False


def test_main_mounts_validation_proof_router_without_order_actions():
    paths = {route.path for route in app.routes}
    assert "/api/validation/proof" in paths
    methods = next(route.methods for route in app.routes if route.path == "/api/validation/proof")
    assert methods == {"GET"}
