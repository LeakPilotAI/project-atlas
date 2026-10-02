"""Prediction-market PAPER engine: single-market, pre-event repricing only.

This module is deliberately isolated from Hyperliquid PAPER journals and from any
authenticated Kalshi account/order surface. It models executable fills from public
orderbook depth and persists append-only PAPER evidence.
"""
from __future__ import annotations

import json
import os
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_CEILING
from pathlib import Path
from typing import Any

from app.prediction.policy import (
    MAX_CONCURRENT_PREDICTION_POSITIONS,
    MUST_EXIT_BEFORE_EVENT_START,
    POLICY_VERSION,
    policy_snapshot,
)

DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "prediction"
CANDIDATE_PATH = DATA_DIR / "paper_candidates.jsonl"
JOURNAL_PATH = DATA_DIR / "paper_trades.jsonl"

PAPER_ENGINE_VERSION = "prediction-paper-reprice-v1"
FEE_MODEL_VERSION = "kalshi-general-taker-conservative-v1"

# Current Kalshi general prediction-market taker formula. Some products can have
# different schedules, so Atlas treats this as a conservative general PAPER model,
# never as a promise of the exact live fee for every market.
GENERAL_TAKER_FEE_RATE = Decimal("0.07")

DEFAULT_MAX_SPREAD_DOLLARS = Decimal("0.08")
DEFAULT_MIN_NET_EDGE_DOLLARS = Decimal("0.02")
DEFAULT_MIN_24H_VOLUME = Decimal("20")
DEFAULT_MIN_OPEN_INTEREST = Decimal("20")
DEFAULT_MIN_HISTORY_BARS = 5
DEFAULT_MAX_QUOTE_JUMP_DOLLARS = Decimal("0.20")
DEFAULT_FLAT_BUFFER_MINUTES = 30
DEFAULT_MIN_ENTRY_LEAD_MINUTES = 60


class PredictionPaperError(RuntimeError):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime | None = None) -> str:
    return (value or _now()).astimezone(timezone.utc).isoformat()


def _d(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None


def _fixed(value: Decimal | None) -> str | None:
    return None if value is None else format(value, "f")


def _parse_dt(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except Exception:
        return None


def _ceil_cent(value: Decimal) -> Decimal:
    if value <= 0:
        return Decimal("0.00")
    return value.quantize(Decimal("0.01"), rounding=ROUND_CEILING)


def kalshi_general_taker_fee(contracts: Decimal, price: Decimal) -> Decimal:
    """Conservative general taker fee estimate for one fill level."""
    if contracts <= 0 or price < 0 or price > 1:
        return Decimal("0.00")
    raw = GENERAL_TAKER_FEE_RATE * contracts * price * (Decimal("1") - price)
    return _ceil_cent(raw)


def walk_executable_depth(
    orderbook: dict[str, Any],
    *,
    side: str,
    action: str,
    quantity: Decimal,
) -> dict[str, Any]:
    """Walk real normalized depth and require a complete fill.

    BUY consumes asks cheapest-first. SELL consumes bids best-first.
    Slippage is measured against the first executable level and therefore reflects
    actual book depth rather than a synthetic bps assumption.
    """
    side_key = str(side or "").lower()
    action_key = str(action or "").upper()
    if side_key not in {"yes", "no"}:
        raise PredictionPaperError("side must be YES or NO")
    if action_key not in {"BUY", "SELL"}:
        raise PredictionPaperError("action must be BUY or SELL")
    if quantity <= 0:
        raise PredictionPaperError("quantity must be positive")

    side_book = orderbook.get(side_key) if isinstance(orderbook, dict) else None
    if not isinstance(side_book, dict):
        raise PredictionPaperError("orderbook side unavailable")
    levels = side_book.get("asks" if action_key == "BUY" else "bids")
    if not isinstance(levels, list) or not levels:
        return {
            "fillable": False,
            "requested_quantity": _fixed(quantity),
            "filled_quantity": "0",
            "levels": [],
            "reason": "NO_EXECUTABLE_DEPTH",
        }

    remaining = quantity
    fills: list[dict[str, str]] = []
    notional = Decimal("0")
    total_fee = Decimal("0")
    best_price: Decimal | None = None
    worst_price: Decimal | None = None

    for row in levels:
        if remaining <= 0:
            break
        price = _d(row.get("price_dollars") if isinstance(row, dict) else None)
        available = _d(row.get("quantity_contracts") if isinstance(row, dict) else None)
        if price is None or available is None or available <= 0:
            continue
        if best_price is None:
            best_price = price
        take = min(remaining, available)
        if take <= 0:
            continue
        fee = kalshi_general_taker_fee(take, price)
        fills.append(
            {
                "price_dollars": _fixed(price) or "0",
                "quantity_contracts": _fixed(take) or "0",
                "estimated_taker_fee_dollars": _fixed(fee) or "0",
            }
        )
        notional += take * price
        total_fee += fee
        remaining -= take
        worst_price = price

    filled = quantity - remaining
    if remaining > 0 or filled <= 0:
        return {
            "fillable": False,
            "requested_quantity": _fixed(quantity),
            "filled_quantity": _fixed(filled),
            "levels": fills,
            "reason": "INSUFFICIENT_EXECUTABLE_DEPTH",
        }

    vwap = notional / filled
    if action_key == "BUY":
        slip = vwap - (best_price or vwap)
    else:
        slip = (best_price or vwap) - vwap

    return {
        "fillable": True,
        "requested_quantity": _fixed(quantity),
        "filled_quantity": _fixed(filled),
        "notional_dollars": _fixed(notional),
        "vwap_dollars": _fixed(vwap),
        "best_price_dollars": _fixed(best_price),
        "worst_price_dollars": _fixed(worst_price),
        "depth_slippage_dollars_per_contract": _fixed(max(Decimal("0"), slip)),
        "estimated_taker_fee_dollars": _fixed(total_fee),
        "fee_model": FEE_MODEL_VERSION,
        "levels": fills,
        "reason": None,
    }


def _side_quote_candles(candles: list[dict[str, Any]], side: str) -> list[dict[str, Decimal]]:
    """Return executable bid/ask close/high evidence for YES or NO."""
    result: list[dict[str, Decimal]] = []
    side_u = str(side or "").upper()
    for row in candles:
        if not isinstance(row, dict):
            continue
        yes_bid = row.get("yes_bid") if isinstance(row.get("yes_bid"), dict) else {}
        yes_ask = row.get("yes_ask") if isinstance(row.get("yes_ask"), dict) else {}
        if side_u == "YES":
            bid_close = _d(yes_bid.get("close_dollars"))
            ask_close = _d(yes_ask.get("close_dollars"))
            bid_high = _d(yes_bid.get("high_dollars")) or bid_close
        elif side_u == "NO":
            yes_ask_close = _d(yes_ask.get("close_dollars"))
            yes_bid_close = _d(yes_bid.get("close_dollars"))
            yes_ask_low = _d(yes_ask.get("low_dollars"))
            bid_close = Decimal("1") - yes_ask_close if yes_ask_close is not None else None
            ask_close = Decimal("1") - yes_bid_close if yes_bid_close is not None else None
            bid_high = Decimal("1") - yes_ask_low if yes_ask_low is not None else bid_close
        else:
            raise PredictionPaperError("side must be YES or NO")
        if bid_close is None or ask_close is None:
            continue
        if not (Decimal("0") <= bid_close <= Decimal("1")):
            continue
        if not (Decimal("0") <= ask_close <= Decimal("1")):
            continue
        result.append(
            {
                "bid_close": bid_close,
                "ask_close": ask_close,
                "bid_high": bid_high if bid_high is not None else bid_close,
            }
        )
    return result


@dataclass(frozen=True)
class RepricingConfig:
    max_spread_dollars: Decimal = DEFAULT_MAX_SPREAD_DOLLARS
    min_net_edge_dollars_per_contract: Decimal = DEFAULT_MIN_NET_EDGE_DOLLARS
    min_24h_volume: Decimal = DEFAULT_MIN_24H_VOLUME
    min_open_interest: Decimal = DEFAULT_MIN_OPEN_INTEREST
    min_history_bars: int = DEFAULT_MIN_HISTORY_BARS
    max_quote_jump_dollars: Decimal = DEFAULT_MAX_QUOTE_JUMP_DOLLARS
    flat_buffer_minutes: int = DEFAULT_FLAT_BUFFER_MINUTES
    min_entry_lead_minutes: int = DEFAULT_MIN_ENTRY_LEAD_MINUTES


def evaluate_pre_event_repricing(
    *,
    market: dict[str, Any],
    orderbook: dict[str, Any],
    candles: list[dict[str, Any]],
    side: str,
    quantity: Decimal,
    now: datetime | None = None,
    config: RepricingConfig | None = None,
) -> dict[str, Any]:
    """Evaluate one PAPER candidate using executable prices and recent quote history.

    v1 is deliberately a conservative recent-reclaim heuristic: the projected exit
    is the highest recently observed executable bid, not settlement probability.
    This is a PAPER research score, never a live recommendation.
    """
    cfg = config or RepricingConfig()
    side_u = str(side or "").upper()
    reasons: list[str] = []
    warnings: list[str] = []
    current = now or _now()

    structure = market.get("market_structure") if isinstance(market.get("market_structure"), dict) else {}
    if structure.get("single_market") is not True or structure.get("multivariate") is True:
        reasons.append("NOT_SINGLE_MARKET")

    occurrence = _parse_dt((market.get("timing") or {}).get("occurrence_datetime"))
    if occurrence is None:
        reasons.append("MISSING_OCCURRENCE_DATETIME")
        minutes_to_start = None
        flat_deadline = None
        minutes_to_flat = None
    else:
        minutes_to_start = (occurrence - current).total_seconds() / 60.0
        flat_deadline = occurrence - timedelta(minutes=cfg.flat_buffer_minutes)
        minutes_to_flat = (flat_deadline - current).total_seconds() / 60.0
        if minutes_to_start <= cfg.min_entry_lead_minutes:
            reasons.append("TOO_CLOSE_TO_EVENT_START")
        if MUST_EXIT_BEFORE_EVENT_START and current >= flat_deadline:
            reasons.append("MANDATORY_FLAT_WINDOW")

    fill = walk_executable_depth(orderbook, side=side_u, action="BUY", quantity=quantity)
    if not fill.get("fillable"):
        reasons.append(str(fill.get("reason") or "ENTRY_NOT_FILLABLE"))

    side_book = orderbook.get(side_u.lower()) if isinstance(orderbook, dict) else {}
    bid = _d(side_book.get("best_bid_dollars") if isinstance(side_book, dict) else None)
    ask = _d(side_book.get("best_ask_dollars") if isinstance(side_book, dict) else None)
    spread = _d(side_book.get("spread_dollars") if isinstance(side_book, dict) else None)
    if bid is None or ask is None or spread is None:
        reasons.append("MISSING_EXECUTABLE_QUOTE")
    elif spread > cfg.max_spread_dollars:
        reasons.append("SPREAD_TOO_WIDE")

    activity = market.get("activity") if isinstance(market.get("activity"), dict) else {}
    volume_24h = _d(activity.get("volume_24h_contracts"))
    open_interest = _d(activity.get("open_interest_contracts"))
    if volume_24h is None or volume_24h < cfg.min_24h_volume:
        reasons.append("INSUFFICIENT_24H_VOLUME")
    if open_interest is None or open_interest < cfg.min_open_interest:
        reasons.append("INSUFFICIENT_OPEN_INTEREST")

    history = _side_quote_candles(candles, side_u)
    if len(history) < cfg.min_history_bars:
        reasons.append("INSUFFICIENT_PRE_EVENT_HISTORY")

    jumps: list[Decimal] = []
    for prev, nxt in zip(history, history[1:]):
        jumps.append(abs(nxt["bid_close"] - prev["bid_close"]))
        jumps.append(abs(nxt["ask_close"] - prev["ask_close"]))
    max_jump = max(jumps) if jumps else Decimal("0")
    if max_jump > cfg.max_quote_jump_dollars:
        reasons.append("QUOTE_INSTABILITY")

    entry_vwap = _d(fill.get("vwap_dollars")) if fill.get("fillable") else None
    entry_fee = _d(fill.get("estimated_taker_fee_dollars")) or Decimal("0")
    recent_reclaim_bid = max((bar["bid_high"] for bar in history), default=None)

    projected_exit_fee = Decimal("0")
    projected_gross = None
    projected_net = None
    net_edge_per_contract = None
    if entry_vwap is not None and recent_reclaim_bid is not None:
        projected_exit_fee = kalshi_general_taker_fee(quantity, recent_reclaim_bid)
        projected_gross = (recent_reclaim_bid - entry_vwap) * quantity
        projected_net = projected_gross - entry_fee - projected_exit_fee
        net_edge_per_contract = projected_net / quantity if quantity > 0 else Decimal("0")
        if recent_reclaim_bid <= entry_vwap:
            reasons.append("NO_RECENT_RECLAIM_EDGE")
        elif net_edge_per_contract < cfg.min_net_edge_dollars_per_contract:
            reasons.append("NET_EDGE_TOO_SMALL")
    else:
        reasons.append("NO_REPRICING_TARGET")

    score = 100
    if spread is not None:
        score -= min(45, int((spread / max(cfg.max_spread_dollars, Decimal("0.0001"))) * Decimal("30")))
    if max_jump > Decimal("0"):
        score -= min(35, int((max_jump / max(cfg.max_quote_jump_dollars, Decimal("0.0001"))) * Decimal("20")))
    if net_edge_per_contract is not None and net_edge_per_contract > 0:
        score += min(20, int(net_edge_per_contract * Decimal("200")))
    score = max(0, min(100, score))
    if reasons:
        score = min(score, 49)

    return {
        "engine_version": PAPER_ENGINE_VERSION,
        "policy_version": POLICY_VERSION,
        "strategy": "PRE_EVENT_RECENT_RECLAIM_V1",
        "mode": "PAPER_RESEARCH_ONLY",
        "eligible": not reasons,
        "score": score,
        "ticker": market.get("ticker"),
        "side": side_u,
        "quantity_contracts": _fixed(quantity),
        "occurrence_datetime": _iso(occurrence) if occurrence else None,
        "flat_deadline": _iso(flat_deadline) if flat_deadline else None,
        "minutes_to_start": round(minutes_to_start, 2) if minutes_to_start is not None else None,
        "minutes_to_flat": round(minutes_to_flat, 2) if minutes_to_flat is not None else None,
        "entry_fill": fill,
        "current_quote": {
            "best_bid_dollars": _fixed(bid),
            "best_ask_dollars": _fixed(ask),
            "spread_dollars": _fixed(spread),
        },
        "history": {
            "usable_bars": len(history),
            "recent_reclaim_bid_dollars": _fixed(recent_reclaim_bid),
            "max_quote_jump_dollars": _fixed(max_jump),
        },
        "activity": {
            "volume_24h_contracts": _fixed(volume_24h),
            "open_interest_contracts": _fixed(open_interest),
        },
        "projected": {
            "gross_repricing_pnl_dollars": _fixed(projected_gross),
            "entry_fee_dollars": _fixed(entry_fee),
            "exit_fee_dollars": _fixed(projected_exit_fee),
            "net_repricing_pnl_dollars": _fixed(projected_net),
            "net_edge_dollars_per_contract": _fixed(net_edge_per_contract),
            "fee_model": FEE_MODEL_VERSION,
        },
        "rejection_reasons": reasons,
        "warnings": warnings,
        "config": {
            "max_spread_dollars": _fixed(cfg.max_spread_dollars),
            "min_net_edge_dollars_per_contract": _fixed(cfg.min_net_edge_dollars_per_contract),
            "min_24h_volume": _fixed(cfg.min_24h_volume),
            "min_open_interest": _fixed(cfg.min_open_interest),
            "min_history_bars": cfg.min_history_bars,
            "max_quote_jump_dollars": _fixed(cfg.max_quote_jump_dollars),
            "flat_buffer_minutes": cfg.flat_buffer_minutes,
            "min_entry_lead_minutes": cfg.min_entry_lead_minutes,
        },
        "live_capital_allowed": False,
        "automatic_real_money_execution": False,
    }


class PredictionPaperJournal:
    """Append-only isolated prediction PAPER evidence store."""

    _lock = threading.RLock()

    def __init__(
        self,
        *,
        journal_path: Path | None = None,
        candidate_path: Path | None = None,
    ) -> None:
        self.journal_path = journal_path or JOURNAL_PATH
        self.candidate_path = candidate_path or CANDIDATE_PATH
        self.journal_path.parent.mkdir(parents=True, exist_ok=True)
        self.candidate_path.parent.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _append(path: Path, row: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(row, default=str, separators=(",", ":")) + "\n"
        with PredictionPaperJournal._lock:
            with path.open("a", encoding="utf-8") as handle:
                handle.write(line)
                handle.flush()
                try:
                    os.fsync(handle.fileno())
                except OSError:
                    pass

    @staticmethod
    def _rows(path: Path) -> list[dict[str, Any]]:
        if not path.exists():
            return []
        rows: list[dict[str, Any]] = []
        try:
            with path.open("r", encoding="utf-8") as handle:
                for raw in handle:
                    raw = raw.strip()
                    if not raw:
                        continue
                    try:
                        row = json.loads(raw)
                    except Exception:
                        continue
                    if isinstance(row, dict):
                        rows.append(row)
        except OSError:
            return []
        return rows

    def open_trade(self) -> dict[str, Any] | None:
        opens: dict[str, dict[str, Any]] = {}
        closed: set[str] = set()
        for row in self._rows(self.journal_path):
            trade_id = str(row.get("trade_id") or "")
            if not trade_id:
                continue
            if row.get("event") == "open":
                opens[trade_id] = row
            elif row.get("event") == "close":
                closed.add(trade_id)
        active = [row for tid, row in opens.items() if tid not in closed]
        active.sort(key=lambda row: str(row.get("entry_timestamp") or ""))
        return active[-1] if active else None

    def log_candidate(self, evaluation: dict[str, Any]) -> dict[str, Any]:
        row = {
            "event": "candidate",
            "candidate_id": str(uuid.uuid4())[:12],
            "timestamp": _iso(),
            **evaluation,
        }
        self._append(self.candidate_path, row)
        return row

    def open_from_evaluation(self, evaluation: dict[str, Any]) -> dict[str, Any]:
        if not evaluation.get("eligible"):
            raise PredictionPaperError("candidate is not eligible for PAPER entry")
        if MAX_CONCURRENT_PREDICTION_POSITIONS != 1:
            raise PredictionPaperError("prediction max-position policy changed unexpectedly")
        if self.open_trade() is not None:
            raise PredictionPaperError("one prediction PAPER position is already open")
        fill = evaluation.get("entry_fill") if isinstance(evaluation.get("entry_fill"), dict) else {}
        if not fill.get("fillable"):
            raise PredictionPaperError("entry depth is not fillable")
        trade_id = str(uuid.uuid4())[:12]
        row = {
            "event": "open",
            "trade_id": trade_id,
            "trade_type": "PREDICTION_PAPER",
            "entry_timestamp": _iso(),
            "ticker": evaluation.get("ticker"),
            "side": evaluation.get("side"),
            "quantity_contracts": evaluation.get("quantity_contracts"),
            "actual_entry_price": fill.get("vwap_dollars"),
            "entry_notional_dollars": fill.get("notional_dollars"),
            "entry_fee_dollars": fill.get("estimated_taker_fee_dollars"),
            "entry_depth_slippage_dollars_per_contract": fill.get("depth_slippage_dollars_per_contract"),
            "entry_fill_levels": fill.get("levels") or [],
            "occurrence_datetime": evaluation.get("occurrence_datetime"),
            "flat_deadline": evaluation.get("flat_deadline"),
            "strategy": evaluation.get("strategy"),
            "signal_score": evaluation.get("score"),
            "candidate_engine_version": evaluation.get("engine_version"),
            "policy_version": POLICY_VERSION,
            "fee_model": FEE_MODEL_VERSION,
            "live_capital_allowed": False,
            "automatic_real_money_execution": False,
            "status": "open",
        }
        self._append(self.journal_path, row)
        return row

    def close_from_orderbook(
        self,
        *,
        orderbook: dict[str, Any],
        exit_reason: str,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        opened = self.open_trade()
        if not opened:
            raise PredictionPaperError("no open prediction PAPER position")
        quantity = _d(opened.get("quantity_contracts"))
        if quantity is None or quantity <= 0:
            raise PredictionPaperError("open PAPER quantity is invalid")
        fill = walk_executable_depth(
            orderbook,
            side=str(opened.get("side") or ""),
            action="SELL",
            quantity=quantity,
        )
        if not fill.get("fillable"):
            raise PredictionPaperError(str(fill.get("reason") or "exit depth is not fillable"))

        entry = _d(opened.get("actual_entry_price")) or Decimal("0")
        exit_vwap = _d(fill.get("vwap_dollars")) or Decimal("0")
        entry_fee = _d(opened.get("entry_fee_dollars")) or Decimal("0")
        exit_fee = _d(fill.get("estimated_taker_fee_dollars")) or Decimal("0")
        gross = (exit_vwap - entry) * quantity
        net = gross - entry_fee - exit_fee
        entry_cash = entry * quantity + entry_fee
        roi = (net / entry_cash) if entry_cash > 0 else Decimal("0")

        current = now or _now()
        occurrence = _parse_dt(opened.get("occurrence_datetime"))
        flat_deadline = _parse_dt(opened.get("flat_deadline"))
        late = bool(flat_deadline and current >= flat_deadline)
        if late and MUST_EXIT_BEFORE_EVENT_START:
            exit_reason = "MANDATORY_FLAT_LATE_EXIT"

        row = {
            **opened,
            "event": "close",
            "status": "closed",
            "exit_timestamp": _iso(current),
            "actual_exit_price": _fixed(exit_vwap),
            "exit_notional_dollars": fill.get("notional_dollars"),
            "exit_fee_dollars": _fixed(exit_fee),
            "exit_depth_slippage_dollars_per_contract": fill.get("depth_slippage_dollars_per_contract"),
            "exit_fill_levels": fill.get("levels") or [],
            "exit_reason": str(exit_reason or "PAPER_EXIT"),
            "gross_pnl_dollars": _fixed(gross),
            "net_pnl_dollars": _fixed(net),
            "net_roi": _fixed(roi),
            "win": net > 0,
            "scratch": net == 0,
            "minutes_to_start_at_exit": (
                round((occurrence - current).total_seconds() / 60.0, 2)
                if occurrence is not None
                else None
            ),
            "violated_flat_deadline": late,
            "counts_for_live": False,
            "live_capital_allowed": False,
            "automatic_real_money_execution": False,
        }
        self._append(self.journal_path, row)
        return row

    def snapshot(self, limit: int = 100) -> dict[str, Any]:
        rows = self._rows(self.journal_path)
        closes = [row for row in rows if row.get("event") == "close"]
        wins = [row for row in closes if row.get("win") is True]
        net_values = [_d(row.get("net_pnl_dollars")) or Decimal("0") for row in closes]
        return {
            "domain": "PREDICTION_PAPER",
            "execution": "PAPER_ONLY",
            "live_capital_allowed": False,
            "automatic_real_money_execution": False,
            "policy": policy_snapshot(),
            "engine_version": PAPER_ENGINE_VERSION,
            "fee_model": FEE_MODEL_VERSION,
            "open_trade": self.open_trade(),
            "summary": {
                "open_positions": 1 if self.open_trade() else 0,
                "closed_trades": len(closes),
                "wins": len(wins),
                "losses_or_scratches": len(closes) - len(wins),
                "net_pnl_dollars": _fixed(sum(net_values, Decimal("0"))),
                "win_rate": round(len(wins) / len(closes), 4) if closes else None,
            },
            "events": rows[-max(1, min(int(limit), 1000)):],
        }


prediction_paper_journal = PredictionPaperJournal()
