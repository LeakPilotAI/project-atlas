"""Manual, Yahoo-only public market-data refresh for Personal PAPER research."""

from __future__ import annotations

import hashlib
import json
import math
import re
from datetime import UTC, date, datetime
from pathlib import Path
from threading import Lock
from typing import Any
from zoneinfo import ZoneInfo

from app.core.durable_io import sync_parent, write_flushed
from app.investment.quality_dip_quotes import (
    FRESH_AGE_SEC,
    LIVE_AGE_SEC,
    MAX_REFERENCE_AGE_SEC,
    _latest_intraday,
)
from app.investment.yahoo_price import dataframe_to_bars
from app.investment.yfinance_client import ProviderCallError, YFinanceClient, utcnow

SCHEMA = "ATLAS_QD_YAHOO_PUBLIC_MARKET_DATA_V1"
SYMBOL_PATTERN = re.compile(r"[A-Z][A-Z0-9.-]{0,14}\Z")
MAX_DAILY_BARS = 2000
MAX_RECORD_BYTES = 2 * 1024 * 1024
MAX_STORE_BYTES = 32 * 1024 * 1024
MANUAL_REFRESH_COOLDOWN_SEC = 30
_STORE_LOCK = Lock()
EASTERN = ZoneInfo("America/New_York")


class PublicMarketDataError(ValueError):
    pass


def _symbol(value: str) -> str:
    symbol = str(value or "").strip().upper()
    if not SYMBOL_PATTERN.fullmatch(symbol):
        raise PublicMarketDataError("A single explicit ticker symbol is required")
    return symbol


def _aware(value: datetime, field: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise PublicMarketDataError(f"{field} must be timezone-aware")
    return value.astimezone(UTC)


def build_yahoo_public_record(
    symbol: str,
    intraday: Any,
    daily: Any,
    *,
    request_started_at: datetime,
    retrieved_at: datetime,
    provider_errors: list[str] | None = None,
) -> dict[str, Any]:
    symbol = _symbol(symbol)
    started = _aware(request_started_at, "request_started_at")
    retrieved = _aware(retrieved_at, "retrieved_at")
    if retrieved < started:
        raise PublicMarketDataError("Provider retrieval time precedes request start")
    errors = list(provider_errors or [])
    if any(type(code) is not str or not code or len(code) > 80 for code in errors):
        raise PublicMarketDataError("Invalid bounded provider error code")

    latest = _latest_intraday(intraday, retrieved)
    quote: dict[str, Any]
    if latest is None:
        quote = {
            "price": None,
            "effective_timestamp": None,
            "age_seconds": None,
            "quality": "MISSING",
            "source": "yfinance_1m",
            "price_kind": "TRADE_BAR_CLOSE",
            "error": "NO_VALID_TIMESTAMPED_INTRADAY_BAR",
        }
    else:
        observed_at, price = latest
        age = (retrieved - observed_at).total_seconds()
        if not math.isfinite(price) or price <= 0 or age < 0:
            quote = {
                "price": None,
                "effective_timestamp": None,
                "age_seconds": None,
                "quality": "MISSING",
                "source": "yfinance_1m",
                "price_kind": "TRADE_BAR_CLOSE",
                "error": "INVALID_OR_FUTURE_PROVIDER_PRICE",
            }
        else:
            quality = (
                "LIVE" if age <= LIVE_AGE_SEC
                else "FRESH" if age <= FRESH_AGE_SEC
                else "REFERENCE" if age <= MAX_REFERENCE_AGE_SEC
                else "STALE"
            )
            quote = {
                "price": price,
                "effective_timestamp": observed_at.isoformat(),
                "age_seconds": round(age, 3),
                "quality": quality,
                "source": "yfinance_1m",
                "price_kind": "TRADE_BAR_CLOSE",
                "error": None,
            }

    bars = dataframe_to_bars(daily, source="yfinance", retrieved_at=retrieved)
    if not bars and not errors:
        errors.append("YAHOO_DAILY_HISTORY_EMPTY")
    if len(bars) > MAX_DAILY_BARS:
        raise PublicMarketDataError("Yahoo history exceeded the bounded daily-bar window")
    sessions = [bar.session_date for bar in bars]
    if len(set(sessions)) != len(sessions):
        raise PublicMarketDataError("Duplicate Yahoo daily-bar session")
    try:
        parsed_sessions = [date.fromisoformat(session) for session in sessions]
    except ValueError as exc:
        raise PublicMarketDataError("Invalid Yahoo daily-bar session date") from exc
    if any(day.isoformat() != session for day, session in zip(parsed_sessions, sessions)):
        raise PublicMarketDataError("Noncanonical Yahoo daily-bar session date")
    latest_session = retrieved.astimezone(EASTERN).date()
    if parsed_sessions != sorted(parsed_sessions) or any(day > latest_session for day in parsed_sessions):
        raise PublicMarketDataError("Unordered or future Yahoo daily-bar session")

    warnings = []
    if quote["quality"] == "MISSING":
        warnings.append("CURRENT_TIMESTAMPED_INTRADAY_BAR_UNAVAILABLE")
    refresh_status = (
        "FAILED" if not bars and quote["quality"] == "MISSING"
        else "PARTIAL" if errors or not bars or quote["quality"] == "MISSING"
        else "COMPLETE"
    )
    body = {
        "schema": SCHEMA,
        "symbol": symbol,
        "provider": "yfinance",
        "provider_endpoint_kind": "PUBLIC_YAHOO_HISTORY",
        "data_provenance": "PUBLIC_PROVIDER_DATA",
        "daily_bar_timestamp_basis": "YAHOO_SESSION_DATE_NO_CLOSE_TIME",
        "refresh_status": refresh_status,
        "provider_errors": errors,
        "warnings": warnings,
        "request_started_at": started.isoformat(),
        "retrieved_at": retrieved.isoformat(),
        "quote": quote,
        "daily_bars": [bar.as_dict() for bar in bars],
        "paper_entry_authorized": False,
        "broker_order_created": False,
        "private_account_accessed": False,
        "automatic_refresh_enabled": False,
        "operational_acceptance": False,
    }
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":"), allow_nan=False)
    body["record_id"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return body


async def fetch_yahoo_public_record(
    symbol: str,
    *,
    client: YFinanceClient | None = None,
) -> dict[str, Any]:
    symbol = _symbol(symbol)
    provider = client or YFinanceClient(min_interval_sec=1.0, timeout_sec=15.0)
    started = utcnow()
    errors: list[str] = []
    try:
        intraday = await provider.history(
            symbol,
            period="5d",
            interval="1m",
            prepost=True,
        )
    except ProviderCallError as exc:
        intraday = None
        errors.append(f"YAHOO_INTRADAY_{exc.failure.code}")
    retrieved_intraday = utcnow()
    try:
        daily = await provider.history(
            symbol,
            period="5y",
            interval="1d",
            prepost=False,
        )
    except ProviderCallError as exc:
        daily = None
        errors.append(f"YAHOO_DAILY_{exc.failure.code}")
    retrieved = utcnow()
    return build_yahoo_public_record(
        symbol,
        intraday,
        daily,
        request_started_at=started,
        retrieved_at=max(retrieved, retrieved_intraday),
        provider_errors=errors,
    )


def require_manual_refresh_spacing(
    path: Path,
    symbol: str,
    *,
    now: datetime | None = None,
) -> None:
    symbol = _symbol(symbol)
    current = _aware(now or utcnow(), "refresh time")
    prior = [
        row for row in read_market_data(path)
        if row["symbol"] == symbol
    ]
    if not prior:
        return
    latest = max(prior, key=lambda row: row["retrieved_at"])
    previous = _aware(datetime.fromisoformat(latest["retrieved_at"]), "prior retrieval time")
    age = (current - previous).total_seconds()
    if age < 0:
        raise PublicMarketDataError("Local clock precedes the last provider retrieval")
    if age < MANUAL_REFRESH_COOLDOWN_SEC:
        remaining = math.ceil(MANUAL_REFRESH_COOLDOWN_SEC - age)
        raise PublicMarketDataError(
            f"Manual Yahoo refresh cooldown active for {remaining} more seconds"
        )


async def refresh_and_store_yahoo_public_data(
    symbol: str,
    path: Path,
    *,
    client: YFinanceClient | None = None,
) -> dict[str, Any]:
    symbol = _symbol(symbol)
    require_manual_refresh_spacing(path, symbol)
    record = await fetch_yahoo_public_record(symbol, client=client)
    return append_market_data(path, record)


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for key, value in pairs:
        if key in output:
            raise PublicMarketDataError("Duplicate market-data record field")
        output[key] = value
    return output


def _reject_nonfinite_json(_value: str) -> None:
    raise PublicMarketDataError("Nonfinite market-data JSON value")


def _validate_record(record: Any) -> dict[str, Any]:
    if type(record) is not dict or record.get("schema") != SCHEMA:
        raise PublicMarketDataError("Unsupported public market-data record")
    symbol = _symbol(record.get("symbol"))
    if (
        record.get("provider") != "yfinance"
        or record.get("data_provenance") != "PUBLIC_PROVIDER_DATA"
        or record.get("daily_bar_timestamp_basis") != "YAHOO_SESSION_DATE_NO_CLOSE_TIME"
        or record.get("refresh_status") not in {"COMPLETE", "PARTIAL", "FAILED"}
        or record.get("paper_entry_authorized") is not False
        or record.get("broker_order_created") is not False
        or record.get("private_account_accessed") is not False
        or record.get("automatic_refresh_enabled") is not False
        or record.get("operational_acceptance") is not False
    ):
        raise PublicMarketDataError("Public-data provenance or authority mismatch")
    _aware(datetime.fromisoformat(record["request_started_at"]), "request_started_at")
    _aware(datetime.fromisoformat(record["retrieved_at"]), "retrieved_at")
    quote = record.get("quote")
    if type(quote) is not dict or quote.get("source") != "yfinance_1m":
        raise PublicMarketDataError("Invalid public quote provenance")
    if quote.get("price") is None:
        if quote.get("quality") != "MISSING" or quote.get("effective_timestamp") is not None:
            raise PublicMarketDataError("Missing quote must not carry a price or timestamp")
    else:
        price = quote["price"]
        if (
            type(price) not in (int, float)
            or not math.isfinite(price)
            or price <= 0
            or quote.get("quality") not in {"LIVE", "FRESH", "REFERENCE", "STALE"}
        ):
            raise PublicMarketDataError("Invalid public quote value or freshness")
        _aware(datetime.fromisoformat(quote["effective_timestamp"]), "quote timestamp")
    bars = record.get("daily_bars")
    if type(bars) is not list or len(bars) > MAX_DAILY_BARS:
        raise PublicMarketDataError("Invalid bounded daily-bar list")
    if any(type(bar) is not dict or bar.get("source") != "yfinance" for bar in bars):
        raise PublicMarketDataError("Daily-bar source provenance mismatch")
    errors = record.get("provider_errors")
    warnings = record.get("warnings")
    if (
        type(errors) is not list
        or any(type(code) is not str or not code or len(code) > 80 for code in errors)
        or type(warnings) is not list
        or any(type(code) is not str or not code or len(code) > 80 for code in warnings)
    ):
        raise PublicMarketDataError("Invalid public market-data error/warning records")
    canonical = dict(record)
    record_id = canonical.pop("record_id", None)
    encoded = json.dumps(canonical, sort_keys=True, separators=(",", ":"), allow_nan=False)
    if record_id != hashlib.sha256(encoded.encode("utf-8")).hexdigest():
        raise PublicMarketDataError("Public market-data record digest mismatch")
    if record["symbol"] != symbol:
        raise PublicMarketDataError("Public market-data symbol is not normalized")
    return record


def read_market_data(path: Path) -> list[dict[str, Any]]:
    path = Path(path)
    if not path.exists():
        return []
    if path.stat().st_size > MAX_STORE_BYTES:
        raise PublicMarketDataError("Public market-data journal exceeds its size limit")
    rows: list[dict[str, Any]] = []
    with path.open("rb") as stream:
        while True:
            raw = stream.readline(MAX_RECORD_BYTES + 1)
            if not raw:
                break
            if len(raw) > MAX_RECORD_BYTES or not raw.endswith(b"\n"):
                raise PublicMarketDataError("Oversized or incomplete market-data journal record")
            try:
                row = json.loads(
                    raw,
                    object_pairs_hook=_unique_object,
                    parse_constant=_reject_nonfinite_json,
                )
                rows.append(_validate_record(row))
            except (UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
                raise PublicMarketDataError("Unreadable public market-data journal record") from exc
    return rows


def append_market_data(path: Path, record: dict[str, Any]) -> dict[str, Any]:
    path = Path(path)
    valid = _validate_record(record)
    payload = json.dumps(valid, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n"
    if len(payload.encode("utf-8")) > MAX_RECORD_BYTES:
        raise PublicMarketDataError("Public market-data record exceeds its size limit")
    with _STORE_LOCK:
        read_market_data(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        existed = path.exists()
        with path.open("a", encoding="utf-8", newline="\n") as stream:
            write_flushed(stream, payload)
        if not existed:
            sync_parent(path)
    return valid


def market_data_read_model(path: Path) -> dict[str, Any]:
    latest: dict[str, dict[str, Any]] = {}
    rows = read_market_data(path)
    for row in rows:
        symbol = row["symbol"]
        prior = latest.get(symbol)
        if prior is None or row["retrieved_at"] > prior["retrieved_at"]:
            latest[symbol] = row
    return {
        "schema": "ATLAS_PERSONAL_PUBLIC_MARKET_DATA_READ_V1",
        "data_provenance": "PUBLIC_PROVIDER_DATA",
        "record_count": len(rows),
        "latest_by_symbol": [latest[symbol] for symbol in sorted(latest)],
        "paper_entry_authorized": False,
        "broker_order_created": False,
        "operational_acceptance": False,
    }
