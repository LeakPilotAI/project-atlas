# Provider metadata consistency refusal — October 20, 2026

Second automatically selected scoped increment. Production NO-GO; no provider traffic or runtime census.

## Confirmed defect and minimal correction

The original reproducer records 10 failed /4 passing cases: explicit chart/quote exchangeTimezoneName=Europe/London, malformed timezone values and incompatible instrumentType metadata were ignored, and accepted under the caller's US_ETF identity. A shared optional-identity check in the existing isolated market_replay normalizers now refuses explicit contradictions before storage. Recognized timezone is America/New_York; unreviewed aliases refuse conservatively. instrumentType and quoteType, if present, must match EQUITY or ETF for the explicitly requested asset class. Conflicting fields cannot override each other. Missing optional fields retain the existing limited fixture contract; absence is not proof of U.S. listing. Fixed gmtoffset is deliberately not used as a timezone authority across DST.

No source payload mutation, journal schema change, production scanner change or provider permission inference. Four positive cases prove matching explicit metadata normalizes identically to the original metadata-absent fixtures. The prior 10-failure output and initial narrow import-formatting finding are retained. quoteType cases were then added because quote-shaped responses can carry that field independently.

## Validation

- Final metadata suite:20 passed,0 failed/skipped (16 negative source/storage refusal cases plus4 exact positive representation cases).
- Final broader selection:436 passed,0 failed/skipped; includes all40 pinned request-tier/deadline cases and20 metadata cases plus market, history, quality, budgets, dispatch, shutdown and durable PAPER regressions.
- Existing frontend suites:271 passed,0 failed/skipped; unchanged JavaScript in both current increments. Success bytes tested by existing expected API fixture and frontend integration.
- Current targeted Ruff, Python compilation, approved-updater PowerShell parsing and diff checks pass. No full canonical lint waiver or full production-suite acceptance.

Delay/adjustment limitation: quote delays remain explicit unit-unverified fixture metadata and nonzero values cannot become current quotes. Raw chart bars are labeled completed minute bar closes, not executable quotes or verified adjusted historical prices. This change does not prove real chart delay, split/dividend adjustment, venue status, consolidated data or timestamp semantics. Actual provider-specific semantics/rights must be accepted separately. Do not infer live status from a fresh timestamp or endpoint name.

## Decision and exact next task

Both increments improve usable offline market flow. No full Atlas/dashboard startup permission exists. Full local production-like startup remains locked; the inert fixture ASGI/consumer is independently testable. Premarket, regular-session, after-hours, early-close and DST fixture paths remain implemented/tested. Live feeds still require approved provider/exchange entitlements, storage/display/historical rights, safe credential verification, actual wire-budget/deadline/vendor semantics and operator-authorized observation-only runtime integration/acceptance.

Next automatically selected task: implement a bounded opt-in chart provenance diagnostic for explicitly supplied source payloads, preserving legacy normalized bytes. It should distinguish raw chart-close fields from optional adjusted-close series, report missing/unverified delay units and adjustment basis without inventing entitlement or live status, bind diagnostic to exact source bytes/hash and observation clock, refuse malformed/nonfinite/misaligned optional series, and expose usable offline API/consumer evidence only if existing architecture supports a narrow addition. First inspect current metadata/provenance contracts to avoid duplication. Continue Evidence Engine/AFI accountability and other independent seven-phase work afterward. Do not stop for the local milestone or activate providers/startup.

All21 canonical decisions remain byte-identical (5 scoped PASS,13 BLOCKED,3 NOT_TESTED). Startup denial untouched. Full seven phases and cross-phase AFI/E136/prediction/Gaming requirements are preserved in the master. AFI-1–10 PENDING. No production integration, service/Docker/Genesis action, PAPER/live/Discord, real storage/backup/restore, protected config/ACL/shortcut or Git mutation.
