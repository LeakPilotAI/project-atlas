"""Manual, gated public Hyperliquid market-data snapshots for Personal PAPER."""

from __future__ import annotations

import asyncio
import hashlib
import json
import math
import re
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock
from typing import Any

import httpx

from app.adapters import hyperliquid_gate_registry
from app.adapters.hyperliquid import HyperliquidAdapter, Ticker
from app.adapters.hyperliquid_gate_registry import install_gate
from app.adapters.hyperliquid_request_gate import (
    HyperliquidRequestGate,
    RequestGateRefused,
)
from app.core.durable_io import sync_parent, write_flushed

SCHEMA = "ATLAS_HYPERLIQUID_PUBLIC_MARKET_DATA_V1"
CORE_SYMBOLS = ("BTC", "ETH", "SOL")
SYMBOLS = CORE_SYMBOLS
MAX_ELIGIBLE_SYMBOLS = 10_000
_SYMBOL_PATTERN = re.compile(r"[A-Za-z0-9._:-]{1,32}\Z")
DAILY_CANDLE_LOOKBACK = 365
MAX_RECORD_BYTES = 2 * 1024 * 1024
MAX_STORE_BYTES = 16 * 1024 * 1024
REQUEST_BUDGET = 12
MAX_SYMBOLS_PER_REFRESH = REQUEST_BUDGET - 2
MANUAL_REFRESH_COOLDOWN_SEC = 30
RECENT_RETRIEVAL_MAX_AGE_SEC = 120
_STORE_LOCK = Lock()


class HyperliquidPublicDataError(ValueError):
    pass


def _validate_symbol(value: Any) -> str:
    if type(value) is not str or _SYMBOL_PATTERN.fullmatch(value) is None:
        raise HyperliquidPublicDataError("Invalid Hyperliquid perpetual symbol")
    return value


def _validate_selected_symbols(value: Any) -> tuple[str, ...]:
    if type(value) not in (tuple, list):
        raise HyperliquidPublicDataError("Invalid selected Hyperliquid perpetual symbols")
    symbols = tuple(_validate_symbol(symbol) for symbol in value)
    if (
        not len(CORE_SYMBOLS) <= len(symbols) <= MAX_SYMBOLS_PER_REFRESH
        or symbols[:len(CORE_SYMBOLS)] != CORE_SYMBOLS
        or len(set(symbols)) != len(symbols)
    ):
        raise HyperliquidPublicDataError("Invalid selected Hyperliquid perpetual universe")
    return symbols


def select_perp_symbols(
    tickers: list[Ticker],
    *,
    limit: int = MAX_SYMBOLS_PER_REFRESH,
) -> tuple[str, ...]:
    """Keep the core markets and select additional live perps by notional volume."""
    if (
        type(tickers) is not list
        or len(tickers) > MAX_ELIGIBLE_SYMBOLS
        or type(limit) is not int
        or not len(CORE_SYMBOLS) <= limit <= MAX_SYMBOLS_PER_REFRESH
    ):
        raise HyperliquidPublicDataError("Invalid bounded Hyperliquid universe selection")
    by_symbol: dict[str, Ticker] = {}
    for ticker in tickers:
        if not isinstance(ticker, Ticker):
            raise HyperliquidPublicDataError("Malformed Hyperliquid perpetual ticker")
        symbol = _validate_symbol(ticker.symbol)
        if symbol in by_symbol:
            raise HyperliquidPublicDataError("Duplicate Hyperliquid market symbol")
        _finite_positive(ticker.price, f"{symbol} mark")
        by_symbol[symbol] = ticker

    ranked = []
    for symbol, ticker in by_symbol.items():
        if symbol in CORE_SYMBOLS:
            continue
        volume = ticker.volume_24h
        if (
            type(volume) not in (int, float)
            or not math.isfinite(volume)
            or volume < 0
        ):
            continue
        ranked.append((-float(volume), symbol))
    ranked.sort()
    return (*CORE_SYMBOLS, *(symbol for _, symbol in ranked[:limit - len(CORE_SYMBOLS)]))


def initialize_public_data_budget(path: Path) -> int:
    gate = HyperliquidRequestGate(
        path,
        rights_approved=True,
        budget_approved=True,
        max_attempts=REQUEST_BUDGET,
    )
    return gate.remaining()


def install_public_data_budget(path: Path) -> HyperliquidRequestGate:
    path = Path(path)
    if not path.is_file():
        raise HyperliquidPublicDataError(
            "Hyperliquid public-data budget is not initialized; initialize it explicitly first"
        )
    gate = HyperliquidRequestGate(
        path,
        rights_approved=True,
        budget_approved=True,
        max_attempts=REQUEST_BUDGET,
    )
    install_gate(gate)
    return gate


def _finite_positive(value: Any, name: str) -> float:
    if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
        raise HyperliquidPublicDataError(f"Invalid Hyperliquid {name}")
    return float(value)


def _timestamp(value: str, name: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise HyperliquidPublicDataError(f"Invalid Hyperliquid {name}") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise HyperliquidPublicDataError(f"Timezone-aware Hyperliquid {name} required")
    return parsed.astimezone(UTC)


def _aware(value: datetime, name: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise HyperliquidPublicDataError(f"Timezone-aware Hyperliquid {name} required")
    return value.astimezone(UTC)


def _daily_bars(rows: Any, *, symbol: str, observed_ms: int) -> list[dict[str, Any]]:
    if type(rows) is not list or len(rows) > DAILY_CANDLE_LOOKBACK:
        raise HyperliquidPublicDataError("Invalid bounded Hyperliquid daily-candle list")
    output = []
    previous_ms = None
    for row in rows:
        if type(row) is not dict:
            raise HyperliquidPublicDataError("Malformed Hyperliquid daily candle")
        stamp = row.get("time")
        if type(stamp) is not int or stamp <= 0 or stamp > observed_ms:
            raise HyperliquidPublicDataError("Future or invalid Hyperliquid candle timestamp")
        if previous_ms is not None and stamp <= previous_ms:
            raise HyperliquidPublicDataError("Unordered or duplicate Hyperliquid candle")
        previous_ms = stamp
        prices = {
            key: _finite_positive(row.get(key), f"{symbol} candle {key}")
            for key in ("open", "high", "low", "close")
        }
        volume = row.get("volume")
        if type(volume) not in (int, float) or not math.isfinite(volume) or volume < 0:
            raise HyperliquidPublicDataError("Invalid Hyperliquid candle volume")
        trade_count = row.get("n")
        if trade_count is not None and (type(trade_count) is not int or trade_count < 0):
            raise HyperliquidPublicDataError("Invalid Hyperliquid candle trade count")
        if (
            prices["low"] > min(prices["open"], prices["close"])
            or prices["high"] < max(prices["open"], prices["close"])
            or prices["low"] > prices["high"]
        ):
            raise HyperliquidPublicDataError("Contradictory Hyperliquid candle OHLC")
        output.append({
            "timestamp_ms": stamp,
            "timestamp": datetime.fromtimestamp(stamp / 1000, UTC).isoformat(),
            "open": prices["open"],
            "high": prices["high"],
            "low": prices["low"],
            "close": prices["close"],
            "volume": float(volume),
            "trade_count": trade_count,
            "interval": "1d",
            "timestamp_basis": "PROVIDER_CANDLE_OPEN_TIME_MS",
            "source": "hyperliquid_info_candleSnapshot",
        })
    return output


def build_public_record(
    tickers: list[Ticker],
    candles_by_symbol: dict[str, list[dict[str, Any]]],
    *,
    request_started_at: datetime,
    retrieved_at: datetime,
    request_budget_remaining: int,
    symbols: tuple[str, ...] | list[str] | None = None,
) -> dict[str, Any]:
    started = _aware(request_started_at, "request start")
    retrieved = _aware(retrieved_at, "retrieval")
    if (
        retrieved < started
        or type(request_budget_remaining) is not int
        or not 0 <= request_budget_remaining <= REQUEST_BUDGET
    ):
        raise HyperliquidPublicDataError("Invalid Hyperliquid observation/budget window")

    if type(tickers) is not list or type(candles_by_symbol) is not dict:
        raise HyperliquidPublicDataError("Invalid Hyperliquid public observation")
    if len(tickers) > MAX_ELIGIBLE_SYMBOLS:
        raise HyperliquidPublicDataError("Hyperliquid perpetual universe exceeds its bound")
    selected_symbols = _validate_selected_symbols(
        select_perp_symbols(tickers) if symbols is None else symbols
    )
    by_symbol: dict[str, Ticker] = {}
    for ticker in tickers:
        if not isinstance(ticker, Ticker):
            raise HyperliquidPublicDataError("Malformed Hyperliquid perpetual ticker")
        symbol = _validate_symbol(ticker.symbol)
        if symbol in by_symbol:
            raise HyperliquidPublicDataError("Duplicate Hyperliquid market symbol")
        _finite_positive(ticker.price, f"{symbol} mark")
        by_symbol[symbol] = ticker
    eligible_symbols = sorted(by_symbol)
    if not set(selected_symbols).difference(CORE_SYMBOLS).issubset(by_symbol):
        raise HyperliquidPublicDataError("Selected market is absent from the live perpetual universe")
    if set(candles_by_symbol).difference(selected_symbols):
        raise HyperliquidPublicDataError("Unexpected Hyperliquid candle symbols")
    current_marks: dict[str, dict[str, Any]] = {}
    errors = []
    for symbol in selected_symbols:
        ticker = by_symbol.get(symbol)
        if ticker is None:
            errors.append(f"MISSING_MARK_{symbol}")
            continue
        mark = _finite_positive(ticker.price, f"{symbol} mark")
        stamp = _timestamp(ticker.timestamp, f"{symbol} request timestamp")
        age = (retrieved - stamp).total_seconds()
        if (
            ticker.timestamp_basis != "REST_REQUEST_START"
            or stamp < started
            or age < 0
            or age > 30
        ):
            errors.append(f"UNUSABLE_MARK_TIMESTAMP_{symbol}")
            continue
        current_marks[symbol] = {
            "price": mark,
            "request_timestamp": stamp.isoformat(),
            "receipt_age_seconds": round(age, 3),
            "timestamp_basis": "REST_REQUEST_START",
            "provider_timestamp_available": False,
            "price_kind": "MARK_PRICE",
            "source": "hyperliquid_info_metaAndAssetCtxs",
        }

    daily_bars = {}
    for symbol in selected_symbols:
        raw = candles_by_symbol.get(symbol)
        if type(raw) is not list or not raw:
            errors.append(f"DAILY_CANDLES_UNAVAILABLE_{symbol}")
            daily_bars[symbol] = []
        else:
            daily_bars[symbol] = _daily_bars(
                raw,
                symbol=symbol,
                observed_ms=int(retrieved.timestamp() * 1000),
            )

    record = {
        "schema": SCHEMA,
        "provider": "hyperliquid",
        "provider_endpoint_kind": "PUBLIC_INFO_ONLY",
        "symbols": list(selected_symbols),
        "eligible_perp_symbols": eligible_symbols,
        "omitted_perp_symbols": sorted(set(eligible_symbols).difference(selected_symbols)),
        "data_provenance": "PUBLIC_PROVIDER_DATA",
        "refresh_status": (
            "COMPLETE"
            if not errors and set(eligible_symbols).issubset(selected_symbols)
            else "PARTIAL"
        ),
        "provider_errors": errors,
        "request_started_at": started.isoformat(),
        "retrieved_at": retrieved.isoformat(),
        "current_marks": current_marks,
        "daily_bars": daily_bars,
        "daily_bar_interval": "1d",
        "request_budget_remaining": request_budget_remaining,
        "websocket_started": False,
        "private_account_accessed": False,
        "order_endpoint_used": False,
        "financial_execution_authorized": False,
        "paper_entry_authorized": False,
        "automatic_refresh_enabled": False,
        "operational_acceptance": False,
    }
    canonical = json.dumps(record, sort_keys=True, separators=(",", ":"), allow_nan=False)
    record["record_id"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return record


async def fetch_public_record(
    adapter: HyperliquidAdapter,
    *,
    request_budget: HyperliquidRequestGate,
    pause_seconds: float = 1.0,
) -> dict[str, Any]:
    if not isinstance(adapter, HyperliquidAdapter) or not 0 <= pause_seconds <= 5:
        raise HyperliquidPublicDataError("Invalid public-data adapter or request spacing")
    if hyperliquid_gate_registry.require_gate() is not request_budget:
        raise HyperliquidPublicDataError("Hyperliquid request budget does not match the installed gate")
    await adapter.connect_http_only()
    started = datetime.now(UTC)
    candles: dict[str, list[dict[str, Any]]] = {}
    try:
        tickers = await adapter.get_all_tickers()
        await asyncio.sleep(pause_seconds)
        candle_budget = request_budget.remaining()
        if type(candle_budget) is not int or candle_budget < len(CORE_SYMBOLS):
            raise HyperliquidPublicDataError(
                "Insufficient request budget to refresh core perpetual markets"
            )
        symbols = select_perp_symbols(
            tickers,
            limit=min(MAX_SYMBOLS_PER_REFRESH, candle_budget),
        )
        for index, symbol in enumerate(symbols):
            candles[symbol] = await adapter.get_candles(
                symbol,
                interval="1d",
                lookback=DAILY_CANDLE_LOOKBACK,
            )
            if index < len(symbols) - 1:
                await asyncio.sleep(pause_seconds)
        return build_public_record(
            tickers,
            candles,
            request_started_at=started,
            retrieved_at=datetime.now(UTC),
            request_budget_remaining=request_budget.remaining(),
            symbols=symbols,
        )
    except httpx.TimeoutException as exc:
        raise HyperliquidPublicDataError("HYPERLIQUID_PUBLIC_HTTP_TIMEOUT") from exc
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code if exc.response is not None else "UNKNOWN"
        raise HyperliquidPublicDataError(f"HYPERLIQUID_PUBLIC_HTTP_STATUS_{status}") from exc
    except httpx.RequestError as exc:
        raise HyperliquidPublicDataError(
            f"HYPERLIQUID_PUBLIC_TRANSPORT_{type(exc).__name__}"
        ) from exc
    except RequestGateRefused:
        raise
    finally:
        await adapter.close()


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for key, value in pairs:
        if key in output:
            raise HyperliquidPublicDataError("Duplicate Hyperliquid record field")
        output[key] = value
    return output


def _reject_constant(_value: str) -> None:
    raise HyperliquidPublicDataError("Nonfinite Hyperliquid JSON value")


def _validate_record(record: Any) -> dict[str, Any]:
    if type(record) is not dict or record.get("schema") != SCHEMA:
        raise HyperliquidPublicDataError("Unsupported Hyperliquid public-data record")
    try:
        symbols = _validate_selected_symbols(record.get("symbols"))
    except HyperliquidPublicDataError as exc:
        raise HyperliquidPublicDataError("Invalid Hyperliquid selected market universe") from exc
    if (
        record.get("provider") != "hyperliquid"
        or record.get("provider_endpoint_kind") != "PUBLIC_INFO_ONLY"
        or record.get("data_provenance") != "PUBLIC_PROVIDER_DATA"
        or record.get("refresh_status") not in {"COMPLETE", "PARTIAL"}
        or record.get("daily_bar_interval") != "1d"
        or record.get("websocket_started") is not False
        or record.get("private_account_accessed") is not False
        or record.get("order_endpoint_used") is not False
        or record.get("financial_execution_authorized") is not False
        or record.get("paper_entry_authorized") is not False
        or record.get("automatic_refresh_enabled") is not False
        or record.get("operational_acceptance") is not False
    ):
        raise HyperliquidPublicDataError("Hyperliquid data scope or authority mismatch")
    started = _timestamp(record.get("request_started_at"), "request start")
    retrieved = _timestamp(record.get("retrieved_at"), "retrieval")
    if retrieved < started or (retrieved - started).total_seconds() > 180:
        raise HyperliquidPublicDataError("Invalid Hyperliquid request/retrieval interval")
    errors = record.get("provider_errors")
    if (
        type(errors) is not list
        or any(type(error) is not str or not error for error in errors)
        or len(set(errors)) != len(errors)
    ):
        raise HyperliquidPublicDataError("Invalid Hyperliquid provider errors")
    if type(record.get("current_marks")) is not dict or type(record.get("daily_bars")) is not dict:
        raise HyperliquidPublicDataError("Invalid Hyperliquid market-data maps")
    if not set(record["current_marks"]).issubset(symbols):
        raise HyperliquidPublicDataError("Invalid Hyperliquid current-mark symbols")
    if set(record["daily_bars"]) != set(symbols):
        raise HyperliquidPublicDataError("Incomplete Hyperliquid daily-bar map")
    has_coverage = (
        "eligible_perp_symbols" in record or "omitted_perp_symbols" in record
    )
    eligible_symbols = record.get("eligible_perp_symbols")
    omitted_symbols = record.get("omitted_perp_symbols")
    if has_coverage:
        if (
            type(eligible_symbols) is not list
            or type(omitted_symbols) is not list
            or len(eligible_symbols) > MAX_ELIGIBLE_SYMBOLS
            or len(omitted_symbols) > MAX_ELIGIBLE_SYMBOLS
            or any(type(value) is not str for value in eligible_symbols + omitted_symbols)
            or any(_SYMBOL_PATTERN.fullmatch(value) is None
                   for value in eligible_symbols + omitted_symbols)
            or eligible_symbols != sorted(set(eligible_symbols))
            or omitted_symbols != sorted(set(omitted_symbols))
            or set(omitted_symbols) != set(eligible_symbols).difference(symbols)
        ):
            raise HyperliquidPublicDataError("Invalid Hyperliquid universe coverage")
    else:
        eligible_symbols = list(symbols)
        omitted_symbols = []
    for symbol, rows in record["daily_bars"].items():
        if type(rows) is not list or len(rows) > DAILY_CANDLE_LOOKBACK:
            raise HyperliquidPublicDataError("Invalid Hyperliquid daily-bar count")
        previous = 0
        for row in rows:
            if type(row) is not dict:
                raise HyperliquidPublicDataError(f"Malformed Hyperliquid {symbol} daily bar")
            stamp = row.get("timestamp_ms")
            if (
                type(stamp) is not int
                or stamp <= previous
                or stamp > int(retrieved.timestamp() * 1000)
                or row.get("interval") != "1d"
                or row.get("timestamp_basis") != "PROVIDER_CANDLE_OPEN_TIME_MS"
                or row.get("source") != "hyperliquid_info_candleSnapshot"
            ):
                raise HyperliquidPublicDataError(f"Invalid Hyperliquid {symbol} daily-bar order")
            if _timestamp(row.get("timestamp"), f"{symbol} candle timestamp") != datetime.fromtimestamp(
                stamp / 1000,
                UTC,
            ):
                raise HyperliquidPublicDataError(f"Mismatched Hyperliquid {symbol} candle timestamp")
            prices = {
                key: _finite_positive(row.get(key), f"{symbol} candle {key}")
                for key in ("open", "high", "low", "close")
            }
            if (
                prices["low"] > min(prices["open"], prices["close"])
                or prices["high"] < max(prices["open"], prices["close"])
                or prices["low"] > prices["high"]
            ):
                raise HyperliquidPublicDataError(f"Contradictory Hyperliquid {symbol} candle OHLC")
            volume = row.get("volume")
            trades = row.get("trade_count")
            if (
                type(volume) not in (int, float)
                or not math.isfinite(volume)
                or volume < 0
                or (
                    trades is not None
                    and (type(trades) is not int or trades < 0)
                )
            ):
                raise HyperliquidPublicDataError(f"Invalid Hyperliquid {symbol} candle statistics")
            previous = stamp
    for symbol, mark in record["current_marks"].items():
        if symbol not in symbols or type(mark) is not dict:
            raise HyperliquidPublicDataError("Invalid Hyperliquid mark symbol")
        _finite_positive(mark.get("price"), f"{symbol} stored mark")
        mark_time = _timestamp(mark.get("request_timestamp"), f"{symbol} stored mark timestamp")
        age = (retrieved - mark_time).total_seconds()
        if (
            mark.get("timestamp_basis") != "REST_REQUEST_START"
            or mark.get("provider_timestamp_available") is not False
            or mark.get("price_kind") != "MARK_PRICE"
            or mark.get("source") != "hyperliquid_info_metaAndAssetCtxs"
            or mark_time < started
            or age < 0
            or age > 30
            or mark.get("receipt_age_seconds") != round(age, 3)
        ):
            raise HyperliquidPublicDataError(f"Invalid Hyperliquid {symbol} mark provenance")
    complete = (
        set(record["current_marks"]) == set(symbols)
        and all(record["daily_bars"][symbol] for symbol in symbols)
        and not omitted_symbols
        and not errors
    )
    if (record["refresh_status"] == "COMPLETE") != complete:
        raise HyperliquidPublicDataError("Inconsistent Hyperliquid snapshot completion status")
    budget_remaining = record.get("request_budget_remaining")
    if type(budget_remaining) is not int or not 0 <= budget_remaining <= REQUEST_BUDGET:
        raise HyperliquidPublicDataError("Invalid Hyperliquid request budget receipt")
    canonical = dict(record)
    record_id = canonical.pop("record_id", None)
    encoded = json.dumps(canonical, sort_keys=True, separators=(",", ":"), allow_nan=False)
    if record_id != hashlib.sha256(encoded.encode("utf-8")).hexdigest():
        raise HyperliquidPublicDataError("Hyperliquid public-data digest mismatch")
    return record


def read_public_data(path: Path) -> list[dict[str, Any]]:
    path = Path(path)
    if not path.exists():
        return []
    if path.is_symlink() or not path.is_file():
        raise HyperliquidPublicDataError("Linked or non-file Hyperliquid journal refused")
    if path.stat().st_size > MAX_STORE_BYTES:
        raise HyperliquidPublicDataError("Hyperliquid public-data journal exceeds its size limit")
    rows = []
    with path.open("rb") as stream:
        while raw := stream.readline(MAX_RECORD_BYTES + 1):
            if len(raw) > MAX_RECORD_BYTES or not raw.endswith(b"\n"):
                raise HyperliquidPublicDataError("Oversized or incomplete Hyperliquid journal record")
            try:
                value = json.loads(
                    raw,
                    object_pairs_hook=_unique_object,
                    parse_constant=_reject_constant,
                )
                rows.append(_validate_record(value))
            except (UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
                raise HyperliquidPublicDataError("Unreadable Hyperliquid public-data journal") from exc
    return rows


def append_public_data(path: Path, record: dict[str, Any]) -> dict[str, Any]:
    path = Path(path)
    valid = _validate_record(record)
    payload = json.dumps(valid, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n"
    if len(payload.encode("utf-8")) > MAX_RECORD_BYTES:
        raise HyperliquidPublicDataError("Hyperliquid public-data record exceeds its size limit")
    with _STORE_LOCK:
        existing = read_public_data(path)
        if any(row["record_id"] == valid["record_id"] for row in existing):
            raise HyperliquidPublicDataError("Duplicate Hyperliquid public-data record refused")
        if path.exists() and path.stat().st_size + len(payload.encode("utf-8")) > MAX_STORE_BYTES:
            raise HyperliquidPublicDataError("Hyperliquid public-data journal exceeds its size limit")
        path.parent.mkdir(parents=True, exist_ok=True)
        existed = path.exists()
        with path.open("a", encoding="utf-8", newline="\n") as stream:
            write_flushed(stream, payload)
        if not existed:
            sync_parent(path)
    return valid


def public_data_read_model(path: Path) -> dict[str, Any]:
    latest = read_public_data(path)
    record = max(latest, key=lambda row: row["retrieved_at"]) if latest else None
    age_seconds = None
    freshness_status = "NO_DATA"
    if record is not None:
        age_seconds = (
            datetime.now(UTC) - _timestamp(record["retrieved_at"], "latest retrieval")
        ).total_seconds()
        if age_seconds < 0:
            freshness_status = "LOCAL_CLOCK_SKEW"
        elif age_seconds <= RECENT_RETRIEVAL_MAX_AGE_SEC:
            freshness_status = "RECENT_LOCAL_RETRIEVAL"
        else:
            freshness_status = "STALE_LOCAL_RETRIEVAL"
    return {
        "schema": "ATLAS_PERSONAL_HYPERLIQUID_MARKET_DATA_READ_V1",
        "data_provenance": "PUBLIC_PROVIDER_DATA",
        "record_count": len(latest),
        "latest": record,
        "freshness": {
            "status": freshness_status,
            "basis": "LOCAL_RETRIEVAL_TIME_ONLY",
            "age_seconds": round(age_seconds, 3) if age_seconds is not None else None,
            "provider_timestamp_available": False,
        },
        "provider_errors": record["provider_errors"] if record is not None else [],
        "paper_entry_authorized": False,
        "order_endpoint_used": False,
        "operational_acceptance": False,
    }


def require_manual_refresh_spacing(
    path: Path,
    *,
    now: datetime | None = None,
) -> None:
    current = _aware(now or datetime.now(UTC), "current time")
    rows = read_public_data(path)
    if not rows:
        return
    prior = _timestamp(rows[-1]["retrieved_at"], "prior retrieval")
    age = (current - prior).total_seconds()
    if age < 0:
        raise HyperliquidPublicDataError("Local clock precedes the last Hyperliquid retrieval")
    if age < MANUAL_REFRESH_COOLDOWN_SEC:
        raise HyperliquidPublicDataError("Hyperliquid public-data refresh cooldown is active")


async def refresh_and_store_public_data(
    adapter: HyperliquidAdapter,
    *,
    request_budget: HyperliquidRequestGate,
    path: Path,
    pause_seconds: float = 1.0,
) -> dict[str, Any]:
    require_manual_refresh_spacing(path)
    record = await fetch_public_record(
        adapter,
        request_budget=request_budget,
        pause_seconds=pause_seconds,
    )
    return append_public_data(path, record)
