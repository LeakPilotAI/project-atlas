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
ALERT_STATE_PATH = DATA_DIR / "alert_state.json"
PLANS_PATH = DATA_DIR / "plans.jsonl"
PAPER_STATE_PATH = DATA_DIR / "paper_account.json"
PORTFOLIO_PATH = HOLDINGS_PATH
OBSERVATIONS_PATH = DATA_DIR / "observations.jsonl"
OUTCOMES_PATH = DATA_DIR / "outcomes.jsonl"
FETCH_STATE_PATH = DATA_DIR / "fetch_state.json"
LATEST_DIR = DATA_DIR / "latest"
SCAN_LOG_PATH = DATA_DIR / "scan_log.jsonl"
PROVIDER_HEALTH_PATH = DATA_DIR / "provider_health.json"
PROVIDER_HEALTH_LOG = DATA_DIR / "provider_health.jsonl"
LAST_CYCLE_PATH = DATA_DIR / "last_cycle.json"


# Trading engine files — never read/write these from this package.
TRADING_PAPER_JOURNAL = _BACKEND / "data" / "paper_journal.jsonl"
TRADING_SHADOW_CANDIDATES = _BACKEND / "data" / "shadow_candidates.jsonl"


def ensure_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    LATEST_DIR.mkdir(parents=True, exist_ok=True)
    if PACKAGE_UNIVERSE_EXAMPLE.exists() and not UNIVERSE_EXAMPLE_PATH.exists():
        UNIVERSE_EXAMPLE_PATH.write_text(
            PACKAGE_UNIVERSE_EXAMPLE.read_text(encoding="utf-8"),
            encoding="utf-8",
        )


def bootstrap_universe_if_missing() -> None:
    """Copy the example universe only when the operator file does not exist.

    Does not hard-code tickers in the engine. Operator may add/remove freely.
    """
    ensure_dirs()
    if UNIVERSE_PATH.exists():
        return
    src = PACKAGE_UNIVERSE_EXAMPLE if PACKAGE_UNIVERSE_EXAMPLE.exists() else UNIVERSE_EXAMPLE_PATH
    if src.exists():
        UNIVERSE_PATH.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")


def trading_paths() -> tuple[Path, Path]:
    return TRADING_PAPER_JOURNAL, TRADING_SHADOW_CANDIDATES


def assert_storage_separated() -> None:
    if LEDGER_PATH.resolve() == TRADING_PAPER_JOURNAL.resolve():
        raise RuntimeError("Investment ledger must not share paper_journal.jsonl")
    if DATA_DIR.resolve() == (_BACKEND / "data").resolve():
        raise RuntimeError("Investment data must live under data/investment/")
    if OBSERVATIONS_PATH.resolve() == TRADING_PAPER_JOURNAL.resolve():
        raise RuntimeError("Investment observations must not share paper_journal.jsonl")
    if OUTCOMES_PATH.resolve() == TRADING_PAPER_JOURNAL.resolve():
        raise RuntimeError("Investment outcomes must not share paper_journal.jsonl")
