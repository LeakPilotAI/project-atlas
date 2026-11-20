import ast
from pathlib import Path

import pytest

from app.adapters import hyperliquid_gate_registry as gate_registry
from app.adapters.hyperliquid_request_gate import RequestGateRefused


MAIN = Path(__file__).resolve().parents[1] / "backend/app/main.py"


def test_startup_requires_gate_before_adapter_creation():
    source = MAIN.read_text(encoding="utf-8-sig")
    tree = ast.parse(source)

    matches = []

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue

        if node.name != "_boot_services":
            continue

        calls = [
            (child.lineno, ast.unparse(child.func))
            for child in ast.walk(node)
            if isinstance(child, ast.Call)
        ]

        gate_lines = [
            line for line, name in calls
            if name == "require_gate"
        ]

        adapter_lines = [
            line for line, name in calls
            if name == "HyperliquidAdapter"
        ]

        assert len(gate_lines) == 1
        assert len(adapter_lines) == 1
        assert gate_lines[0] < adapter_lines[0]
        matches.append(node)

    assert len(matches) == 1


def test_default_gate_refuses(monkeypatch):
    monkeypatch.setattr(gate_registry, "_gate", None)

    with pytest.raises(RequestGateRefused):
        gate_registry.require_gate()
