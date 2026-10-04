from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable, FrozenSet


class EngineDomain(str, Enum):
    HYPERLIQUID_PERP = "HYPERLIQUID_PERP"
    EQUITY_INVESTMENT = "EQUITY_INVESTMENT"
    ORCHESTRATION = "ORCHESTRATION"


class DomainViolation(ValueError):
    pass


def normalize_symbol(symbol: str) -> str:
    value = str(symbol or "").strip().upper()
    if not value:
        raise DomainViolation("symbol is required")
    return value


def normalize_universe(symbols: Iterable[str]) -> FrozenSet[str]:
    return frozenset(normalize_symbol(s) for s in symbols if str(s or "").strip())


def require_hyperliquid_market(symbol: str, hyperliquid_symbols: Iterable[str]) -> str:
    """Return normalized symbol only when it exists in the supplied HL universe.

    Atlas must never infer that an equity ticker is a perp market. The caller must
    supply the current Hyperliquid universe obtained from the Hyperliquid data path.
    """
    normalized = normalize_symbol(symbol)
    universe = normalize_universe(hyperliquid_symbols)
    if normalized not in universe:
        raise DomainViolation(f"{normalized} is not in the current Hyperliquid market universe")
    return normalized


@dataclass(frozen=True)
class AtlasEngineLayout:
    perp: EngineDomain = EngineDomain.HYPERLIQUID_PERP
    investment: EngineDomain = EngineDomain.EQUITY_INVESTMENT
    orchestration: EngineDomain = EngineDomain.ORCHESTRATION

    @property
    def isolated(self) -> bool:
        return len({self.perp, self.investment, self.orchestration}) == 3


ATLAS_ENGINE_LAYOUT = AtlasEngineLayout()
