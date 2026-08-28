"""Investment storage is isolated from Hyperliquid paper journals."""

from __future__ import annotations

from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[2]
DATA_DIR = _BACKEND / "data" / "investment"

LEDGER_PATH = DATA_DIR / "paper_investment_ledger.jsonl"
HOLDINGS_PATH = DATA_DIR / "holdings.json"
OPPORTUNITIES_PATH = DATA_DIR / "opportunities.jsonl"
EVIDENCE_PATH = DATA_DIR / "evidence.jsonl"

# Trading engine files — never read/write these from this package.
TRADING_PAPER_JOURNAL = _BACKEND / "data" / "paper_journal.jsonl"
TRADING_SHADOW_CANDIDATES = _BACKEND / "data" / "shadow_candidates.jsonl"


def ensure_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def trading_paths() -> tuple[Path, Path]:
    return TRADING_PAPER_JOURNAL, TRADING_SHADOW_CANDIDATES


def assert_storage_separated() -> None:
    if LEDGER_PATH.resolve() == TRADING_PAPER_JOURNAL.resolve():
        raise RuntimeError("Investment ledger must not share paper_journal.jsonl")
    if DATA_DIR.resolve() == (_BACKEND / "data").resolve():
        raise RuntimeError("Investment data must live under data/investment/")
