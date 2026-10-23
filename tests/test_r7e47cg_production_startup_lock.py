import ast
from pathlib import Path

import pytest

from app.core.production_startup_lock import (
    ProductionStartupRefused,
    require_startup_authorization,
)


MAIN = Path(__file__).resolve().parents[1] / "backend/app/main.py"


def test_production_startup_always_refuses():
    with pytest.raises(ProductionStartupRefused):
        require_startup_authorization()


def test_lock_precedes_provider_gate_and_redis():
    tree = ast.parse(MAIN.read_text(encoding="utf-8-sig"))

    functions = [
        node for node in tree.body
        if isinstance(node, ast.AsyncFunctionDef)
        and node.name == "lifespan"
    ]

    assert len(functions) == 1

    calls = [
        (node.lineno, ast.unparse(node.func))
        for node in ast.walk(functions[0])
        if isinstance(node, ast.Call)
    ]

    def first_line(name):
        matches = [
            line for line, call in calls
            if call == name
        ]
        assert matches, f"Missing call: {name}"
        return min(matches)

    assert (
        first_line("require_startup_authorization")
        < first_line("require_gate")
        < first_line("get_redis_client")
    )


def test_lock_has_no_unlock_function():
    from app.core import production_startup_lock

    assert not hasattr(production_startup_lock, "authorize")
    assert not hasattr(production_startup_lock, "unlock")
    assert not hasattr(production_startup_lock, "enable")
