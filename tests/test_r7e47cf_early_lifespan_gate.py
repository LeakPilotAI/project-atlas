import ast
from pathlib import Path

import pytest

from app.adapters import hyperliquid_gate_registry as registry
from app.adapters.hyperliquid_request_gate import RequestGateRefused


MAIN = Path(__file__).resolve().parents[1] / "backend/app/main.py"


def test_gate_precedes_startup_io():
    source = MAIN.read_text(encoding="utf-8-sig")
    tree = ast.parse(source)

    lifespan = [
        node for node in tree.body
        if isinstance(node, ast.AsyncFunctionDef)
        and node.name == "lifespan"
    ]

    assert len(lifespan) == 1

    function = lifespan[0]

    calls = [
        (node.lineno, ast.unparse(node.func))
        for node in ast.walk(function)
        if isinstance(node, ast.Call)
    ]

    gate_lines = [
        line for line, name in calls
        if name == "require_gate"
    ]

    redis_lines = [
        line for line, name in calls
        if name == "get_redis_client"
    ]

    database_lines = [
        line for line, name in calls
        if name == "engine.begin"
    ]

    assert len(gate_lines) >= 2
    assert len(redis_lines) == 1
    assert len(database_lines) == 1

    assert min(gate_lines) < redis_lines[0]
    assert min(gate_lines) < database_lines[0]


def test_default_admission_refuses(monkeypatch):
    monkeypatch.setattr(registry, "_gate", None)

    with pytest.raises(RequestGateRefused):
        registry.require_gate()
