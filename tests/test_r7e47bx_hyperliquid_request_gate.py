from concurrent.futures import ThreadPoolExecutor

import pytest

from app.adapters.hyperliquid_request_gate import (
    HyperliquidRequestGate,
    RequestGateRefused,
)


def test_default_refuses(tmp_path):
    with pytest.raises(RequestGateRefused):
        HyperliquidRequestGate(tmp_path / "budget.sqlite")


def test_shared_budget_across_instances(tmp_path):
    path = tmp_path / "budget.sqlite"

    a = HyperliquidRequestGate(
        path,
        rights_approved=True,
        budget_approved=True,
        max_attempts=2,
    )
    b = HyperliquidRequestGate(
        path,
        rights_approved=True,
        budget_approved=True,
        max_attempts=2,
    )

    assert a.consume_before_attempt("HTTP") == 1
    assert b.consume_before_attempt("WEBSOCKET_CONNECT") == 0

    with pytest.raises(RequestGateRefused):
        a.consume_before_attempt("HTTP")


def test_budget_mismatch_refuses(tmp_path):
    path = tmp_path / "budget.sqlite"

    HyperliquidRequestGate(
        path,
        rights_approved=True,
        budget_approved=True,
        max_attempts=2,
    )

    with pytest.raises(RequestGateRefused):
        HyperliquidRequestGate(
            path,
            rights_approved=True,
            budget_approved=True,
            max_attempts=3,
        )


def test_unsupported_operation_does_not_consume(tmp_path):
    gate = HyperliquidRequestGate(
        tmp_path / "budget.sqlite",
        rights_approved=True,
        budget_approved=True,
        max_attempts=1,
    )

    with pytest.raises(RequestGateRefused):
        gate.consume_before_attempt("TRADE")

    assert gate.remaining() == 1


def test_concurrent_budget_enforcement(tmp_path):
    path = tmp_path / "budget.sqlite"
    gate = HyperliquidRequestGate(
        path,
        rights_approved=True,
        budget_approved=True,
        max_attempts=3,
    )

    def attempt(_):
        try:
            gate.consume_before_attempt("HTTP")
            return True
        except RequestGateRefused:
            return False

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(attempt, range(12)))

    assert sum(results) == 3
    assert gate.remaining() == 0
