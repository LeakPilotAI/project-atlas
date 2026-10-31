"""Process-local Hyperliquid gate registry.

Default state is denied. This module does not authorize provider access.
"""

from __future__ import annotations

from threading import RLock

from app.adapters.hyperliquid_request_gate import (
    HyperliquidRequestGate,
    RequestGateRefused,
)


_lock = RLock()
_gate: HyperliquidRequestGate | None = None


def require_gate() -> HyperliquidRequestGate:
    with _lock:
        if _gate is None:
            raise RequestGateRefused(
                "Shared Hyperliquid request gate is not configured"
            )
        return _gate


def install_gate(gate: HyperliquidRequestGate) -> None:
    global _gate

    if type(gate) is not HyperliquidRequestGate:
        raise RequestGateRefused("Invalid shared request gate")

    with _lock:
        if _gate is not None:
            raise RequestGateRefused(
                "Shared request gate already installed"
            )
        _gate = gate


def consume_before_attempt(kind: str) -> int:
    return require_gate().consume_before_attempt(kind)
