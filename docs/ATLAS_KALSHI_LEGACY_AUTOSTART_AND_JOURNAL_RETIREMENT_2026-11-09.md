# Atlas Kalshi legacy autostart and direct PAPER journal entry retirement — 2026-11-09

## User-approved exclusive scope

The only planned Kalshi PAPER strategy is **exchange-proven brand-new binary YES/NO listings**, with evidence-backed early price discovery and potential small **NET** exits after actual executable depth, taker fees and slippage. At most one position, no combos/parlays/multivariate contracts/stacking, no mature/general pre-event reclaim fallback, no hold to event or settlement, no funded capital. This replacement strategy is not yet implemented or commissioned for financial PAPER. Existing publicly retrieved market and order book research remains available as diagnostics only.

## Real mismatch closed

- Legacy `backend/app/main.py` had `("prediction_paper_automation",prediction_paper_automation.start)` among normal startup services. The old automation scanned PRE_EVENT_RECENT_RECLAIM_V1 research; although unattended PAPER opening was reported blocked, running this obsolete scanner automatically contradicted exclusive new-listing scope. Removed **only** that startup registration. Preserved the matching `prediction_paper_automation.stop` on shutdown to clean up a preexisting worker, plus status reporting.
- Previous milestone retired `POST /api/prediction/paper/open/{ticker}`, but direct Python `prediction_paper_journal.open_from_evaluation` remained reachable. The shared application-owned `PredictionPaperJournal` singleton now refuses every old/new PAPER entry with `KALSHI_LEGACY_PAPER_JOURNAL_ENTRY_RETIRED`, **before reading positions, opening any data source, appending financial events or treating caller-controlled strategy strings as authorized**. The replacement will need its own independently accepted source/issuer/custody and dedicated approved writer.
- Isolated `PredictionPaperJournal(journal_path=tmp_path/...)` instances still run the existing disposable/legacy simulation tests and historical scenario replay; they are not production financial source authority. Existing journal readback, safe `close_from_orderbook`, emergency flat and historical diagnostics are unmodified.
- Updated two old `tests/test_prediction_history_window.py` expectations that contradicted already-established 2026-11-07 source guards: legacy scanner research requests must begin no earlier than the exchange's verified open/create timestamp (not an arbitrary full three hours); a prior intrabar high is hindsight and cannot make a candidate PAPER-eligible (`HISTORICAL_HIGH_NOT_FORWARD_EXIT_EVIDENCE`). Neither code guard was relaxed for test convenience.
- Added `tests/test_kalshi_legacy_autostart_retirement.py` to prove no old startup binding and retained cleanup, direct singleton attempt fails before journaling/position read, manual route refuses before provider I/O, isolated injected test journal remains usable, and public research/safe close route remain available.

## Local test results

- Uncredentialed Hyperliquid public-data model, core PAPER funding/margin/native accounting, PAPER setup shutdown, Kalshi new-listing eligibility and quote analysis: **103 passed, zero failures**.
- Removed old startup hook and checked Kalshi/legacy market API/automation regression: **80 passed**.
- Expanded Kalshi registration, existing PAPER engine/persistence/history, new-listing policy and forward observer: **138 passed, zero failures, two third-party deprecation warnings**.
- **No** live Hyperliquid order book, wallet, provider-rights grant or financial account operation, and **no** private Kalshi account or trading. Tests are isolated fixtures; no financial PAPER acceptance is implied.

## What must still happen

User-approved source-only guard is a workspace change. Installed selected native revision 12 remains unchanged until a future reviewed release is built, installed and independently selected. Kalshi new-listing PAPER needs independent exchange-first-appearance proof, chronological early orderbooks, executable cost-aware forward-edge estimation, a properly bound new PAPER account/journal, and safe short-term Stop+flatten before it can activate. QD/Hyperliquid financial admission remains 0/9 accepted workstreams; Kalshi is an unaccepted third venue.

Do not resume the old general pre-event-reclaim strategy, add a fallback, or loosen new-listing data/edge requirements to boost trade counts. No Genesis, provider access, actual or simulated financial orders, Windows boot/time, credentials, native selected release/shortcuts or remote GitHub push changed.
