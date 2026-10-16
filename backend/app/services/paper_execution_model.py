"""Conservative PAPER execution-cost assumptions.

Simulation-only. These assumptions intentionally lean pessimistic and do not enable
live trading.
"""
from __future__ import annotations

from typing import Any

PAPER_EXECUTION_MODEL_VERSION = "paper-exec-v2-conservative-gap-target"
DEFAULT_FEE_BPS_PER_SIDE = 2.0
DEFAULT_SLIPPAGE_BPS_PER_SIDE = 2.0
DEFAULT_TOUCH_BUFFER_BPS = 1.0


def execution_assumptions() -> dict[str, Any]:
    return {
        "version": PAPER_EXECUTION_MODEL_VERSION,
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


def conservative_stop_exit(*, side: str, mark: float, stop_price: float, slippage_bps: float = DEFAULT_SLIPPAGE_BPS_PER_SIDE) -> float:
    """Model a stop exit at the worse of observed mark or stop plus adverse slippage."""
    mark_f=float(mark); stop_f=float(stop_price)
    side_u=str(side or "").upper()
    if side_u=="LONG":
        base=min(mark_f,stop_f)
        return base*(1.0-float(slippage_bps)/10000.0)
    if side_u=="SHORT":
        base=max(mark_f,stop_f)
        return base*(1.0+float(slippage_bps)/10000.0)
    return mark_f


def conservative_target_exit(*, side: str, mark: float, target_price: float, slippage_bps: float = DEFAULT_SLIPPAGE_BPS_PER_SIDE) -> float:
    """Cap favorable target exits at target and apply adverse slippage."""
    mark_f=float(mark); target_f=float(target_price)
    side_u=str(side or "").upper()
    if side_u=="LONG":
        base=min(mark_f,target_f)
        return base*(1.0-float(slippage_bps)/10000.0)
    if side_u=="SHORT":
        base=max(mark_f,target_f)
        return base*(1.0+float(slippage_bps)/10000.0)
    return mark_f
