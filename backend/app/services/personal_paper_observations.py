"""Manual public-market observation evaluation for the local Personal PAPER app."""

from __future__ import annotations

import json
import math
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.core.durable_io import sync_parent, write_flushed
from app.investment.quality_dips_paper import (
    initialize_paper_account,
    read_events,
    record_decision,
)
from app.investment.quality_dips_v3 import build_v3_entry_plan
from app.services.personal_hyperliquid_public_data import read_public_data
from app.services.personal_public_market_data import read_market_data

FORWARD_ACCOUNT_ID = "atlas-personal-qd-forward-paper-v1"
MAX_PUBLIC_SNAPSHOT_AGE = 15 * 60
MAX_QD_BAR_AGE = 15 * 60
MAX_QD_RESEARCH_AGE = 24 * 60 * 60
MAX_HYPERLIQUID_SNAPSHOT_AGE = 15 * 60
DAILY_CANDLE_MS = 86_400_000
MAX_OBSERVATION_STORE_BYTES = 16 * 1024 * 1024


def _aware(value: Any, field: str) -> datetime:
    if type(value) is not str:
        raise ValueError(f"{field} timestamp is required")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{field} timestamp is invalid") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field} timestamp must include a timezone")
    return parsed.astimezone(UTC)


def _research_for_symbol(rows: list[dict[str, Any]], symbol: str) -> dict[str, Any] | None:
    matches = [
        row for row in rows
        if type(row) is dict and str(row.get("symbol") or "").upper() == symbol
    ]
    if not matches:
        return None
    return max(matches, key=lambda row: str(row.get("timestamp") or ""))


def _score(row: dict[str, Any] | None, key: str, component: str | None = None) -> Any:
    if row is None:
        return None
    value = row.get(key)
    if value is not None:
        return value
    return dict(row.get("components") or {}).get(component or key)


def _qd_observation(
    record: dict[str, Any],
    research_rows: list[dict[str, Any]],
    *,
    now: datetime,
) -> dict[str, Any]:
    symbol = str(record["symbol"]).upper()
    quote = record["quote"]
    retrieved = _aware(record["retrieved_at"], "Yahoo retrieval")
    market_price = quote.get("price")
    source_time = quote.get("effective_timestamp")
    blockers: list[str] = []
    quote_at = None
    if market_price is None or source_time is None:
        blockers.append("TIMESTAMPED_YAHOO_INTRADAY_BAR_UNAVAILABLE")
    else:
        quote_at = _aware(source_time, "Yahoo bar")
        age = (now - quote_at).total_seconds()
        if quote_at > now:
            blockers.append("FUTURE_YAHOO_MARKET_OBSERVATION")
        elif age < 0 or age > MAX_QD_BAR_AGE:
            blockers.append("YAHOO_MARKET_OBSERVATION_STALE")
        if quote_at > retrieved:
            blockers.append("YAHOO_BAR_AFTER_RETRIEVAL")
        if (
            type(market_price) not in (int, float)
            or not math.isfinite(market_price)
            or market_price <= 0
        ):
            blockers.append("INVALID_YAHOO_MARKET_PRICE")

    snapshot_age = (now - retrieved).total_seconds()
    if snapshot_age < 0 or snapshot_age > MAX_PUBLIC_SNAPSHOT_AGE:
        blockers.append("YAHOO_PUBLIC_SNAPSHOT_STALE")

    research = _research_for_symbol(research_rows, symbol)
    research_age = None
    if research is None:
        blockers.append("QUALITY_DIPS_RESEARCH_UNAVAILABLE")
    else:
        try:
            research_at = _aware(research.get("timestamp"), "Quality Dips research")
            research_age = (now - research_at).total_seconds()
            if research_age < 0 or research_age > MAX_QD_RESEARCH_AGE:
                blockers.append("QUALITY_DIPS_RESEARCH_STALE")
        except ValueError:
            blockers.append("QUALITY_DIPS_RESEARCH_TIMESTAMP_INVALID")

    normalization = dict(
        (research or {}).get("normalization_value")
        or (research or {}).get("valuation_window")
        or {}
    )
    drawdown = dict((research or {}).get("drawdown") or {})
    flags = dict((research or {}).get("flags") or {})
    thesis = str((research or {}).get("thesis") or "").upper()
    plan = build_v3_entry_plan(
        symbol=symbol,
        current_price=market_price,
        normalization=normalization,
        quality_score=_score(research, "quality_score", "quality"),
        fundamentals_score=_score(research, "fundamentals_score", "fundamentals"),
        valuation_score=_score(research, "valuation_score", "valuation"),
        drawdown_percentile=drawdown.get("percentile", drawdown.get("historical_percentile")),
        evidence_quality=str((research or {}).get("evidence_quality") or "UNKNOWN"),
        thesis_intact=thesis in {"STRONG", "INTACT"},
        value_trap=bool(
            (research or {}).get("value_trap")
            or flags.get("value_trap")
            or flags.get("falling_knife")
        ),
    )

    # Yahoo's recorded value is an intraday bar close, not a contemporaneous quote.
    # It can inform V3 research, but it never becomes a simulated fill price.
    blockers.extend(plan["blockers"])
    blockers.append("YAHOO_TRADE_BAR_CLOSE_IS_NOT_AN_EXECUTABLE_QUOTE")
    timestamp = source_time or record["retrieved_at"]
    observation_id = f"yahoo:{record['record_id']}:{symbol}"
    observation = {
        "observation_id": observation_id,
        "symbol": symbol,
        "price": market_price,
        "source_timestamp": timestamp,
        "classification": plan["patient_state"],
        "strategy_version": "QUALITY_DIPS_V3",
        "policy_version": "quality-dips-v3-mos-15-20-25-30-v1",
        "evidence_class": "FORWARD_COLLECTION",
        "prediction": plan,
        "fixture_id": None,
    }
    return {
        "schema": "ATLAS_PERSONAL_PAPER_STRATEGY_OBSERVATION_V1",
        "observation_id": observation_id,
        "strategy": "QUALITY_DIPS_V3",
        "symbol": symbol,
        "source_record_id": record["record_id"],
        "source_timestamp": timestamp,
        "source_timestamp_basis": "YAHOO_INTRADAY_BAR_INDEX_TIME",
        "source_snapshot_retrieved_at": record["retrieved_at"],
        "source_snapshot_age_seconds": round(snapshot_age, 3),
        "research_age_seconds": None if research_age is None else round(research_age, 3),
        "price": market_price,
        "decision": "NO_TRADE",
        "strategy_result": plan,
        "blockers": list(dict.fromkeys(blockers)),
        "paper_execution_eligible": False,
        "execution_blocker": "YAHOO_TRADE_BAR_CLOSE_IS_NOT_AN_EXECUTABLE_QUOTE",
        "data_provenance": "PUBLIC_PROVIDER_DATA",
        "evidence_class": "FORWARD_COLLECTION",
        "broker_order_created": False,
        "live_capital_allowed": False,
    }, observation


def _hyperliquid_observations(
    record: dict[str, Any],
    *,
    now: datetime,
) -> list[dict[str, Any]]:
    from app.trading_core.perp_discovery import analyze_candles, rank_setup

    retrieved = _aware(record["retrieved_at"], "Hyperliquid retrieval")
    snapshot_age = (now - retrieved).total_seconds()
    output = []
    for symbol in record["symbols"]:
        closed = [
            bar for bar in record["daily_bars"][symbol]
            if bar["timestamp_ms"] + DAILY_CANDLE_MS
            <= int(min(now, retrieved).timestamp() * 1000)
        ]
        bars = closed[-96:]
        blockers = []
        if snapshot_age < 0 or snapshot_age > MAX_HYPERLIQUID_SNAPSHOT_AGE:
            blockers.append("HYPERLIQUID_PUBLIC_SNAPSHOT_STALE")
        if len(bars) < 20:
            blockers.append("INSUFFICIENT_CLOSED_DAILY_CANDLES")

        strategy_result = None
        if len(bars) >= 20:
            structure = analyze_candles(bars)
            strategy_result = {
                "structure": {
                    "side": None if structure.side is None else structure.side.value,
                    "confidence": structure.confidence,
                    "volatility_pct": structure.volatility_pct,
                    "momentum_pct": structure.momentum_pct,
                    "trend_pct": structure.trend_pct,
                    "reason": structure.reason,
                },
                "ranked_setup": None,
            }
            last = bars[-1]
            ranked = rank_setup(
                symbol=symbol,
                price=float(last["close"]),
                volume_24h=float(last["volume"]),
                open_interest=0.0,
                funding_rate=None,
                structure=structure,
            )
            if ranked is None:
                decision = "WAIT"
                blockers.append("EXISTING_PERP_STRATEGY_HAS_NO_DIRECTIONAL_SETUP")
            else:
                decision = "RESEARCH_SIGNAL"
                strategy_result["ranked_setup"] = {
                    "symbol": ranked.symbol,
                    "side": ranked.side.value,
                    "score": ranked.score,
                    "price": ranked.price,
                    "volume_24h": ranked.volume_24h,
                    "open_interest": ranked.open_interest,
                    "funding_rate": ranked.funding_rate,
                    "volatility_pct": ranked.volatility_pct,
                    "momentum_pct": ranked.momentum_pct,
                    "trend_pct": ranked.trend_pct,
                    "reason": ranked.reason,
                }
        else:
            decision = "WAIT"

        last_bar = bars[-1] if bars else None
        candle_close_at = (
            datetime.fromtimestamp(
                (last_bar["timestamp_ms"] + DAILY_CANDLE_MS) / 1000,
                UTC,
            ).isoformat()
            if last_bar
            else None
        )
        blockers.append("CLOSED_DAILY_CANDLE_CLOSE_IS_HISTORICAL_NOT_A_CURRENT_QUOTE")
        output.append({
            "schema": "ATLAS_PERSONAL_PAPER_STRATEGY_OBSERVATION_V1",
            "observation_id": f"hyperliquid:{record['record_id']}:{symbol}",
            "strategy": "HYPERLIQUID_PERP_DISCOVERY",
            "symbol": symbol,
            "source_record_id": record["record_id"],
            "source_timestamp": candle_close_at,
            "source_timestamp_basis": "PROVIDER_CANDLE_OPEN_TIME_MS_PLUS_1D",
            "source_snapshot_retrieved_at": record["retrieved_at"],
            "source_snapshot_age_seconds": round(snapshot_age, 3),
            "closed_candle_count": len(bars),
            "price": None if last_bar is None else last_bar["close"],
            "price_kind": "HISTORICAL_CLOSED_DAILY_CANDLE_CLOSE",
            "decision": decision,
            "strategy_result": strategy_result,
            "blockers": list(dict.fromkeys(blockers)),
            "paper_execution_eligible": False,
            "execution_blocker": "CLOSED_DAILY_CANDLE_CLOSE_IS_HISTORICAL_NOT_A_CURRENT_QUOTE",
            "data_provenance": "PUBLIC_PROVIDER_DATA",
            "broker_order_created": False,
            "live_capital_allowed": False,
        })
    return output


def evaluate_public_observations(
    *,
    market_data_path: Path,
    hyperliquid_data_path: Path,
    research_rows: list[dict[str, Any]] | None = None,
    now: datetime | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    current = now or datetime.now(UTC)
    if current.tzinfo is None or current.utcoffset() is None:
        raise ValueError("Personal PAPER evaluation clock must be timezone-aware")
    current = current.astimezone(UTC)
    yahoo_records = read_market_data(market_data_path)
    hyperliquid_records = read_public_data(hyperliquid_data_path)
    if not yahoo_records and not hyperliquid_records:
        raise ValueError("No persisted public market observations are available")

    output: list[dict[str, Any]] = []
    paper_decisions: list[dict[str, Any]] = []
    latest_yahoo: dict[str, dict[str, Any]] = {}
    for row in yahoo_records:
        prior = latest_yahoo.get(row["symbol"])
        if prior is None or row["retrieved_at"] > prior["retrieved_at"]:
            latest_yahoo[row["symbol"]] = row
    for record in sorted(latest_yahoo.values(), key=lambda row: row["symbol"]):
        decision, observation = _qd_observation(
            record,
            research_rows or [],
            now=current,
        )
        output.append(decision)
        paper_decisions.append(observation)

    if hyperliquid_records:
        latest = max(hyperliquid_records, key=lambda row: row["retrieved_at"])
        output.extend(_hyperliquid_observations(latest, now=current))
    return output, paper_decisions


def read_strategy_observations(path: Path) -> list[dict[str, Any]]:
    path = Path(path)
    if not path.exists():
        return []
    if path.stat().st_size > MAX_OBSERVATION_STORE_BYTES:
        raise ValueError("Personal PAPER strategy-observation journal exceeds its size limit")
    rows = []
    with path.open("rb") as stream:
        while raw := stream.readline(256 * 1024 + 1):
            if len(raw) > 256 * 1024 or not raw.endswith(b"\n"):
                raise ValueError("Oversized or incomplete strategy-observation record")
            row = json.loads(raw)
            if (
                type(row) is not dict
                or row.get("schema") != "ATLAS_PERSONAL_PAPER_STRATEGY_OBSERVATION_V1"
                or row.get("broker_order_created") is not False
            ):
                raise ValueError("Invalid Personal PAPER strategy-observation record")
            rows.append(row)
    return rows


def _append_strategy_observations(path: Path, observations: list[dict[str, Any]]) -> int:
    path = Path(path)
    existing = read_strategy_observations(path)
    ids = {row["observation_id"] for row in existing}
    pending = [row for row in observations if row["observation_id"] not in ids]
    if not pending:
        return len(existing)
    path.parent.mkdir(parents=True, exist_ok=True)
    existed = path.exists()
    with path.open("a", encoding="utf-8", newline="\n") as stream:
        for row in pending:
            write_flushed(stream, json.dumps(row, sort_keys=True, allow_nan=False) + "\n")
    if not existed:
        sync_parent(path)
    return len(existing) + len(pending)


def process_public_observations(
    *,
    market_data_path: Path,
    hyperliquid_data_path: Path,
    forward_journal_path: Path,
    strategy_observation_path: Path,
    research_rows: list[dict[str, Any]] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    observations, paper_decisions = evaluate_public_observations(
        market_data_path=market_data_path,
        hyperliquid_data_path=hyperliquid_data_path,
        research_rows=research_rows,
        now=now,
    )
    initialize_paper_account(
        account_id=FORWARD_ACCOUNT_ID,
        opening_cash=1000.0,
        fee_bps_per_side=2.0,
        max_open_positions=1,
        data_provenance="FORWARD_COLLECTION",
        path=forward_journal_path,
    )
    for observation in paper_decisions:
        record_decision(
            observation,
            decision="PUBLIC_OBSERVATION_NO_TRADE",
            reason=(
                "Timestamped public market input evaluated; "
                "executable current quote unavailable"
            ),
            account_id=FORWARD_ACCOUNT_ID,
            path=forward_journal_path,
        )
    decision_count = _append_strategy_observations(strategy_observation_path, observations)
    events = read_events(forward_journal_path)
    return {
        "schema": "ATLAS_PERSONAL_PAPER_PUBLIC_OBSERVATION_CYCLE_V1",
        "data_provenance": "PUBLIC_PROVIDER_DATA",
        "decision_count": len(observations),
        "strategy_observation_journal_count": decision_count,
        "forward_account_id": FORWARD_ACCOUNT_ID,
        "forward_account_events": len(events),
        "paper_positions_opened": 0,
        "paper_execution": "NO_TRADE_CURRENT_QUOTES_UNAVAILABLE",
        "broker_order_created": False,
        "live_capital_allowed": False,
        "automatic_real_money_execution": False,
        "genesis_accessed": False,
        "observations": observations,
    }
