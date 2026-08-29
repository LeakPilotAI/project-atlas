"""Investment-engine enumerations. No scoring. No trading-engine coupling."""

from __future__ import annotations

from enum import Enum


class AssetType(str, Enum):
    STOCK = "STOCK"
    ETF = "ETF"
    INDEX = "INDEX"
    SECTOR_ETF = "SECTOR_ETF"
    OTHER = "OTHER"
    UNKNOWN = "UNKNOWN"


class DataQuality(str, Enum):
    FRESH = "FRESH"
    STALE = "STALE"
    MISSING = "MISSING"
    CONFLICTING = "CONFLICTING"
    UNKNOWN = "UNKNOWN"


class ThesisState(str, Enum):
    STRONG = "STRONG"
    INTACT = "INTACT"
    UNDER_PRESSURE = "UNDER_PRESSURE"
    DAMAGED = "DAMAGED"
    BROKEN = "BROKEN"
    UNKNOWN = "UNKNOWN"


class InvestmentAlertState(str, Enum):
    WATCH = "WATCH"
    ACCUMULATION = "ACCUMULATION"
    DEEP_VALUE = "DEEP_VALUE"
    GENERATIONAL_OPPORTUNITY = "GENERATIONAL_OPPORTUNITY"
    NO_ACTION = "NO_ACTION"
    THESIS_BROKEN = "THESIS_BROKEN"


class EvidenceQuality(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INSUFFICIENT = "INSUFFICIENT"
    UNKNOWN = "UNKNOWN"


class RiskTolerance(str, Enum):
    CONSERVATIVE = "CONSERVATIVE"
    MODERATE = "MODERATE"
    AGGRESSIVE = "AGGRESSIVE"
    UNKNOWN = "UNKNOWN"


class InvestmentHorizon(str, Enum):
    YEARS = "YEARS"
    MULTI_YEAR = "MULTI_YEAR"
    DECADE = "DECADE"
    UNKNOWN = "UNKNOWN"


class EvaluationStatus(str, Enum):
    """Why a row exists. Distinct from investment classification.

    VALID              — enough data to score; classification is the research call
    VALID_NO_ACTION    — enough data; genuinely not an accumulation setup
    INSUFFICIENT_DATA  — too few usable fields to trust a call
    PROVIDER_ERROR     — Yahoo/client failure, no usable substitute
    RATE_LIMITED       — 429 / rate limit, no usable substitute
    STALE_DATA         — scored from cache/last print past freshness TTL
    CONFLICTING_DATA   — irreconcilable values, not repaired
    UNKNOWN            — cannot tell
    """

    VALID = "VALID"
    VALID_NO_ACTION = "VALID_NO_ACTION"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    PROVIDER_ERROR = "PROVIDER_ERROR"
    RATE_LIMITED = "RATE_LIMITED"
    STALE_DATA = "STALE_DATA"
    CONFLICTING_DATA = "CONFLICTING_DATA"
    UNKNOWN = "UNKNOWN"
