# Pinned provider request tier and synthetic deadline acceptance — 2026-10-20

Scoped offline functionality accepted; production NO-GO. Existing native Goal retained.

## Working implementation

`scripts/observation_runtime/yf_wire_fixture.py` executes the complete reviewed installed yfinance 1.7.0 data.py request tier in a fresh private namespace, after verifying SHA-256 5f41a4cec99d50be3a13c8ae5f2674e1b5e1582be1a861fcdbb57bba783629da. All HTTP, imports, cookie cache, configuration, logging, consent parsing and sleeping dependencies are synthetic. No real yfinance package, requests/curl backend, credential store or provider connection is instantiated. This is not an arbitrary-code security sandbox. One local documented S102 annotation permits only the pinned fixture execution, not arbitrary expressions; no global lint waiver.

The existing SQLite attempt ledger commits before every fake cookie/crumb, consent GET/POST, chart/quote, redirect and retry attempt. Missing, malformed, contradictory and uncertain debit acknowledgements refuse and latch. No debit refund follows ambiguous failure. Known same-session ledger rollback refuses; this is not an independent rollback anchor or account-wide enforcement. Default synthetic 429 halts further attempts; an explicit test-only override observes the vendor retry branch and does not authorize production retries.

Actual reviewed code -> fake transport -> existing normalization -> disposable SQLite -> in-process ASGI -> existing Node dashboard consumer is tested. Three sessions retain previously accepted fixture classification and freshness behavior. Nine prior API/HTML successful representations remain unchanged from the preceding read-view acceptance.

## Second measured gap and correction

The preserved test confirms SDK cookie bootstrap requests timeout=30 even when the outer request asks for five seconds. Default fixture timeout-ceiling refusal remains strict. An explicit VirtualDeadline option now clamps each fake hop to the minimum of requested timeout, ceiling and remaining shared virtual time. Redirects, SDK backoff and retries consume that same scope. Checks before debit, after debit, before result and on cached access refuse expiry. Committed reservation lost to deadline expiry is retained without fake send. Late fake results cannot be accepted. This is controlled virtual time, not a real monotonic-clock adapter, hard OS deadline, real transport cancellation or proof that blocked third-party workers terminate.

## Validation

- Initial complete request-tier focused suite: 29 passed; strengthened timeout reproducer separately 1 passed /28 deselected.
- Final request-tier/deadline focused suite: 40 passed, zero failures/skips; 11 additional deadline cases.
- Final broader isolated selection: 416 passed, zero failures/skips (market ingestion, quality/history/replay, storage, read views, wire budgets, dispatch, shutdown and PAPER durable acknowledgement). Previous 405-run evidence retained; counts are successive selections, not additive.
- Existing two offline dashboard suites: 271 passed, zero failures/skips; no frontend source changed in this increment.
- Targeted Ruff passes; compilation, checkpoint-updater PowerShell parsing and Git diff checks recorded separately. Earlier static failures are preserved and corrected. No full canonical suite or native browser/runtime acceptance claim.
- Prior 82 intended source/evidence pins verified unchanged before checkpoint; only new fixture module, its tests and this report added to the intended source inventory. Continuity appended and managed master updated by approved updater only.

## Actual readiness and remaining prerequisites

Full local Atlas startup remains locked and NOT authorized; no fresh process/Docker census or dashboard server health verification. The inert replay factory and offline consumer are technically testable without a network server. This does not establish that the complete application is ready to launch.

Premarket/regular/after-hours provider-shaped quote/bar fixture paths are implemented and tested, including calendars, timestamp/freshness/refusal, provenance, receipts and read-only display. Actual continuous feed coverage remains unverified. No API key, subscription or entitlement is assumed present or absent. Required before live collection: provider/exchange automated-use and U.S. equity/ETF session coverage, real-time/delay status, historical/storage/display/redistribution rights appropriate to scope; safe credential validation; actual transport fan-out budgets/deadlines/provider semantics; explicit observation-only runtime integration/admission and bounded lifecycle acceptance. The repaired launcher is not an observation-only profile and must not bypass startup denial. No external HTTP/WebSocket requests occurred.

All 21 canonical decisions and production lock hashes stay unchanged. PAPER_ONLY/MANUAL_ONLY; no PAPER/prediction/live/Discord activation, Genesis, services, Docker, production stores/ACL/config/shortcuts, backups/restores or Git staging/commit/push/reset/cleanup. Synthetic replay does not prove forecasting skill/profitability or live data authorization.

## Exact continuation

Do not repeat these Linux/Windows fixture runs without a specific changed contract or failure. Next automatically selected offline task: inspect existing bar/quote timestamp normalization against vendor chart metadata for delayed-feed and adjustment semantics; implement only a confirmed missing refusal or explicit fixture provenance diagnostic, preserving accepted legacy bytes and source evidence. Do not infer live rights, real-time status or adjusted-price semantics merely from endpoint names. Then continue independent Evidence Engine/AFI accountability, prediction PAPER durability and seven-phase reliability work. No isolated milestone completes the full Goal.

Seven phases remain: (1) core lifecycle/backup/restoration/provider/cash/lint/package/Gaming reliability; (2) Evidence Engine PIT/history/replay/calibration; (3) bounded crypto PAPER eligibility/costs/settlement, no activation; (4) cross-market intelligence; (5) SaaS/rights/tenant isolation; (6) institutional security/governance; (7) commercial validation. AFI-1–10 PENDING, E136 consent/recovery/no-backfill, prediction exactly-once/predeadline/autoflat and PM-V2 safeguards remain in the master unchanged. Full authoritative phase inventory is included verbatim in the managed checkpoint.
