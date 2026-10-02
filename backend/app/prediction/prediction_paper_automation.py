"""Bounded Prediction PAPER scanner and mandatory auto-flat safety worker.

PAPER-only: public single-market discovery/evaluation plus mandatory PAPER exit
enforcement. This module has no authenticated provider, account, or live-order surface.
"""
from __future__ import annotations

import asyncio
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from app.prediction.kalshi_public import PredictionProviderError, kalshi_public
from app.prediction.paper_engine import (
    FEE_MODEL_VERSION,
    PAPER_ENGINE_VERSION,
    PredictionPaperError,
    RepricingConfig,
    _d,
    _fixed,
    _iso,
    _parse_dt,
    evaluate_pre_event_repricing,
    prediction_paper_journal,
)
from app.prediction.policy import POLICY_VERSION, policy_snapshot

AUTOMATION_VERSION = "prediction-paper-automation-v1"
DEFAULT_SCAN_INTERVAL_SECONDS = 60.0
DEFAULT_FLAT_INTERVAL_SECONDS = 5.0
DEFAULT_FLAT_LEAD_SECONDS = 5.0
DEFAULT_DISCOVERY_LIMIT = 40
DEFAULT_MAX_CONCURRENCY = 4
DEFAULT_ORDERBOOK_DEPTH = 20
DEFAULT_HISTORY_MINUTES = 180
DEFAULT_QUANTITY = Decimal("10")


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class PredictionAutomationConfig:
    scan_interval_seconds: float = DEFAULT_SCAN_INTERVAL_SECONDS
    flat_interval_seconds: float = DEFAULT_FLAT_INTERVAL_SECONDS
    flat_lead_seconds: float = DEFAULT_FLAT_LEAD_SECONDS
    discovery_limit: int = DEFAULT_DISCOVERY_LIMIT
    max_concurrency: int = DEFAULT_MAX_CONCURRENCY
    orderbook_depth: int = DEFAULT_ORDERBOOK_DEPTH
    history_minutes: int = DEFAULT_HISTORY_MINUTES
    quantity: Decimal = DEFAULT_QUANTITY


class PredictionPaperAutomation:
    """Own bounded candidate scanning and mandatory PAPER auto-flat."""

    def __init__(self, *, config: PredictionAutomationConfig | None = None) -> None:
        self.config = config or PredictionAutomationConfig()
        self.running = False
        self._scanner_task: asyncio.Task | None = None
        self._flat_task: asyncio.Task | None = None
        self._scan_lock: asyncio.Lock | None = None
        self._flat_lock: asyncio.Lock | None = None
        self._state_lock = threading.RLock()
        self._last_scan = self._empty_scan_state()
        self._last_successful_scan: dict[str, Any] | None = None
        self._last_flat = self._empty_flat_state()
        self._flat_blocked = False

    @staticmethod
    def _empty_scan_state() -> dict[str, Any]:
        return {
            "cycle_id": None, "running": False, "started_at": None, "finished_at": None,
            "markets_discovered": 0, "markets_prefilter_rejected": 0,
            "markets_fully_evaluated": 0, "yes_evaluations": 0, "no_evaluations": 0,
            "eligible_count": 0, "rejected_count": 0, "error_count": 0,
            "timeout_count": 0, "last_error": None, "top_eligible": [],
        }

    @staticmethod
    def _empty_flat_state() -> dict[str, Any]:
        return {
            "last_check_at": None, "last_trade_id": None, "last_action": "IDLE",
            "last_reason": None, "blocked": False, "deadline_violation": False,
            "last_error": None,
        }

    def _scan_guard(self) -> asyncio.Lock:
        if self._scan_lock is None:
            self._scan_lock = asyncio.Lock()
        return self._scan_lock

    def _flat_guard(self) -> asyncio.Lock:
        if self._flat_lock is None:
            self._flat_lock = asyncio.Lock()
        return self._flat_lock

    async def start(self) -> None:
        if self.running:
            return
        self.running = True
        self._scanner_task = asyncio.create_task(
            self._scanner_loop(), name="prediction_paper_scanner"
        )
        self._flat_task = asyncio.create_task(
            self._flat_loop(), name="prediction_paper_auto_flat"
        )

    async def stop(self) -> None:
        self.running = False
        tasks = [t for t in (self._scanner_task, self._flat_task) if t is not None]
        for task in tasks:
            task.cancel()
        for task in tasks:
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass
        self._scanner_task = None
        self._flat_task = None
        self._scan_lock = None
        self._flat_lock = None

    def status(self) -> dict[str, Any]:
        with self._state_lock:
            scan = dict(self._last_scan)
            last_good = (
                dict(self._last_successful_scan)
                if self._last_successful_scan is not None else None
            )
            flat = dict(self._last_flat)
            blocked = bool(self._flat_blocked)
        return {
            "version": AUTOMATION_VERSION,
            "running": self.running,
            "scanner": scan,
            "last_successful_scan": last_good,
            "auto_flat": flat,
            "bounds": {
                "scan_interval_seconds": self.config.scan_interval_seconds,
                "flat_interval_seconds": self.config.flat_interval_seconds,
                "flat_lead_seconds": self.config.flat_lead_seconds,
                "discovery_limit": self.config.discovery_limit,
                "max_concurrency": self.config.max_concurrency,
                "orderbook_depth": self.config.orderbook_depth,
                "history_minutes": self.config.history_minutes,
                "quantity_contracts": _fixed(self.config.quantity),
            },
            "unattended_paper_open_enabled": False,
            "unattended_paper_open_blocked": True,
            "automatic_paper_position_opening": False,
            "unattended_paper_open_block_reasons": (
                ["AUTO_FLAT_SAFETY_BLOCKED", "RUNTIME_VALIDATION_REQUIRED"]
                if blocked else ["RUNTIME_VALIDATION_REQUIRED"]
            ),
            "execution": "PAPER_ONLY",
            "live_execution": False,
            "live_capital_allowed": False,
            "automatic_real_money_execution": False,
            "policy": policy_snapshot(),
        }

    async def run_scan_once(self, *, now: datetime | None = None) -> dict[str, Any]:
        scan_lock = self._scan_guard()
        if scan_lock.locked():
            with self._state_lock:
                return {**self._last_scan, "duplicate_cycle_skipped": True}
        async with scan_lock:
            current = now or _now()
            cycle_id = str(uuid.uuid4())[:12]
            state = self._empty_scan_state()
            state.update(
                {"cycle_id": cycle_id, "running": True, "started_at": _iso(current)}
            )
            with self._state_lock:
                self._last_scan = dict(state)
            success = False
            try:
                payload = await asyncio.wait_for(
                    kalshi_public.get_markets(
                        status="open",
                        limit=max(1, min(int(self.config.discovery_limit), 200)),
                    ),
                    timeout=12.0,
                )
                rows = payload.get("markets") if isinstance(payload, dict) else []
                markets = [
                    row for row in rows if isinstance(row, dict)
                ][: self.config.discovery_limit]
                state["markets_discovered"] = len(markets)

                survivors = []
                for market in markets:
                    reasons = self._prefilter_reasons(market, current)
                    if not reasons:
                        survivors.append(market)
                        continue
                    state["markets_prefilter_rejected"] += 1
                    for side in ("YES", "NO"):
                        prediction_paper_journal.log_candidate(
                            self._prefilter_candidate(
                                market, side, reasons, cycle_id, current
                            )
                        )
                        state["rejected_count"] += 1

                semaphore = asyncio.Semaphore(
                    max(1, min(int(self.config.max_concurrency), 16))
                )

                async def evaluate_market(market: dict[str, Any]) -> list[dict[str, Any]]:
                    async with semaphore:
                        return await asyncio.wait_for(
                            self._evaluate_market(market, cycle_id, current),
                            timeout=25.0,
                        )

                results = await asyncio.gather(
                    *(evaluate_market(market) for market in survivors),
                    return_exceptions=True,
                )
                eligible = []
                for market, result in zip(survivors, results):
                    if isinstance(result, BaseException):
                        state["error_count"] += 1
                        timed_out = isinstance(result, asyncio.TimeoutError)
                        if timed_out:
                            state["timeout_count"] += 1
                        state["last_error"] = type(result).__name__
                        reason = (
                            "SCANNER_EVALUATION_TIMEOUT"
                            if timed_out else "SCANNER_EVALUATION_ERROR"
                        )
                        for side in ("YES", "NO"):
                            prediction_paper_journal.log_candidate(
                                self._error_candidate(
                                    market, side, reason, cycle_id, current, result
                                )
                            )
                            state["rejected_count"] += 1
                        continue
                    state["markets_fully_evaluated"] += 1
                    for evaluation in result:
                        if evaluation.get("side") == "YES":
                            state["yes_evaluations"] += 1
                        elif evaluation.get("side") == "NO":
                            state["no_evaluations"] += 1
                        prediction_paper_journal.log_candidate(evaluation)
                        if evaluation.get("eligible"):
                            state["eligible_count"] += 1
                            eligible.append(evaluation)
                        else:
                            state["rejected_count"] += 1

                eligible.sort(key=lambda row: int(row.get("score") or 0), reverse=True)
                state["top_eligible"] = [
                    {
                        "ticker": row.get("ticker"),
                        "side": row.get("side"),
                        "score": row.get("score"),
                        "net_edge_dollars_per_contract": (
                            row.get("projected") or {}
                        ).get("net_edge_dollars_per_contract"),
                    }
                    for row in eligible[:5]
                ]
                success = True
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                state["error_count"] += 1
                if isinstance(exc, asyncio.TimeoutError):
                    state["timeout_count"] += 1
                state["last_error"] = type(exc).__name__
            finally:
                state["running"] = False
                state["finished_at"] = _iso()
                with self._state_lock:
                    self._last_scan = dict(state)
                    if success:
                        self._last_successful_scan = dict(state)
            return dict(state)

    def _prefilter_reasons(
        self, market: dict[str, Any], now: datetime
    ) -> list[str]:
        cfg = RepricingConfig()
        reasons: list[str] = []
        structure = (
            market.get("market_structure")
            if isinstance(market.get("market_structure"), dict) else {}
        )
        if structure.get("single_market") is not True or structure.get("multivariate") is True:
            reasons.append("NOT_SINGLE_MARKET")
        if str(market.get("status") or "").lower() != "open":
            reasons.append("MARKET_NOT_OPEN")
        if market.get("is_provisional") is True:
            reasons.append("PROVISIONAL_MARKET")
        occurrence = _parse_dt((market.get("timing") or {}).get("occurrence_datetime"))
        if occurrence is None:
            reasons.append("MISSING_OCCURRENCE_DATETIME")
        else:
            minutes_to_start = (occurrence - now).total_seconds() / 60.0
            flat_deadline = occurrence - timedelta(minutes=cfg.flat_buffer_minutes)
            if minutes_to_start <= cfg.min_entry_lead_minutes:
                reasons.append("TOO_CLOSE_TO_EVENT_START")
            if now >= flat_deadline:
                reasons.append("MANDATORY_FLAT_WINDOW")
        activity = (
            market.get("activity") if isinstance(market.get("activity"), dict) else {}
        )
        volume = _d(activity.get("volume_24h_contracts"))
        oi = _d(activity.get("open_interest_contracts"))
        if volume is None or volume < cfg.min_24h_volume:
            reasons.append("INSUFFICIENT_24H_VOLUME")
        if oi is None or oi < cfg.min_open_interest:
            reasons.append("INSUFFICIENT_OPEN_INTEREST")
        return list(dict.fromkeys(reasons))

    def _prefilter_candidate(
        self,
        market: dict[str, Any],
        side: str,
        reasons: list[str],
        cycle_id: str,
        now: datetime,
    ) -> dict[str, Any]:
        occurrence = _parse_dt((market.get("timing") or {}).get("occurrence_datetime"))
        cfg = RepricingConfig()
        flat_deadline = (
            occurrence - timedelta(minutes=cfg.flat_buffer_minutes)
            if occurrence else None
        )
        return {
            "engine_version": PAPER_ENGINE_VERSION,
            "automation_version": AUTOMATION_VERSION,
            "policy_version": POLICY_VERSION,
            "strategy": "PRE_EVENT_RECENT_RECLAIM_V1",
            "mode": "PAPER_RESEARCH_ONLY",
            "evaluation_stage": "CHEAP_PREFILTER",
            "scan_cycle_id": cycle_id,
            "eligible": False,
            "score": 0,
            "ticker": market.get("ticker"),
            "side": side,
            "quantity_contracts": _fixed(self.config.quantity),
            "occurrence_datetime": _iso(occurrence) if occurrence else None,
            "flat_deadline": _iso(flat_deadline) if flat_deadline else None,
            "rejection_reasons": reasons,
            "warnings": [],
            "fee_model": FEE_MODEL_VERSION,
            "observed_at": _iso(now),
            "live_capital_allowed": False,
            "automatic_real_money_execution": False,
        }

    def _error_candidate(
        self,
        market: dict[str, Any],
        side: str,
        reason: str,
        cycle_id: str,
        now: datetime,
        error: BaseException,
    ) -> dict[str, Any]:
        return {
            "engine_version": PAPER_ENGINE_VERSION,
            "automation_version": AUTOMATION_VERSION,
            "policy_version": POLICY_VERSION,
            "strategy": "PRE_EVENT_RECENT_RECLAIM_V1",
            "mode": "PAPER_RESEARCH_ONLY",
            "evaluation_stage": "FULL_EVALUATION_ERROR",
            "scan_cycle_id": cycle_id,
            "eligible": False,
            "score": 0,
            "ticker": market.get("ticker"),
            "side": side,
            "quantity_contracts": _fixed(self.config.quantity),
            "rejection_reasons": [reason],
            "warnings": [],
            "error_type": type(error).__name__,
            "fee_model": FEE_MODEL_VERSION,
            "observed_at": _iso(now),
            "live_capital_allowed": False,
            "automatic_real_money_execution": False,
        }

    async def _evaluate_market(
        self, market: dict[str, Any], cycle_id: str, now: datetime
    ) -> list[dict[str, Any]]:
        ticker = str(market.get("ticker") or "").strip().upper()
        if not ticker:
            raise PredictionPaperError("discovered market ticker missing")
        book_payload = await kalshi_public.get_orderbook(
            ticker, depth=self.config.orderbook_depth
        )
        end_ts = int(now.timestamp())
        start_ts = end_ts - (
            max(5, min(int(self.config.history_minutes), 1000)) * 60
        )
        candles_payload = await kalshi_public.get_candlesticks(
            ticker=ticker,
            start_ts=start_ts,
            end_ts=end_ts,
            period_interval=1,
            include_latest_before_start=True,
        )
        orderbook = book_payload.get("orderbook") or {}
        candles = candles_payload.get("candlesticks") or []
        evaluations = []
        for side in ("YES", "NO"):
            evaluation = evaluate_pre_event_repricing(
                market=market,
                orderbook=orderbook,
                candles=candles,
                side=side,
                quantity=self.config.quantity,
                now=now,
            )
            evaluation["automation_version"] = AUTOMATION_VERSION
            evaluation["evaluation_stage"] = "FULL"
            evaluation["scan_cycle_id"] = cycle_id
            evaluations.append(evaluation)
        return evaluations

    async def run_auto_flat_once(
        self, *, now: datetime | None = None
    ) -> dict[str, Any]:
        flat_lock = self._flat_guard()
        if flat_lock.locked():
            with self._state_lock:
                return {**self._last_flat, "duplicate_check_skipped": True}
        async with flat_lock:
            current = now or _now()
            state = self._empty_flat_state()
            state["last_check_at"] = _iso(current)
            opened = prediction_paper_journal.open_trade()
            if not opened:
                with self._state_lock:
                    self._flat_blocked = False
                    self._last_flat = dict(state)
                return state

            state["last_trade_id"] = opened.get("trade_id")
            flat_deadline = _parse_dt(opened.get("flat_deadline"))
            occurrence = _parse_dt(opened.get("occurrence_datetime"))
            if flat_deadline is None:
                return self._record_flat_block(
                    opened, state, "AUTO_FLAT_MISSING_DEADLINE", current
                )
            due_at = flat_deadline - timedelta(
                seconds=max(0.0, float(self.config.flat_lead_seconds))
            )
            if current < due_at:
                state["last_action"] = "WAITING_FOR_FLAT_DEADLINE"
                with self._state_lock:
                    self._flat_blocked = False
                    self._last_flat = dict(state)
                return state
            if occurrence is not None and current >= occurrence:
                return self._record_flat_block(
                    opened,
                    state,
                    "AUTO_FLAT_DEADLINE_VIOLATION",
                    current,
                    deadline_violation=True,
                )

            ticker = str(opened.get("ticker") or "").strip().upper()
            if not ticker:
                return self._record_flat_block(
                    opened, state, "AUTO_FLAT_MISSING_TICKER", current
                )
            try:
                payload = await asyncio.wait_for(
                    kalshi_public.get_orderbook(
                        ticker, depth=self.config.orderbook_depth
                    ),
                    timeout=12.0,
                )
                orderbook = payload.get("orderbook") or {}
                closed = prediction_paper_journal.close_from_orderbook(
                    orderbook=orderbook,
                    exit_reason="AUTO_FLAT_EXECUTED",
                    now=current,
                )
                state.update(
                    {
                        "last_action": "AUTO_FLAT_EXECUTED",
                        "last_reason": closed.get("exit_reason"),
                        "blocked": False,
                        "deadline_violation": bool(
                            closed.get("violated_flat_deadline")
                        ),
                    }
                )
                with self._state_lock:
                    self._flat_blocked = False
                    self._last_flat = dict(state)
                return state
            except asyncio.TimeoutError:
                return self._record_flat_block(
                    opened, state, "AUTO_FLAT_PROVIDER_TIMEOUT", current
                )
            except PredictionPaperError as exc:
                raw = str(exc)
                if raw == "INSUFFICIENT_EXECUTABLE_DEPTH":
                    reason = "AUTO_FLAT_BLOCKED_INSUFFICIENT_DEPTH"
                elif raw == "NO_EXECUTABLE_DEPTH":
                    reason = "AUTO_FLAT_BLOCKED_NO_DEPTH"
                else:
                    reason = "AUTO_FLAT_PAPER_ERROR"
                return self._record_flat_block(
                    opened, state, reason, current, error=raw
                )
            except PredictionProviderError as exc:
                return self._record_flat_block(
                    opened,
                    state,
                    "AUTO_FLAT_PROVIDER_ERROR",
                    current,
                    error=str(exc),
                )
            except Exception as exc:
                return self._record_flat_block(
                    opened,
                    state,
                    "AUTO_FLAT_UNEXPECTED_ERROR",
                    current,
                    error=type(exc).__name__,
                )

    def _record_flat_block(
        self,
        opened: dict[str, Any],
        state: dict[str, Any],
        reason: str,
        now: datetime,
        *,
        error: str | None = None,
        deadline_violation: bool = False,
    ) -> dict[str, Any]:
        row = {
            "event": "auto_flat_blocked",
            "trade_id": opened.get("trade_id"),
            "trade_type": "PREDICTION_PAPER",
            "timestamp": _iso(now),
            "ticker": opened.get("ticker"),
            "side": opened.get("side"),
            "quantity_contracts": opened.get("quantity_contracts"),
            "flat_deadline": opened.get("flat_deadline"),
            "occurrence_datetime": opened.get("occurrence_datetime"),
            "reason": reason,
            "deadline_violation": deadline_violation,
            "error": error,
            "automation_version": AUTOMATION_VERSION,
            "policy_version": POLICY_VERSION,
            "live_capital_allowed": False,
            "automatic_real_money_execution": False,
        }
        with self._state_lock:
            duplicate = (
                self._last_flat.get("last_trade_id") == opened.get("trade_id")
                and self._last_flat.get("last_reason") == reason
                and self._last_flat.get("blocked") is True
            )
        if not duplicate:
            logger = getattr(prediction_paper_journal, "log_event", None)
            if callable(logger):
                logger(row)
            else:
                prediction_paper_journal._append(prediction_paper_journal.journal_path, row)
        state.update(
            {
                "last_action": "BLOCKED",
                "last_reason": reason,
                "blocked": True,
                "deadline_violation": deadline_violation,
                "last_error": error,
            }
        )
        with self._state_lock:
            self._flat_blocked = True
            self._last_flat = dict(state)
        return state

    async def _scanner_loop(self) -> None:
        while self.running:
            try:
                await self.run_scan_once()
            except asyncio.CancelledError:
                raise
            except Exception:
                pass
            await asyncio.sleep(
                max(5.0, float(self.config.scan_interval_seconds))
            )

    async def _flat_loop(self) -> None:
        while self.running:
            try:
                await self.run_auto_flat_once()
            except asyncio.CancelledError:
                raise
            except Exception:
                pass
            await asyncio.sleep(
                max(1.0, float(self.config.flat_interval_seconds))
            )


prediction_paper_automation = PredictionPaperAutomation()
