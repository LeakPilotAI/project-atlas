"""Evidence-adaptive PAPER exit policy for manual Hyperliquid setup mirrors.

This module never places or modifies real exchange orders. It produces deterministic
PAPER-only working stop/target guidance from information Atlas already observes:
trade-path MFE/MAE, hold time, the fresh 5m setup structure, score, 24h volume,
open interest, volatility, momentum and trend.

The policy is intentionally versioned and opt-in per trade so historical/static
PAPER cohorts remain comparable. It cannot guarantee profitable exits or prevent
gaps through a protective stop.
"""
from __future__ import annotations

from datetime import datetime, timezone
from math import log10
from typing import Any

ADAPTIVE_EXIT_POLICY_VERSION = "paper-exit-v1-evidence-protect"
ADAPTIVE_EXECUTION_COHORT_VERSION = "paper-exec-v2-conservative-gap-target+adaptive-exit-v1"
ADAPTIVE_EVIDENCE_INTERVAL = "5m"
ADAPTIVE_STRUCTURE_LOOKBACK_BARS = 48
ADAPTIVE_EVIDENCE_WINDOW = "48x5m + trade path + 24h liquidity"


def _num(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(float(lo), min(float(hi), float(value)))


def _age_seconds(trade: dict[str, Any], now: datetime | None = None) -> float:
    raw = trade.get("entry_timestamp")
    if not raw:
        return 0.0
    try:
        dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        current = now or datetime.now(timezone.utc)
        return max(0.0, (current - dt.astimezone(timezone.utc)).total_seconds())
    except Exception:
        return 0.0


def _trade_r(*, side: str, mark: float, entry: float, risk: float) -> float:
    if risk <= 0:
        return 0.0
    return (mark - entry) / risk if side == "LONG" else (entry - mark) / risk


def _price_for_r(*, side: str, entry: float, risk: float, r_value: float) -> float:
    return entry + risk * r_value if side == "LONG" else entry - risk * r_value


def _cost_r(trade: dict[str, Any], *, entry: float, risk: float) -> float:
    if risk <= 0:
        return 0.0
    fees = max(0.0, _num(trade.get("fees_bps"))) / 10000.0
    slip = max(0.0, _num(trade.get("slippage_bps"))) / 10000.0
    return 2.0 * (fees + slip) * abs(entry) / risk


def _liquidity_points(setup: dict[str, Any] | None) -> float:
    if not setup:
        return 0.0
    volume = max(1.0, _num(setup.get("volume_24h"), 1.0))
    oi = max(1.0, _num(setup.get("open_interest"), 1.0))
    volume_points = _clamp((log10(volume) - 5.0) * 7.0, 0.0, 22.0)
    oi_points = _clamp((log10(oi) - 4.5) * 7.0, 0.0, 18.0)
    return volume_points + oi_points


def _structure_evidence(side: str, setup: dict[str, Any] | None) -> dict[str, Any]:
    if not setup or bool(setup.get("discovery_stale")):
        return {
            "fresh": False,
            "aligned": False,
            "fading": True,
            "score": 0.0,
            "momentum_pct": None,
            "trend_pct": None,
            "volatility_pct": None,
            "liquidity_points": 0.0,
            "strength": 0.0,
        }

    momentum = _num(setup.get("momentum_pct"))
    trend = _num(setup.get("trend_pct"))
    volatility = abs(_num(setup.get("volatility_pct")))
    score = _num(setup.get("score"))
    direction = 1.0 if side == "LONG" else -1.0
    directional_momentum = direction * momentum
    directional_trend = direction * trend
    liquidity = _liquidity_points(setup)

    aligned = directional_momentum >= 0.10 and directional_trend >= 0.20
    reverse = directional_momentum <= -0.05 or directional_trend <= -0.10
    volatility_ok = 0.15 <= volatility <= 2.5
    strength = 0.0
    strength += 0.30 if directional_momentum >= 0.10 else 0.0
    strength += 0.30 if directional_trend >= 0.20 else 0.0
    strength += 0.15 if score >= 72.0 else 0.0
    strength += 0.15 if liquidity >= 24.0 else 0.0
    strength += 0.10 if volatility_ok else 0.0

    return {
        "fresh": True,
        "aligned": aligned,
        "fading": reverse or strength < 0.35,
        "score": round(score, 4),
        "momentum_pct": round(momentum, 6),
        "trend_pct": round(trend, 6),
        "volatility_pct": round(volatility, 6),
        "liquidity_points": round(liquidity, 4),
        "strength": round(strength, 4),
    }


def policy_metadata() -> dict[str, Any]:
    return {
        "version": ADAPTIVE_EXIT_POLICY_VERSION,
        "execution_cohort_version": ADAPTIVE_EXECUTION_COHORT_VERSION,
        "mode": "PAPER_ONLY",
        "evidence_interval": ADAPTIVE_EVIDENCE_INTERVAL,
        "structure_lookback_bars": ADAPTIVE_STRUCTURE_LOOKBACK_BARS,
        "evidence_window": ADAPTIVE_EVIDENCE_WINDOW,
        "protect_after_mfe_r": 0.35,
        "time_protect_after_sec": 1800,
        "time_protect_min_mfe_r": 0.25,
        "tp_extension": "TP2 only with fresh aligned 5m structure and sufficient evidence strength",
        "live_capital_allowed": False,
        "automatic_real_money_execution": False,
        "guaranteed_no_loss": False,
    }


def evaluate_adaptive_exit(
    trade: dict[str, Any],
    setup: dict[str, Any] | None,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Return the PAPER working stop/target for one open trade.

    Existing trades without this policy version stay on their original static exit
    contract. New opted-in trades can tighten risk or extend TP, but the stop is
    never loosened away from protection.
    """
    features = trade.get("features") if isinstance(trade.get("features"), dict) else {}
    enabled = str(features.get("adaptive_exit_policy_version") or "") == ADAPTIVE_EXIT_POLICY_VERSION

    side = str(trade.get("side") or "").upper()
    entry = _num(trade.get("actual_entry_price"))
    risk = _num(trade.get("risk_price") or abs(entry - _num(trade.get("stop_price"))))
    mark = _num(trade.get("mark"), entry)
    initial_stop = _num(trade.get("stop_price"))
    current_stop = _num(trade.get("working_stop"), initial_stop)
    tp1 = _num(trade.get("tp1_price"))
    tp2 = _num(trade.get("tp2_price"), tp1)
    current_target = _num(trade.get("working_target"), tp1)

    if (
        not enabled
        or side not in {"LONG", "SHORT"}
        or min(entry, risk, initial_stop, tp1) <= 0
    ):
        return {
            "eligible": False,
            "policy_version": str(features.get("adaptive_exit_policy_version") or "STATIC"),
            "stage": "STATIC",
            "working_stop": current_stop or initial_stop,
            "working_target": current_target or tp1,
            "reason": "Existing/static PAPER exit contract retained.",
            "evidence": {},
        }

    mfe_r = max(0.0, _num(trade.get("mfe_r")))
    current_r = _trade_r(side=side, mark=mark, entry=entry, risk=risk)
    age_sec = _age_seconds(trade, now=now)
    evidence = _structure_evidence(side, setup)
    cost_r = _cost_r(trade, entry=entry, risk=risk)
    protect_floor_r = max(0.10, cost_r + 0.05)

    lock_r: float | None = None
    stage = "WARMUP"
    reasons: list[str] = []

    # Path evidence is primary. A sufficiently favorable excursion arms protection
    # immediately; a smaller favorable excursion can arm after six 5m bars.
    if mfe_r >= 0.35:
        lock_r = protect_floor_r
        stage = "PROTECT"
        reasons.append("MFE >= 0.35R")
    elif age_sec >= 1800 and mfe_r >= 0.25:
        lock_r = protect_floor_r
        stage = "TIME_PROTECT"
        reasons.append("30m+ hold with MFE >= 0.25R")

    if mfe_r >= 1.0:
        lock_r = max(lock_r or protect_floor_r, 0.35, mfe_r - 0.75)
        stage = "LOCK_1R"
        reasons.append("MFE >= 1R")
    if mfe_r >= 1.5:
        lock_r = max(lock_r or protect_floor_r, 0.75, mfe_r - 0.60)
        stage = "TRAIL_1_5R"
        reasons.append("MFE >= 1.5R")
    if mfe_r >= 2.0:
        lock_r = max(lock_r or protect_floor_r, 1.20, mfe_r - 0.50)
        stage = "TRAIL_2R"
        reasons.append("MFE >= 2R")

    if lock_r is not None and evidence.get("fading") and mfe_r >= 0.50:
        lock_r = max(lock_r, mfe_r - 0.35)
        stage = "FADE_PROTECT"
        reasons.append("fresh evidence weakened/reversed")

    proposed_stop = current_stop or initial_stop
    if lock_r is not None:
        candidate = _price_for_r(side=side, entry=entry, risk=risk, r_value=lock_r)
        if side == "LONG":
            proposed_stop = max(proposed_stop, candidate)
        else:
            proposed_stop = min(proposed_stop, candidate)

    strong_follow_through = (
        bool(evidence.get("fresh"))
        and bool(evidence.get("aligned"))
        and float(evidence.get("strength") or 0.0) >= 0.70
        and not bool(evidence.get("fading"))
    )
    proposed_target = tp2 if strong_follow_through and mfe_r >= 0.35 and tp2 > 0 else tp1
    if proposed_target == tp2 and tp2 != tp1:
        reasons.append("TP extended to TP2 on strong fresh structure/liquidity")
    elif current_target == tp2 and proposed_target == tp1:
        reasons.append("TP returned to TP1 after evidence weakened")

    evidence_out = {
        **evidence,
        "mfe_r": round(mfe_r, 4),
        "current_r": round(current_r, 4),
        "mae_r": round(max(0.0, _num(trade.get("mae_r"))), 4),
        "hold_sec": int(age_sec),
        "round_trip_cost_r_estimate": round(cost_r, 4),
        "protect_floor_r": round(protect_floor_r, 4),
        "interval": ADAPTIVE_EVIDENCE_INTERVAL,
        "lookback_bars": ADAPTIVE_STRUCTURE_LOOKBACK_BARS,
    }

    return {
        "eligible": True,
        "policy_version": ADAPTIVE_EXIT_POLICY_VERSION,
        "stage": stage,
        "working_stop": float(proposed_stop),
        "working_target": float(proposed_target),
        "lock_r": None if lock_r is None else round(lock_r, 4),
        "strong_follow_through": strong_follow_through,
        "reason": "; ".join(reasons) if reasons else "Waiting for sufficient favorable path evidence.",
        "evidence": evidence_out,
        "guaranteed_no_loss": False,
    }
