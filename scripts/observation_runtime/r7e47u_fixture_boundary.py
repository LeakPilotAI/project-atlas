"""Data-only synthetic snapshot validation; no executable fixtures or network."""
import json
import math
import re
from dataclasses import dataclass


class FixtureRefused(ValueError):
    pass


@dataclass(frozen=True)
class MarketSnapshot:
    provider: str
    symbol: str
    timestamp_ms: int
    price: float
    volume: float


class FixtureBoundary:
    MAX_BYTES = 4096
    FIELDS = frozenset({"provider", "symbol", "timestamp_ms", "price", "volume"})

    def __init__(self, provider: str, max_records: int):
        if (
            type(provider) is not str
            or re.fullmatch(r"[a-z][a-z0-9_]{0,31}", provider) is None
            or type(max_records) is not int
            or not 1 <= max_records <= 10000
        ):
            raise FixtureRefused("Invalid synthetic fixture admission")
        self.provider = provider
        self.max_records = max_records
        self.attempted = 0
        self.closed = False

    def ingest(self, raw: bytes) -> MarketSnapshot:
        if self.closed:
            raise FixtureRefused("Fixture boundary closed")
        if self.attempted >= self.max_records:
            raise FixtureRefused("Synthetic record budget exhausted")
        if type(raw) is not bytes or not 1 <= len(raw) <= self.MAX_BYTES:
            raise FixtureRefused("Expected bounded JSON bytes")

        self.attempted += 1

        try:
            record = json.loads(
                raw.decode("utf-8"),
                parse_constant=lambda value: (_ for _ in ()).throw(
                    FixtureRefused("Nonfinite JSON constant")
                ),
            )
        except (UnicodeError, ValueError, TypeError) as error:
            raise FixtureRefused("Malformed synthetic JSON") from error

        if type(record) is not dict or set(record) != self.FIELDS:
            raise FixtureRefused("Unexpected synthetic snapshot schema")

        provider = record["provider"]
        symbol = record["symbol"]
        timestamp = record["timestamp_ms"]
        price = record["price"]
        volume = record["volume"]

        if type(provider) is not str or provider != self.provider:
            raise FixtureRefused("Provider mismatch")

        if (
            type(symbol) is not str
            or re.fullmatch(r"[A-Z0-9][A-Z0-9._/-]{0,31}", symbol) is None
        ):
            raise FixtureRefused("Invalid symbol")

        if type(timestamp) is not int or not 0 <= timestamp <= 9999999999999:
            raise FixtureRefused("Invalid timestamp")

        for name, value in (("price", price), ("volume", volume)):
            if (
                type(value) not in (int, float)
                or not math.isfinite(value)
                or value < 0
                or (name == "price" and value == 0)
            ):
                raise FixtureRefused("Invalid " + name)

        return MarketSnapshot(
            provider=provider,
            symbol=symbol,
            timestamp_ms=timestamp,
            price=float(price),
            volume=float(volume),
        )

    def stop(self) -> None:
        self.closed = True