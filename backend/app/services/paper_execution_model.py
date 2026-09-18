"""Conservative PAPER execution-cost assumptions.

Simulation-only. These assumptions intentionally lean pessimistic and do not enable
live trading.
"""
from __future__ import annotations

from typing import Any

DEFAULT_FEE_BPS_PER_SIDE = 2.0
DEFAULT_SLIPPAGE_BPS_PER_SIDE = 2.0
DEFAULT_TOUCH_BUFFER_BPS = 1.0


def execution_assumptions() -> dict[str, Any]:
    return {
        "fee_bps_per_side": DEFAULT_FEE_BPS_PER_SIDE,
        "slippage_bps_per_side": DEFAULT_SLIPPAGE_BPS_PER_SIDE,
        "touch_buffer_bps": DEFAULT_TOUCH_BUFFER_BPS,
        "fill_model": "LIMIT_TOUCH_PLUS_BUFFER",
        "conservative": True,
        "execution": "PAPER_ONLY",
        "live_capital_allowed": False,
        "automatic_real_money_execution": False,
    }


def touched_with_buffer(*, side: str, mark: float, limit_price: float, buffer_bps: float = DEFAULT_TOUCH_BUFFER_BPS) -> bool:
    if min(float(mark), float(limit_price)) <= 0:
        return False
    buffer = float(limit_price) * float(buffer_bps) / 10000.0
    side_u = str(side or "").upper()
    if side_u == "LONG":
        return float(mark) <= float(limit_price) - buffer
    if side_u == "SHORT":
        return float(mark) >= float(limit_price) + buffer
    return False
