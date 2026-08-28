"""Investment storage is isolated from Hyperliquid paper journals."""

from __future__ import annotations

from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[2]
PACKAGE_DIR = Path(__file__).resolve().parent
DATA_DIR = _BACKEND / "data" / "investment"

LEDGER_PATH = DATA_DIR / "paper_investment_ledger.jsonl"
HOLDINGS_PATH = DATA_DIR / "holdings.json"
OPPORTUNITIES_PATH = DATA_DIR / "opportunities.jsonl"
EVIDENCE_PATH = DATA_DIR / "evidence.jsonl"
UNIVERSE_PATH = DATA_DIR / "universe.json"
UNIVERSE_EXAMPLE_PATH = DATA_DIR / "universe.example.json"
PACKAGE_UNIVERSE_EXAMPLE = PACKAGE_DIR / "universe.example.json"
HISTORY_DIR = DATA_DIR / "history"
SNAPSHOTS_PATH = DATA_DIR / "snapshots.jsonl"

# Trading engine files — never read/write these from this package.
TRADING_PAPER_JOURNAL = _BACKEND / "data" / "paper_journal.jsonl"
TRADING_SHADOW_CANDIDATES = _BACKEND / "data" / "shadow_candidates.jsonl"


def ensure_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    if PACKAGE_UNIVERSE_EXAMPLE.exists() and not UNIVERSE_EXAMPLE_PATH.exists():
        UNIVERSE_EXAMPLE_PATH.write_text(
            PACKAGE_UNIVERSE_EXAMPLE.read_text(encoding="utf-8"),
            encoding="utf-8",
        )


def trading_paths() -> tuple[Path, Path]:
    return TRADING_PAPER_JOURNAL, TRADING_SHADOW_CANDIDATES


def assert_storage_separated() -> None:
    if LEDGER_PATH.resolve() == TRADING_PAPER_JOURNAL.resolve():
        raise RuntimeError("Investment ledger must not share paper_journal.jsonl")
    if DATA_DIR.resolve() == (_BACKEND / "data").resolve():
        raise RuntimeError("Investment data must live under data/investment/")
