# Atlas R14 — Hyperliquid public-book offline schema and safe refusal evidence (2026-11-10)

## Completed

**OFFLINE DIAGNOSTIC IMPROVEMENT VERIFIED. No additional provider requests or trading authority.** Atlas's selected release remains native R14 `7ff9d3dba2eabe110f843c13efac49464805de2a`, selected revision 13 SHA-256 `6b1e04b8f733d46421c81a5d158dbafbecf052e6f3a8e8289d175caca96d4e31`.

The earlier one-shot BTC public-data probe was refused and consumed **two** permitted attempts. Its original result contained a generic refusal only. No raw provider response or authenticated quote was preserved, so the particular refusal's root cause **cannot be reconstructed from the stored evidence**. The canonical 12-attempt Hyperliquid public request budget remains **10 used, 2 remaining**, confirmed via SQLite read-only mode. No automatic retry, new allowance, budget reset, network call, installed runtime modification or financial PAPER startup was performed during this diagnostic.

## Verified offline compatibility and diagnostic improvement

Hyperliquid's publicly documented `l2Book` format supplies `coin`, `time` in Unix milliseconds, and `levels` with separate bid and ask arrays and Decimal-compatible string price/size fields. A new offline official-shaped BTC fixture passes the *actual* existing `_paper_execution_observation` adapter and then the R14 data-only `admit_public_book` function. The test demonstrates that the basic documented response layout is compatible with the current selected R14 adapter source, **not that the failed live sample succeeded**.

The selected-R14 probe `scripts/observation_runtime/atlas_r14_hyperliquid_public_book_probe.py` now maps the existing `HyperliquidPublicBookAdmissionRefused.reason_code` to a fixed reviewed allowlist: `SYMBOL_NOT_ALLOWLISTED`, `OBSERVATION_CLOCK_TYPE`, `OBSERVATION_CLOCK_REVERSED`, `OBSERVATION_DURATION_EXCEEDED`, `METADATA_ENVELOPE`, `METADATA_PART_TYPES`, `BOOK_ENVELOPE`, `BOOK_COIN_MISMATCH`, `BOOK_TIMESTAMP_TYPE`, `BOOK_TIMESTAMP_FUTURE`, `BOOK_TIMESTAMP_STALE`. The output stays a bounded nonsecret token prefixed `HL_PUBLIC_BOOK_`; arbitrary, unrecognized or malicious reason strings collapse to `HL_PUBLIC_BOOK_ADMISSION_REFUSED`. Existing NTP, HTTP transport/status/timeout, and budget classifications remain sanitized. No provider response body, private fields, URLs or credentials are logged.

New offline fixture tests `tests/test_atlas_r14_hl_offline_schema_diagnostics.py` assert exact documented-shaped positive bid/ask parsing and nonfinancial scope, stale/future/missing/wrong-book and excessive observation-time first-gate reasons, hostile reason-string redaction, nonfinite values, and impossible price/size refusal. They do not open a network socket, create a budget or touch an operating account.

## Executed validation

- Focused adapter + selected R14 probe + new offline fixture: **78 passed, 0 failed**, 2.78 seconds.
- Expanded selected R14 Hyperliquid provider-record, source/readiness, original public-book adapter and offline fixture: **128 passed, 0 failed**, 4.63 seconds, with one pre-existing Starlette/httpx deprecation warning.
- No live API retry: no information about the previous generic refusal was invented. Existing native source/selector, budget remaining, desktop launch permissions and all financial NO-GO flags remain unmodified.

## Next practical blockers

1. **Qualify public source transport**, using fixed source eligibility and review of the existing request gate. Only a separately authorized bounded public-data observation may consume the remaining two requests; do not silently replenish or repeat them. The new error categorization will distinguish specific safe classes if a later run is authorized and fails.
2. **Verify Alpaca IEX entitlement and fresh data** independently before any credentialed observation, and handle limited quote subscription coverage without claiming Robinhood equivalence or NBBO.
3. **Qualify two native financial PAPER writers and accounting** for QD and Hyperliquid, their continuous independent clock and risk limits, and then demonstrate the selected-R14 owner lifecycle through supervised actual simulated entry/monitor/Stop/drain/recovery. The installed Stop transport already passed disposable tests, not genuine financial commissioning.
4. Connect the manually controlled Start/Stop desktop shortcuts, dashboard, and Discord alerts only after operating acceptance; Kalshi newly listed YES/NO contracts remain a distinct unfinished venue.

**Full financial PAPER production remains NO-GO: 0/9 operating gates independently accepted.** No live trading, private accounts, real order, service startup, Windows boot/clock change, VPS/paid data, or Project Genesis modification occurred.
