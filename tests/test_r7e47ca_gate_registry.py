import pytest

from app.adapters import hyperliquid_gate_registry as registry
from app.adapters.hyperliquid_request_gate import (
    HyperliquidRequestGate,
    RequestGateRefused,
)


@pytest.fixture(autouse=True)
def reset_registry(monkeypatch):
    monkeypatch.setattr(registry, "_gate", None)


def test_default_refuses():
    with pytest.raises(RequestGateRefused):
        registry.consume_before_attempt("HTTP")


def test_shared_budget(tmp_path):
    gate = HyperliquidRequestGate(
        tmp_path / "shared.sqlite",
        rights_approved=True,
        budget_approved=True,
        max_attempts=2,
    )

    registry.install_gate(gate)

    assert registry.consume_before_attempt("HTTP") == 1
    assert registry.consume_before_attempt("WEBSOCKET_CONNECT") == 0

    with pytest.raises(RequestGateRefused):
        registry.consume_before_attempt("HTTP")


def test_second_install_refused(tmp_path):
    first = HyperliquidRequestGate(
        tmp_path / "first.sqlite",
        rights_approved=True,
        budget_approved=True,
        max_attempts=1,
    )
    second = HyperliquidRequestGate(
        tmp_path / "second.sqlite",
        rights_approved=True,
        budget_approved=True,
        max_attempts=1,
    )

    registry.install_gate(first)

    with pytest.raises(RequestGateRefused):
        registry.install_gate(second)

    assert registry.require_gate() is first


def test_invalid_gate_refused():
    with pytest.raises(RequestGateRefused):
        registry.install_gate(object())
